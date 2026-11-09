"""
main.py — API FastAPI.

Espone il motore (engine.py) e il database come servizio HTTP. Il frontend
(cartella /frontend) parla solo con queste rotte via fetch(): nessuna logica
di business nel browser oltre alla presentazione.

Avvio locale:
    uvicorn backend.main:app --reload
poi apri http://127.0.0.1:8000/
"""

from calendar import monthrange
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models, schemas
from .database import SessionLocal, init_db
from .engine import ASSIGNABLE_TYPES, ShiftEngine
from .excel_export import build_excel

app = FastAPI(title="Gestione Sicurezza — Planning Turni")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


def db_session() -> Session:
    return SessionLocal()


# ---------------------------------------------------------------------
# Dipendenti
# ---------------------------------------------------------------------

def _compute_short_codes(employees: list[dict]) -> dict[str, str]:
    """Sigla più corta possibile (2 lettere di default, come richiesto per
    stringere le colonne di stampa) per ogni dipendente — allungata SOLO
    per chi altrimenti collide con un collega (es. BERTRAND e BEJAOUI
    diventerebbero entrambi "BE" a 2 lettere: quel gruppo passa a 3
    lettere, "BER"/"BEJ", finché non è unico). Unica fonte di verità,
    calcolata una volta sola sull'intera squadra, usata sia a schermo che
    nell'export Excel/stampa — così le sigle sono sempre le stesse ovunque
    (richiesta utente 2026-09-25)."""
    names = {e["id"]: (e.get("last_name") or e["id"]).upper() for e in employees}
    codes: dict[str, str] = {}
    todo = set(names.keys())
    length = 2
    while todo and length <= 12:
        buckets: dict[str, list[str]] = {}
        for eid in todo:
            buckets.setdefault(names[eid][:length], []).append(eid)
        for code, group in buckets.items():
            if len(group) == 1:
                codes[group[0]] = code
                todo.discard(group[0])
        length += 1
    for eid in todo:  # caso patologico (cognomi identici): non risolvibile per troncamento
        codes[eid] = names[eid][:length]
    return codes


def _with_short_codes(rows: list[dict]) -> list[dict]:
    codes = _compute_short_codes(rows)
    for r in rows:
        r["short_code"] = codes.get(r["id"], (r.get("last_name") or "")[:2].upper())
    return rows


@app.get("/api/employees")
def list_employees():
    db = db_session()
    try:
        rows = [e.to_dict() for e in db.query(models.Employee).all()]
        return _with_short_codes(rows)
    finally:
        db.close()


@app.post("/api/employees")
def create_employee(payload: schemas.EmployeeIn):
    db = db_session()
    try:
        eid = f"{payload.last_name.strip().upper()}_{payload.first_name.strip().upper()}"
        existing = db.query(models.Employee).get(eid)
        if existing:
            for field, value in payload.dict().items():
                setattr(existing, field, value)
        else:
            existing = models.Employee(id=eid, **payload.dict())
            db.add(existing)
        db.commit()
        return existing.to_dict()
    finally:
        db.close()


@app.delete("/api/employees/{employee_id}")
def delete_employee(employee_id: str):
    db = db_session()
    try:
        emp = db.query(models.Employee).get(employee_id)
        if not emp:
            raise HTTPException(404, "Dipendente non trovato")
        db.delete(emp)
        db.commit()
        return {"deleted": employee_id}
    finally:
        db.close()


# ---------------------------------------------------------------------
# Vincoli manuali (ferie, malattia, riposo forzato, sostituzione capo...)
# ---------------------------------------------------------------------

@app.get("/api/constraints")
def list_constraints(year: int, month: int):
    db = db_session()
    try:
        rows = (
            db.query(models.ManualConstraint)
            .filter_by(year=year, month=month)
            .all()
        )
        return [c.to_dict() for c in rows]
    finally:
        db.close()


def _recovery_balance(db: Session, employee_id: str) -> dict:
    """Bilancio cumulativo (su tutti i mesi) dei giorni di recupero per un
    dipendente: earned = giorni di straordinario maturati (RecoveryEarned),
    spent = giorni di recupero già presi (ManualConstraint type="recupero").
    Cumulativo e non per-mese, perché il credito può essere speso "nel mese
    successivo o anche in quello corrente", come richiesto."""
    earned = db.query(models.RecoveryEarned).filter_by(employee_id=employee_id).count()
    spent = (
        db.query(models.ManualConstraint)
        .filter_by(employee_id=employee_id, type="recupero")
        .count()
    )
    return {"earned": earned, "spent": spent, "balance": earned - spent}


@app.get("/api/recovery/balances")
def recovery_balances():
    """Bilancio giorni di recupero per tutti i dipendenti, per la vista
    riepilogativa in UI (Personale / Planning)."""
    db = db_session()
    try:
        employees = _load_employees(db)
        earned_rows = (
            db.query(models.RecoveryEarned.employee_id, func.count(models.RecoveryEarned.id))
            .group_by(models.RecoveryEarned.employee_id)
            .all()
        )
        spent_rows = (
            db.query(models.ManualConstraint.employee_id, func.count(models.ManualConstraint.id))
            .filter(models.ManualConstraint.type == "recupero")
            .group_by(models.ManualConstraint.employee_id)
            .all()
        )
        earned_map = dict(earned_rows)
        spent_map = dict(spent_rows)
        return [
            {
                "employee_id": e["id"],
                "earned": earned_map.get(e["id"], 0),
                "spent": spent_map.get(e["id"], 0),
                "balance": earned_map.get(e["id"], 0) - spent_map.get(e["id"], 0),
            }
            for e in employees
        ]
    finally:
        db.close()


@app.post("/api/constraints")
def add_constraint_range(payload: schemas.ConstraintIn):
    if payload.type not in ASSIGNABLE_TYPES:
        raise HTTPException(400, f"Tipo non valido: {payload.type}")
    if payload.day_from > payload.day_to:
        raise HTTPException(400, "Il giorno di inizio deve precedere quello di fine")

    db = db_session()
    try:
        if payload.type == "recupero":
            # Non si può "spendere" più recupero di quanto maturato: conta
            # quanto è già stato preso (su tutti i mesi) e verifica che
            # earned copra anche i nuovi giorni richiesti in questo range.
            requested_days = payload.day_to - payload.day_from + 1
            bal = _recovery_balance(db, payload.employee_id)
            if bal["spent"] + requested_days > bal["earned"]:
                raise HTTPException(400, "insufficient_recovery_balance")

        num_days = monthrange(payload.year, payload.month)[1]
        created = []
        for d in range(payload.day_from, min(payload.day_to, num_days) + 1):
            row = (
                db.query(models.ManualConstraint)
                .filter_by(year=payload.year, month=payload.month, day=d, employee_id=payload.employee_id)
                .first()
            )
            if row:
                row.type = payload.type
            else:
                row = models.ManualConstraint(
                    year=payload.year, month=payload.month, day=d,
                    employee_id=payload.employee_id, type=payload.type,
                )
                db.add(row)
            created.append(row)
        db.commit()
        return [c.to_dict() for c in created]
    finally:
        db.close()


@app.delete("/api/constraints/{constraint_id}")
def delete_constraint(constraint_id: int):
    db = db_session()
    try:
        row = db.query(models.ManualConstraint).get(constraint_id)
        if not row:
            raise HTTPException(404, "Vincolo non trovato")
        db.delete(row)
        db.commit()
        return {"deleted": constraint_id}
    finally:
        db.close()


@app.delete("/api/constraints")
def delete_all_constraints(year: int, month: int):
    db = db_session()
    try:
        db.query(models.ManualConstraint).filter_by(year=year, month=month).delete()
        db.commit()
        return {"deleted_all": True}
    finally:
        db.close()


# ---------------------------------------------------------------------
# Generazione planning
# ---------------------------------------------------------------------

def _load_employees(db: Session) -> list[dict]:
    return _with_short_codes([e.to_dict() for e in db.query(models.Employee).all()])


def _load_constraints_map(db: Session, year: int, month: int) -> dict:
    rows = db.query(models.ManualConstraint).filter_by(year=year, month=month).all()
    return {(r.day, r.employee_id): r.type for r in rows}


def _load_overrides_map(db: Session, year: int, month: int) -> dict:
    rows = db.query(models.PlanningOverride).filter_by(year=year, month=month).all()
    return {(r.day, r.employee_id): r.assignment for r in rows}


def _apply_overrides(days_out: dict, overrides: dict):
    """Applica le correzioni manuali salvate sopra il risultato del motore."""
    for (day, eid), assignment in overrides.items():
        if day not in days_out:
            continue
        for k in ("giorno", "notte", "riposo"):
            if eid in days_out[day][k]:
                days_out[day][k].remove(eid)
        if assignment in ("giorno", "notte", "riposo"):
            days_out[day][assignment].append(eid)


def _generate_full(db: Session, year: int, month: int, chef_present: bool,
                    overtime_employee_ids: list[str] | None = None, overtime_max_extra: int = 0):
    """Genera il planning con il motore e applica sopra le correzioni
    manuali già salvate per quel mese. Punto unico usato da /generate,
    /export e /save, così il risultato è sempre identico ovunque venga
    richiesto (nessuna divergenza tra quello che vedi a schermo, quello
    che scarichi ed eventualmente quello che salvi).

    overtime_employee_ids / overtime_max_extra: selezione ad-hoc (non
    persistente) dei dipendenti disponibili per lo straordinario e del
    numero massimo di giorni extra concessi — vedi engine.py."""
    employees = _load_employees(db)
    constraints = _load_constraints_map(db, year, month)
    engine = ShiftEngine(
        employees, year, month, constraints, chef_present,
        overtime_ids=set(overtime_employee_ids or []),
        overtime_max_extra=overtime_max_extra,
    )
    result = engine.generate()
    if not result.ok:
        # detail strutturato: la UI usa "diagnosis" per spiegare la causa
        # più probabile invece del solo "Nessuna soluzione trovata" (vedi
        # ShiftEngine._diagnose in engine.py) — richiesta utente 2026-09-25.
        raise HTTPException(409, {"error": result.error or "no_solution", "diagnosis": result.diagnosis})

    overrides = _load_overrides_map(db, year, month)
    _apply_overrides(result.days, overrides)
    return employees, result


@app.post("/api/planning/generate")
def generate_planning(payload: schemas.GenerateIn):
    db = db_session()
    try:
        _, result = _generate_full(
            db, payload.year, payload.month, payload.chef_present,
            overtime_employee_ids=payload.overtime_employee_ids,
            overtime_max_extra=payload.overtime_max_extra,
        )
        return {
            "year": payload.year,
            "month": payload.month,
            "num_days": monthrange(payload.year, payload.month)[1],
            "days": result.days,
            "targets": result.targets,
            "night_targets": result.night_targets,
            # Giorni di riposo dovuti nel mese per dipendente (formula "Sacri 15"
            # pro-rata, esclusi ferie/malattia). Varia con le assenze del mese.
            "riposi_dovuti": result.riposi_dovuti,
            # {employee_id: [giorni]} — giorni di straordinario usati dal
            # solutore per trovare una soluzione, tra quelli concessi.
            "overtime_days": result.overtime_days,
        }
    finally:
        db.close()


@app.post("/api/planning/override")
def set_override(payload: schemas.OverrideIn):
    if payload.assignment not in ("giorno", "notte", "riposo"):
        raise HTTPException(400, "Assegnazione non valida")
    db = db_session()
    try:
        row = (
            db.query(models.PlanningOverride)
            .filter_by(year=payload.year, month=payload.month, day=payload.day, employee_id=payload.employee_id)
            .first()
        )
        if row:
            row.assignment = payload.assignment
        else:
            row = models.PlanningOverride(
                year=payload.year, month=payload.month, day=payload.day,
                employee_id=payload.employee_id, assignment=payload.assignment,
            )
            db.add(row)
        db.commit()
        return row.to_dict()
    finally:
        db.close()


@app.get("/api/planning/overrides")
def list_overrides(year: int, month: int):
    """Elenco delle correzioni manuali attualmente salvate per un mese —
    permette alla UI di mostrarle e farle cancellare, cosa che prima non
    era possibile (nessun modo di "disfare" una correzione manuale, che
    quindi restava applicata per sempre a ogni nuova generazione)."""
    db = db_session()
    try:
        rows = (
            db.query(models.PlanningOverride)
            .filter_by(year=year, month=month)
            .all()
        )
        return [o.to_dict() for o in rows]
    finally:
        db.close()


@app.delete("/api/planning/override/{override_id}")
def delete_override(override_id: int):
    db = db_session()
    try:
        row = db.query(models.PlanningOverride).get(override_id)
        if not row:
            raise HTTPException(404, "Correzione non trovata")
        db.delete(row)
        db.commit()
        return {"deleted": override_id}
    finally:
        db.close()


@app.delete("/api/planning/overrides")
def delete_all_overrides(year: int, month: int):
    """Azzera tutte le correzioni manuali salvate per un mese, così che le
    prossime generazioni tornino a rispecchiare esattamente il risultato
    puro del motore (nessuna correzione residua da sessioni precedenti)."""
    db = db_session()
    try:
        db.query(models.PlanningOverride).filter_by(year=year, month=month).delete()
        db.commit()
        return {"deleted_all": True}
    finally:
        db.close()


@app.get("/api/planning/export")
def export_excel(
    year: int, month: int, chef_present: bool = True, lang: str = "IT",
    overtime_employee_ids: str = "", overtime_max_extra: int = 0,
):
    db = db_session()
    try:
        ot_ids = [x for x in overtime_employee_ids.split(",") if x]
        employees, result = _generate_full(
            db, year, month, chef_present,
            overtime_employee_ids=ot_ids, overtime_max_extra=overtime_max_extra,
        )
        xlsx_bytes = build_excel(year, month, result.days, employees, lang=lang,
                                  overtime_days=result.overtime_days)
        filename = f"Planning_{year}_{month:02d}.xlsx"
        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    finally:
        db.close()


# ---------------------------------------------------------------------
# Planning salvati (snapshot "definitivi" per mese, richiamabili in
# sola lettura — es. per controllare il fine mese precedente quando si
# genera quello successivo, senza doverlo rigenerare da capo).
# ---------------------------------------------------------------------

@app.post("/api/planning/save")
def save_planning(payload: schemas.SavePlanningIn):
    db = db_session()
    try:
        existing = (
            db.query(models.SavedPlanning)
            .filter_by(year=payload.year, month=payload.month)
            .first()
        )
        if existing and not payload.confirm_overwrite:
            # Il chiamante deve confermare esplicitamente la sovrascrittura
            # di un mese già salvato in precedenza.
            raise HTTPException(409, "already_saved")

        _, result = _generate_full(
            db, payload.year, payload.month, payload.chef_present,
            overtime_employee_ids=payload.overtime_employee_ids,
            overtime_max_extra=payload.overtime_max_extra,
        )
        num_days = monthrange(payload.year, payload.month)[1]

        row = existing or models.SavedPlanning(year=payload.year, month=payload.month)
        row.num_days = num_days
        row.chef_present = payload.chef_present
        row.days = result.days
        row.targets = result.targets
        row.night_targets = result.night_targets
        row.riposi_dovuti = result.riposi_dovuti
        row.overtime_days = result.overtime_days
        row.saved_at = datetime.now(timezone.utc)
        if not existing:
            db.add(row)

        # Ricalcolo idempotente del "credito" giorni di recupero: cancella e
        # ricrea le righe RecoveryEarned per questo (year, month) da
        # result.overtime_days, così generazioni di prova ripetute prima del
        # salvataggio definitivo non accreditano giorni più volte — solo il
        # salvataggio "conta" ai fini del bilancio.
        db.query(models.RecoveryEarned).filter_by(
            year=payload.year, month=payload.month
        ).delete()
        for eid, days in (result.overtime_days or {}).items():
            for d in days:
                db.add(models.RecoveryEarned(
                    year=payload.year, month=payload.month, day=d, employee_id=eid,
                ))

        # Le correzioni manuali di questo mese sono ormai "congelate" dentro
        # lo snapshot appena salvato (result.days le include già): non
        # servono più come righe separate. Tenerle era esattamente il bug
        # che faceva riapplicare per sempre, ad ogni nuova generazione,
        # correzioni fatte in sessioni passate — anche a distanza di
        # settimane — facendo sforare la quota mensile senza che l'utente
        # avesse toccato nulla di recente. Da qui in poi, dopo un
        # salvataggio riuscito, una nuova generazione dello stesso mese
        # riparte pulita dal solo motore.
        db.query(models.PlanningOverride).filter_by(
            year=payload.year, month=payload.month
        ).delete()

        db.commit()
        db.refresh(row)
        return row.to_dict()
    finally:
        db.close()


@app.get("/api/planning/saved")
def list_saved_plannings():
    db = db_session()
    try:
        rows = (
            db.query(models.SavedPlanning)
            .order_by(models.SavedPlanning.year.desc(), models.SavedPlanning.month.desc())
            .all()
        )
        return [r.to_dict(include_days=False) for r in rows]
    finally:
        db.close()


@app.get("/api/planning/saved/{year}/{month}")
def get_saved_planning(year: int, month: int):
    db = db_session()
    try:
        row = (
            db.query(models.SavedPlanning)
            .filter_by(year=year, month=month)
            .first()
        )
        if not row:
            raise HTTPException(404, "Nessun planning salvato per questo mese")
        return row.to_dict(include_days=True)
    finally:
        db.close()


# Serve il frontend statico (index.html, style.css, app.js)
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

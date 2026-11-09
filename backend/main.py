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
from .engine import ASSIGNABLE_TYPES, ShiftEngine, holiday_groups_from_december
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
    # v25.8: ogni sostituzione su un planning salvato matura un recupero.
    earned += db.query(models.PlanningVariation).filter_by(
        employee_id=employee_id, kind="sostituzione").count()
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
        # v25.8: ogni sostituzione su un planning salvato matura un recupero.
        subst_rows = (
            db.query(models.PlanningVariation.employee_id, func.count(models.PlanningVariation.id))
            .filter(models.PlanningVariation.kind == "sostituzione")
            .group_by(models.PlanningVariation.employee_id)
            .all()
        )
        for eid, n in subst_rows:
            earned_map[eid] = earned_map.get(eid, 0) + n
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


def _load_holiday_history(db: Session, before_year: int) -> dict:
    """{employee_id: {"natale": [anni], "capodanno": [anni]}} per gli anni
    precedenti a `before_year` — input della rotazione delle feste."""
    history: dict = {}
    rows = db.query(models.HolidayHistory).filter(models.HolidayHistory.year < before_year).all()
    for r in rows:
        history.setdefault(r.employee_id, {}).setdefault(r.holiday, []).append(r.year)
    return history


def _load_saved_days(db: Session, year: int, month: int) -> dict | None:
    """Giorni EFFETTIVI di un mese salvato (snapshot + variazioni v25.8):
    li usano gennaio (1° gennaio dopo il dicembre salvato) e i controlli di
    continuità, che devono vedere chi ha lavorato davvero."""
    row = db.query(models.SavedPlanning).filter_by(year=year, month=month).first()
    return _effective_saved(db, row)["days"] if row else None


# ---------------------------------------------------------------------
# Variazioni su un planning salvato (v25.8). Il motore NON viene mai
# rilanciato: lo snapshot resta com'è e le variazioni (assenze e
# sostituzioni inserite a mano) vengono sovrapposte quando lo si legge.
# ---------------------------------------------------------------------

ABSENCE_TYPES = ("malattia", "ferie")
WORK_SHIFTS = ("giorno", "notte")
# v25.9: esterno dell'agenzia Boss. Non è un dipendente: nei giorni del
# planning compare con l'id speciale "BOSS:<id dell'assente>" (uno per
# turno coperto), fuori da quote, riepiloghi, recuperi e storico feste.
BOSS_PREFIX = "BOSS:"
COVERING_KINDS = ("sostituzione", "esterno")


def _slot_of(rd: dict, eid: str) -> str | None:
    """Dove sta `eid` in un giorno: giorno/notte/riposo/ferie/malattia/chef."""
    for k in ("giorno", "notte", "riposo", "ferie", "malattia"):
        if eid in (rd.get(k) or []):
            return k
    if rd.get("chef") == eid:
        return "chef"
    return None


def _month_variations(db: Session, year: int, month: int) -> list:
    return (
        db.query(models.PlanningVariation)
        .filter_by(year=year, month=month)
        .order_by(models.PlanningVariation.day, models.PlanningVariation.id)
        .all()
    )


def _effective_saved(db: Session, row) -> dict:
    """Snapshot salvato + variazioni. Restituisce la stessa struttura di
    SavedPlanning.to_dict() (così la UI la disegna come sempre), più:
    - variations: elenco delle variazioni del mese;
    - uncovered: turni rimasti scoperti per un'assenza [{day, shift, employee_id}].
    Quote del riepilogo: un'assenza su un giorno di lavoro abbassa la quota
    di lavoro, su un giorno di riposo quella di riposo; una sostituzione
    conta come giorno di straordinario (overtime_days), quindi il
    riepilogo resta in linea."""
    data = row.to_dict(include_days=True)
    days = {str(k): {kk: (list(vv) if isinstance(vv, list) else vv) for kk, vv in v.items()}
            for k, v in (data["days"] or {}).items()}
    targets = dict(data["targets"] or {})
    rest_due = dict(data["riposi_dovuti"] or {})
    overtime = {k: list(v) for k, v in (data["overtime_days"] or {}).items()}

    variations = _month_variations(db, row.year, row.month)
    covered = set()
    for v in variations:
        if v.kind in COVERING_KINDS:
            covered.add((v.day, v.replaces_id))

    uncovered = []
    for v in sorted(variations, key=lambda x: 0 if x.kind == "assenza" else 1):
        rd = days.get(str(v.day))
        if rd is None:
            continue
        eid = v.employee_id
        for k in ("giorno", "notte", "riposo"):
            if eid in rd.get(k, []):
                rd[k].remove(eid)
        if v.kind == "assenza":
            if rd.get("chef") == eid:
                rd["chef"] = None
            rd.setdefault(v.absence_type, []).append(eid)
            if v.shift in WORK_SHIFTS:
                if eid in targets:
                    targets[eid] -= 1
                if (v.day, eid) not in covered:
                    uncovered.append({"day": v.day, "shift": v.shift, "employee_id": eid})
            elif v.shift == "riposo" and eid in rest_due:
                rest_due[eid] -= 1
        elif v.kind == "esterno":  # v25.9: Boss, nessuno straordinario
            rd.setdefault(v.shift, []).append(eid)
        else:  # sostituzione
            rd.setdefault(v.shift, []).append(eid)
            overtime.setdefault(eid, [])
            if v.day not in overtime[eid]:
                overtime[eid].append(v.day)

    data.update({
        "days": days,
        "targets": targets,
        "riposi_dovuti": rest_due,
        "overtime_days": overtime,
        "variations": [v.to_dict() for v in variations],
        "uncovered": uncovered,
    })
    return data


def _saved_row_or_404(db: Session, year: int, month: int):
    row = db.query(models.SavedPlanning).filter_by(year=year, month=month).first()
    if not row:
        raise HTTPException(404, "not_saved")
    return row


def _after_variation_change(db: Session, row) -> dict:
    """Dopo ogni variazione: aggiorna lo storico Natale/Capodanno (se è
    dicembre o gennaio) con i giorni effettivi e restituisce il planning."""
    eff = _effective_saved(db, row)
    _record_holidays(db, row.year, row.month, eff["days"])
    db.commit()
    return _effective_saved(db, row)


@app.get("/api/planning/variations")
def list_variations(year: int, month: int):
    db = db_session()
    try:
        return [v.to_dict() for v in _month_variations(db, year, month)]
    finally:
        db.close()


@app.post("/api/planning/variations/absence")
def add_absence_variation(payload: schemas.AbsenceVariationIn):
    if payload.absence_type not in ABSENCE_TYPES:
        raise HTTPException(400, "Tipo di assenza non valido")
    if payload.day_to < payload.day_from:
        raise HTTPException(400, "day_order")
    db = db_session()
    try:
        row = _saved_row_or_404(db, payload.year, payload.month)
        if payload.day_to > row.num_days:
            raise HTTPException(400, "day_out_of_month")
        emp = db.query(models.Employee).get(payload.employee_id)
        if not emp:
            raise HTTPException(404, "Dipendente non trovato")

        existing = {(v.day, v.employee_id): v for v in _month_variations(db, row.year, row.month)}
        snapshot = row.days or {}
        added = 0
        for d in range(payload.day_from, payload.day_to + 1):
            v = existing.get((d, payload.employee_id))
            if v and v.kind == "sostituzione":
                # Prima va annullata la sostituzione che fa quel giorno.
                raise HTTPException(409, {"error": "is_substitute", "day": d})
            if v:  # già assente quel giorno: aggiorna solo il tipo
                v.absence_type = payload.absence_type
                continue
            rd = snapshot.get(str(d)) or snapshot.get(d) or {}
            slot = _slot_of(rd, payload.employee_id)
            if slot in ("ferie", "malattia") or slot is None:
                continue  # già assente nello snapshot (o non in squadra)
            db.add(models.PlanningVariation(
                year=row.year, month=row.month, day=d, kind="assenza",
                employee_id=payload.employee_id, absence_type=payload.absence_type,
                shift=slot,
            ))
            added += 1
        db.flush()
        result = _after_variation_change(db, row)
        result["added"] = added
        return result
    finally:
        db.close()


@app.post("/api/planning/variations/substitute")
def add_substitution(payload: schemas.SubstitutionIn):
    db = db_session()
    try:
        row = _saved_row_or_404(db, payload.year, payload.month)
        variations = _month_variations(db, row.year, row.month)
        absence = next((v for v in variations if v.kind == "assenza" and v.day == payload.day
                        and v.employee_id == payload.replaces_id and v.shift in WORK_SHIFTS), None)
        already = any(v.kind == "sostituzione" and v.day == payload.day
                      and v.replaces_id == payload.replaces_id for v in variations)
        if not absence or already:
            raise HTTPException(409, "not_uncovered")
        # v25.9: se il turno è coperto da un esterno Boss, il collega lo
        # rimpiazza (l'esterno viene tolto nella stessa operazione).
        boss = next((v for v in variations if v.kind == "esterno" and v.day == payload.day
                     and v.replaces_id == payload.replaces_id), None)
        eff = _effective_saved(db, row)
        rd = eff["days"].get(str(payload.day)) or {}
        if _slot_of(rd, payload.employee_id) != "riposo":
            raise HTTPException(409, "not_resting")
        if boss:
            db.delete(boss)
            db.flush()
        db.add(models.PlanningVariation(
            year=row.year, month=row.month, day=payload.day, kind="sostituzione",
            employee_id=payload.employee_id, shift=absence.shift,
            replaces_id=payload.replaces_id,
        ))
        db.flush()
        return _after_variation_change(db, row)
    finally:
        db.close()


@app.post("/api/planning/variations/external")
def add_external(payload: schemas.ExternalIn):
    """v25.9: un esterno dell'agenzia Boss copre il turno di un assente.
    Scelto solo a mano; il motore non lo usa mai."""
    db = db_session()
    try:
        row = _saved_row_or_404(db, payload.year, payload.month)
        variations = _month_variations(db, row.year, row.month)
        absence = next((v for v in variations if v.kind == "assenza" and v.day == payload.day
                        and v.employee_id == payload.replaces_id and v.shift in WORK_SHIFTS), None)
        already = any(v.kind in COVERING_KINDS and v.day == payload.day
                      and v.replaces_id == payload.replaces_id for v in variations)
        if not absence or already:
            raise HTTPException(409, "not_uncovered")
        db.add(models.PlanningVariation(
            year=row.year, month=row.month, day=payload.day, kind="esterno",
            employee_id=BOSS_PREFIX + payload.replaces_id, shift=absence.shift,
            replaces_id=payload.replaces_id,
        ))
        db.flush()
        return _after_variation_change(db, row)
    finally:
        db.close()


@app.delete("/api/planning/variations/{variation_id}")
def delete_variation(variation_id: int):
    """Annulla una variazione. Annullare un'assenza annulla anche la
    sostituzione collegata (il collega torna di riposo)."""
    db = db_session()
    try:
        v = db.query(models.PlanningVariation).get(variation_id)
        if not v:
            raise HTTPException(404, "Variazione non trovata")
        row = _saved_row_or_404(db, v.year, v.month)
        if v.kind == "assenza":
            db.query(models.PlanningVariation).filter(
                models.PlanningVariation.year == v.year, models.PlanningVariation.month == v.month,
                models.PlanningVariation.day == v.day, models.PlanningVariation.replaces_id == v.employee_id,
                models.PlanningVariation.kind.in_(COVERING_KINDS),
            ).delete(synchronize_session=False)
        db.delete(v)
        db.flush()
        return _after_variation_change(db, row)
    finally:
        db.close()


@app.get("/api/planning/saved/{year}/{month}/export")
def export_saved_excel(year: int, month: int, lang: str = "IT"):
    """Excel di un planning salvato, variazioni comprese (le sostituzioni
    in verde come lo straordinario). Non rilancia il motore."""
    db = db_session()
    try:
        row = _saved_row_or_404(db, year, month)
        eff = _effective_saved(db, row)
        days_int = {int(k): v for k, v in eff["days"].items()}
        xlsx_bytes = build_excel(year, month, days_int, _load_employees(db), lang=lang,
                                 overtime_days=eff["overtime_days"])
        filename = f"Planning_{year}_{month:02d}.xlsx"
        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    finally:
        db.close()


def _record_holidays(db: Session, year: int, month: int, days: dict):
    """Dopo il salvataggio di dicembre o gennaio, aggiorna lo storico delle
    feste (v25.4). Idempotente: ricrea solo le righe automatiche di quel
    salvataggio; le righe inserite a mano restano come sono."""
    if month == 12:
        holiday_year, source = year, "auto_dic"
        groups = holiday_groups_from_december(days)
        entries = [(eid, "natale") for eid in groups["natale"]]
        entries += [(eid, "capodanno") for eid in groups["day31"] | groups["night31"]]
    elif month == 1:
        holiday_year, source = year - 1, "auto_gen"
        jan1 = days.get(1) or days.get("1") or {}
        entries = [(eid, "capodanno") for eid in jan1.get("giorno", [])]
    else:
        return

    entries = [(eid, h) for eid, h in entries if not str(eid).startswith(BOSS_PREFIX)]  # v25.9
    db.query(models.HolidayHistory).filter_by(year=holiday_year, source=source).delete()
    db.flush()
    for eid, holiday in entries:
        exists = db.query(models.HolidayHistory).filter_by(
            year=holiday_year, employee_id=eid, holiday=holiday
        ).first()
        if not exists:
            db.add(models.HolidayHistory(year=holiday_year, employee_id=eid, holiday=holiday, source=source))


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
        holiday_history=_load_holiday_history(db, before_year=year) if month == 12 else None,
        prev_december=_load_saved_days(db, year - 1, 12) if month == 1 else None,
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
        if existing and db.query(models.PlanningVariation).filter_by(
                year=payload.year, month=payload.month).count() > 0:
            # v25.8: risalvare rigenera il mese col motore e le variazioni
            # non corrisponderebbero più. Vanno annullate prima.
            raise HTTPException(409, "has_variations")

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

        _record_holidays(db, payload.year, payload.month, result.days)

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
        return _effective_saved(db, row)  # snapshot + variazioni (v25.8)
    finally:
        db.close()


# ---------------------------------------------------------------------
# Storico Natale/Capodanno (v25.4) — per la rotazione delle feste
# ---------------------------------------------------------------------

HOLIDAYS = ("natale", "capodanno")


@app.get("/api/holidays/history")
def list_holiday_history():
    db = db_session()
    try:
        rows = db.query(models.HolidayHistory).order_by(models.HolidayHistory.year.desc()).all()
        return [r.to_dict() for r in rows]
    finally:
        db.close()


@app.post("/api/holidays/history")
def add_holiday_history(payload: schemas.HolidayHistoryIn):
    if payload.holiday not in HOLIDAYS:
        raise HTTPException(400, "Festa non valida")
    db = db_session()
    try:
        if not db.query(models.Employee).get(payload.employee_id):
            raise HTTPException(404, "Dipendente non trovato")
        row = db.query(models.HolidayHistory).filter_by(
            year=payload.year, employee_id=payload.employee_id, holiday=payload.holiday
        ).first()
        if row:
            return row.to_dict()  # già presente: niente doppioni
        row = models.HolidayHistory(year=payload.year, employee_id=payload.employee_id,
                                    holiday=payload.holiday, source="manuale")
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.to_dict()
    finally:
        db.close()


@app.delete("/api/holidays/history/{entry_id}")
def delete_holiday_history(entry_id: int):
    db = db_session()
    try:
        row = db.query(models.HolidayHistory).get(entry_id)
        if not row:
            raise HTTPException(404, "Voce non trovata")
        db.delete(row)
        db.commit()
        return {"deleted": entry_id}
    finally:
        db.close()


# Serve il frontend statico (index.html, style.css, app.js)
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

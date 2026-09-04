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

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
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

@app.get("/api/employees")
def list_employees():
    db = db_session()
    try:
        rows = db.query(models.Employee).all()
        return [e.to_dict() for e in rows]
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


@app.post("/api/constraints")
def add_constraint_range(payload: schemas.ConstraintIn):
    if payload.type not in ASSIGNABLE_TYPES:
        raise HTTPException(400, f"Tipo non valido: {payload.type}")
    if payload.day_from > payload.day_to:
        raise HTTPException(400, "Il giorno di inizio deve precedere quello di fine")

    db = db_session()
    try:
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
    return [e.to_dict() for e in db.query(models.Employee).all()]


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


@app.post("/api/planning/generate")
def generate_planning(payload: schemas.GenerateIn):
    db = db_session()
    try:
        employees = _load_employees(db)
        constraints = _load_constraints_map(db, payload.year, payload.month)
        engine = ShiftEngine(employees, payload.year, payload.month, constraints, payload.chef_present)
        result = engine.generate()
        if not result.ok:
            raise HTTPException(409, result.error or "no_solution")

        overrides = _load_overrides_map(db, payload.year, payload.month)
        _apply_overrides(result.days, overrides)

        return {
            "year": payload.year,
            "month": payload.month,
            "num_days": monthrange(payload.year, payload.month)[1],
            "days": result.days,
            "targets": result.targets,
            "night_targets": result.night_targets,
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


@app.get("/api/planning/export")
def export_excel(year: int, month: int, chef_present: bool = True, lang: str = "IT"):
    db = db_session()
    try:
        employees = _load_employees(db)
        constraints = _load_constraints_map(db, year, month)
        engine = ShiftEngine(employees, year, month, constraints, chef_present)
        result = engine.generate()
        if not result.ok:
            raise HTTPException(409, result.error or "no_solution")

        overrides = _load_overrides_map(db, year, month)
        _apply_overrides(result.days, overrides)

        xlsx_bytes = build_excel(year, month, result.days, employees, lang=lang)
        filename = f"Planning_{year}_{month:02d}.xlsx"
        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    finally:
        db.close()


# Serve il frontend statico (index.html, style.css, app.js)
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

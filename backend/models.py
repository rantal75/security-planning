"""
models.py — Tabelle del database.

Rispetto alla v24.85:
  - Employee guadagna un campo `custom_weight` opzionale: il peso gerarchico
    (Sez. 6) resta calcolato per cognome come prima (compatibilità piena con
    l'elenco esistente), ma ora può anche essere impostato manualmente per
    ogni dipendente senza dover toccare il codice.
  - ManualConstraint è ora ancorato a (year, month, day, employee_id) invece
    che al solo giorno: corregge il bug per cui un vincolo restava attivo per
    sempre, indipendentemente dal mese generato.
  - PlanningOverride è nuovo: la "Correzione Manuale" post-generazione
    (spostare un nome da una colonna all'altra) ora viene salvata nel
    database invece che solo in memoria — nella versione originale bastava
    ricaricare la pagina per perdere tutte le correzioni fatte.
"""

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from .database import Base


class Employee(Base):
    __tablename__ = "employees"

    id = Column(String, primary_key=True)  # es. "ROMEO_MARCO"
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)

    pref_night = Column(Boolean, default=False)
    pref_day = Column(Boolean, default=False)
    pref_33 = Column(Boolean, default=False)

    is_titular = Column(Boolean, default=False)
    is_adjoint = Column(Boolean, default=False)
    is_equipe = Column(Boolean, default=False)
    is_temp = Column(Boolean, default=False)

    custom_weight = Column(Integer, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "pref_night": self.pref_night,
            "pref_day": self.pref_day,
            "pref_33": self.pref_33,
            "is_titular": self.is_titular,
            "is_adjoint": self.is_adjoint,
            "is_equipe": self.is_equipe,
            "is_temp": self.is_temp,
            "custom_weight": self.custom_weight,
        }


class ManualConstraint(Base):
    __tablename__ = "manual_constraints"
    __table_args__ = (UniqueConstraint("year", "month", "day", "employee_id", name="uq_constraint_slot"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    day = Column(Integer, nullable=False)
    employee_id = Column(String, ForeignKey("employees.id"), nullable=False)
    type = Column(String, nullable=False)  # giorno/notte/riposo/ferie/malattia/chef2

    employee = relationship("Employee")

    def to_dict(self):
        return {
            "id": self.id,
            "year": self.year,
            "month": self.month,
            "day": self.day,
            "employee_id": self.employee_id,
            "type": self.type,
        }


class PlanningOverride(Base):
    """Correzione manuale applicata SOPRA il risultato calcolato dal motore
    per un dato giorno/dipendente (es. spostare qualcuno da Riposo a Notte
    dopo la generazione automatica)."""
    __tablename__ = "planning_overrides"
    __table_args__ = (UniqueConstraint("year", "month", "day", "employee_id", name="uq_override_slot"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    day = Column(Integer, nullable=False)
    employee_id = Column(String, ForeignKey("employees.id"), nullable=False)
    assignment = Column(String, nullable=False)  # giorno/notte/riposo

    def to_dict(self):
        return {
            "id": self.id,
            "year": self.year,
            "month": self.month,
            "day": self.day,
            "employee_id": self.employee_id,
            "assignment": self.assignment,
        }

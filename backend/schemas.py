"""schemas.py — Schemi Pydantic per l'API (validazione input/output)."""

from typing import Optional

from pydantic import BaseModel, Field

# NOTA (2026-09-25): campi "overtime_*" — selezione ad-hoc, valida per una
# sola generazione/salvataggio, dei dipendenti disponibili per lo
# straordinario e del numero massimo di giorni extra concessi. Non è un
# attributo fisso del dipendente (scelta B, confermata dall'utente):
# l'elenco va passato esplicitamente ad ogni chiamata che deve tenerne
# conto (generate/export/save).


class EmployeeIn(BaseModel):
    first_name: str
    last_name: str
    pref_night: bool = False
    pref_day: bool = False
    pref_33: bool = False
    is_titular: bool = False
    is_adjoint: bool = False
    is_equipe: bool = False
    is_temp: bool = False
    custom_weight: Optional[int] = None


class EmployeeOut(EmployeeIn):
    id: str


class ConstraintIn(BaseModel):
    year: int
    month: int = Field(ge=1, le=12)
    day_from: int = Field(ge=1, le=31)
    day_to: int = Field(ge=1, le=31)
    employee_id: str
    type: str  # giorno/notte/riposo/ferie/malattia/chef2/recupero


class OverrideIn(BaseModel):
    year: int
    month: int = Field(ge=1, le=12)
    day: int = Field(ge=1, le=31)
    employee_id: str
    assignment: str  # giorno/notte/riposo


class GenerateIn(BaseModel):
    year: int
    month: int = Field(ge=1, le=12)
    chef_present: bool = True
    overtime_employee_ids: list[str] = Field(default_factory=list)
    overtime_max_extra: int = 0


class SavePlanningIn(BaseModel):
    year: int
    month: int = Field(ge=1, le=12)
    chef_present: bool = True
    overtime_employee_ids: list[str] = Field(default_factory=list)
    overtime_max_extra: int = 0
    # Se il mese è già stato salvato in precedenza, l'API rifiuta con 409
    # "already_saved" a meno che questo non sia True: la UI lo usa per
    # chiedere conferma prima di sovrascrivere uno snapshot esistente.
    confirm_overwrite: bool = False

"""schemas.py — Schemi Pydantic per l'API (validazione input/output)."""

from typing import Optional

from pydantic import BaseModel, Field


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
    type: str  # giorno/notte/riposo/ferie/malattia/chef2


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

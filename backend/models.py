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

MODIFICA (2026-09-24): aggiunta SavedPlanning — snapshot "definitivo" del
planning per un dato mese (motore + correzioni manuali già applicate),
salvato esplicitamente dall'utente dopo la revisione. Serve per poter
richiamare in sola lettura i planning dei mesi passati (es. per controllare
il fine mese precedente quando si genera quello successivo) senza doverli
rigenerare, e senza rischiare di confondere lo storico con il planning su
cui si sta ancora lavorando. Uno slot per (year, month): salvare di nuovo
lo stesso mese sovrascrive lo snapshot precedente (previa conferma lato UI).

MODIFICA (2026-09-25): aggiunta RecoveryEarned — il "credito" (lato
entrata) del bilancio giorni di recupero, un record per ogni giorno di
straordinario effettivamente lavorato da un dipendente (vedi engine.py,
meccanismo "straordinario"). Il "debito" (lato uscita, quando il
dipendente si riprende un giorno di recupero) NON ha una tabella propria:
riusa ManualConstraint con type="recupero", esattamente come già avviene
per ferie/malattia/riposo — evita di duplicare la logica di
inserimento/cancellazione vincoli già esistente. Il bilancio è quindi
sempre "earned - spent", calcolato al volo (main.py), cumulativo su tutti
i mesi (un giorno maturato in un mese può essere speso il mese successivo
o in quello corrente, come richiesto). SavedPlanning guadagna la colonna
`overtime_days`, lo snapshot congelato di quali giorni sono stati di
straordinario per ciascun dipendente in quel mese (serve per la
colorazione in blu quando si visualizza/esporta un mese già salvato).
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
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
    type = Column(String, nullable=False)  # giorno/notte/riposo/ferie/malattia/chef2/recupero

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


class RecoveryEarned(Base):
    """Un giorno di straordinario effettivamente lavorato da un dipendente
    (vedi engine.py) = un credito nel bilancio "giorni da recuperare". Riga
    per riga, così il bilancio è sempre ricostruibile come conteggio. Le
    righe vengono ricalcolate in modo idempotente ad ogni salvataggio
    planning per (year, month) — si cancellano e si ricreano da
    EngineResult.overtime_days — per evitare doppi accrediti da generazioni
    di prova ripetute prima del salvataggio definitivo."""
    __tablename__ = "recovery_earned"
    __table_args__ = (UniqueConstraint("year", "month", "day", "employee_id", name="uq_recovery_slot"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    day = Column(Integer, nullable=False)
    employee_id = Column(String, ForeignKey("employees.id"), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "year": self.year,
            "month": self.month,
            "day": self.day,
            "employee_id": self.employee_id,
        }


class SavedPlanning(Base):
    """Snapshot "definitivo" del planning per un mese (motore + correzioni
    manuali già applicate), salvato esplicitamente dall'utente dopo la
    revisione. Uno slot per (year, month): un nuovo salvataggio sullo
    stesso mese sovrascrive lo snapshot precedente (la conferma della
    sovrascrittura è gestita lato API/UI, non qui)."""
    __tablename__ = "saved_plannings"
    __table_args__ = (UniqueConstraint("year", "month", name="uq_saved_planning_month"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    num_days = Column(Integer, nullable=False)
    chef_present = Column(Boolean, default=True)

    # Stesse strutture dati restituite da /api/planning/generate, congelate
    # al momento del salvataggio.
    days = Column(JSON, nullable=False)
    targets = Column(JSON, nullable=False)
    night_targets = Column(JSON, nullable=False)
    riposi_dovuti = Column(JSON, nullable=False)
    # {employee_id: [giorni]} — congelato al salvataggio, vedi engine.py.
    overtime_days = Column(JSON, nullable=True)

    saved_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self, include_days: bool = True):
        base = {
            "year": self.year,
            "month": self.month,
            "num_days": self.num_days,
            "chef_present": self.chef_present,
            "saved_at": self.saved_at.isoformat() if self.saved_at else None,
        }
        if include_days:
            base.update({
                "days": self.days,
                "targets": self.targets,
                "night_targets": self.night_targets,
                "riposi_dovuti": self.riposi_dovuti,
                "overtime_days": self.overtime_days or {},
            })
        return base

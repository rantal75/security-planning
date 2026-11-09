"""
database.py — Connessione al database.

Sostituisce il file JSON (db_personnel.json) della versione originale con un
vero database SQLite: stesso livello di semplicità (un unico file, zero
configurazione, nessun server da installare), ma con transazioni reali che
evitano corruzioni/perdite di dati. Se in futuro serve un uso multi-sito, è
sufficiente cambiare DATABASE_URL per puntare a Postgres: il resto del codice
(modelli SQLAlchemy) non cambia.

MODIFICA (2026-09-25): aggiunta una migrazione leggera in init_db(). Prima,
Base.metadata.create_all() creava solo le TABELLE che ancora non esistevano
nel file planning.db — ma se una tabella esisteva già (creata da una
versione precedente del codice) e nel frattempo un modello guadagnava una
nuova colonna (es. SavedPlanning.overtime_days, aggiunta il 2026-09-24),
create_all() non aggiungeva quella colonna al file .db esistente sul disco
dell'utente: il programma partiva senza errori, ma qualsiasi query su quella
tabella falliva con "sqlite3.OperationalError: no such column" al primo uso
reale (es. GET /api/planning/saved). _migrate_add_missing_columns() confronta
ora, ad ogni avvio, le colonne che ciascun modello si aspetta con quelle
realmente presenti nel file .db, e aggiunge con ALTER TABLE quelle mancanti
— senza toccare le tabelle né le righe già esistenti, quindi senza perdita di
dati salvati.
"""

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./planning.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from . import models  # noqa: F401  (registra i modelli su Base)
    Base.metadata.create_all(bind=engine)
    _migrate_add_missing_columns()


def _migrate_add_missing_columns():
    """Per ogni tabella già esistente nel file .db, aggiunge con ALTER
    TABLE le colonne presenti nel modello SQLAlchemy ma assenti sul disco.
    Le tabelle nuove non passano di qui: create_all() le ha già create per
    intero, comprese tutte le loro colonne. Pensata per essere a prova di
    errore: un problema su UNA colonna viene segnalato in console ma non
    blocca l'avvio dell'app né le colonne/tabelle successive."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        existing_cols = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing_cols:
                continue
            col_type = column.type.compile(dialect=engine.dialect)
            ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}'
            try:
                with engine.begin() as conn:
                    conn.execute(text(ddl))
                print(f"[migrazione db] aggiunta colonna mancante: {table.name}.{column.name}")
            except Exception as exc:  # pragma: no cover — non deve bloccare l'avvio
                print(f"[migrazione db] impossibile aggiungere {table.name}.{column.name}: {exc}")

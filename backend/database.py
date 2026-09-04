"""
database.py — Connessione al database.

Sostituisce il file JSON (db_personnel.json) della versione originale con un
vero database SQLite: stesso livello di semplicità (un unico file, zero
configurazione, nessun server da installare), ma con transazioni reali che
evitano corruzioni/perdite di dati. Se in futuro serve un uso multi-sito, è
sufficiente cambiare DATABASE_URL per puntare a Postgres: il resto del codice
(modelli SQLAlchemy) non cambia.
"""

from sqlalchemy import create_engine
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

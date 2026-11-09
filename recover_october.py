"""recover_october.py — Script una tantum per recuperare il planning di
ottobre 2026, rimasto "intrappolato" nella vecchia tabella `generated_shifts`
(residuo della versione precedente dell'app, non più letta dal codice
attuale) e mai migrato alla tabella `saved_plannings` che l'app legge oggi.

USO:
  1. Chiudi il backend (Ctrl+C nella finestra dove gira `uvicorn`), per
     evitare scritture concorrenti sullo stesso file planning.db.
  2. Apri un terminale nella cartella del progetto (security-planning),
     con il virtualenv attivo (stessa procedura di "avvio script.txt"):
         cd security-planning
         .venv\\Scripts\\activate
  3. Copia questo file nella cartella del progetto (accanto a planning.db,
     cioè nella cartella "security-planning", NON dentro "backend") e
     eseguilo:
         python recover_october.py
  4. Riavvia il backend come al solito.

Lo script:
  - Se esiste un file "planning.db-journal" orfano (lasciato da un
    tentativo di scrittura precedente non andato a buon fine), lo lascia
    gestire a SQLite stesso all'apertura della connessione (rollback
    automatico e sicuro) — non lo tocca manualmente.
  - Controlla che non esista già una riga salvata per ottobre 2026 (se
    esiste, si ferma senza toccare nulla).
  - Legge tutti i turni di ottobre 2026 dalla vecchia tabella
    generated_shifts e li converte nel formato usato oggi da
    saved_plannings.days.
  - Inserisce una nuova riga in saved_plannings per (2026, 10).

Non cancella né modifica nessun'altra riga o tabella.
"""

import json
import sqlite3
import sys
from datetime import datetime, timezone

DB_PATH = "planning.db"
YEAR, MONTH = 2026, 10
NUM_DAYS = 31


def main():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("SELECT COUNT(*) FROM saved_plannings WHERE year=? AND month=?", (YEAR, MONTH))
    if cur.fetchone()[0] > 0:
        print(f"Esiste già un planning salvato per {MONTH}/{YEAR}. Non faccio nulla.")
        return

    cur.execute(
        "SELECT day, employee_id, shift FROM generated_shifts WHERE year=? AND month=? ORDER BY day",
        (YEAR, MONTH),
    )
    rows = cur.fetchall()
    if not rows:
        print(f"Nessun dato trovato in generated_shifts per {MONTH}/{YEAR}. Non c'è nulla da recuperare.")
        return

    days = {
        str(d): {"giorno": [], "notte": [], "riposo": [], "ferie": [], "malattia": [], "chef": None}
        for d in range(1, NUM_DAYS + 1)
    }

    unknown_types = set()
    for day, eid, shift in rows:
        key = str(day)
        if key not in days:
            continue
        if shift == "chef":
            days[key]["chef"] = eid
        elif shift in ("giorno", "notte", "riposo", "ferie", "malattia"):
            days[key][shift].append(eid)
        else:
            unknown_types.add(shift)

    if unknown_types:
        print("ATTENZIONE — tipi di turno non riconosciuti, ignorati:", unknown_types)

    now = datetime.now(timezone.utc).isoformat(sep=" ", timespec="microseconds")

    cur.execute(
        """INSERT INTO saved_plannings
           (year, month, num_days, chef_present, days, targets, night_targets,
            riposi_dovuti, saved_at, overtime_days, boss_days)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            YEAR, MONTH, NUM_DAYS, 1,
            json.dumps(days), json.dumps({}), json.dumps({}), json.dumps({}),
            now, json.dumps({}), json.dumps({}),
        ),
    )
    con.commit()
    print(f"Fatto: planning di {MONTH}/{YEAR} recuperato e salvato (id={cur.lastrowid}).")

    cur.execute("SELECT id, year, month, num_days, saved_at FROM saved_plannings ORDER BY year, month")
    print("\nPlanning salvati ora presenti:")
    for r in cur.fetchall():
        print(" ", r)

    con.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nERRORE: {e}", file=sys.stderr)
        print(
            "Il database potrebbe avere un file 'planning.db-journal' rimasto da un "
            "tentativo precedente non riuscito. Prova a chiudere completamente il "
            "backend (e qualsiasi altro programma che tenga aperto planning.db), "
            "poi riesegui questo script.",
            file=sys.stderr,
        )
        sys.exit(1)

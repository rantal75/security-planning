# Gestione Sicurezza — Planning Turni (riscrittura)

Riscrittura completa della v24.85 (Colab + ipywidgets). Stessa logica di
fondo (Python + Google OR-Tools CP-SAT per il calcolo), ma riorganizzata in
un'applicazione vera: **backend FastAPI** + **database SQLite** + **frontend
web** al posto del notebook Colab.

## Versione

Il salto da v24.x a **v25.x** segna il cambio di architettura (Colab →
FastAPI/SQLite/web); da qui in avanti la numerazione continua in modo
progressivo a ogni modifica. Versione corrente visibile anche nell'interfaccia
(badge accanto al titolo, in alto a sinistra).

| Versione | Data | Cosa è cambiato |
|----------|------|------------------|
| v25.0 | 2026-09-04 | Prima consegna della nuova architettura: riscrittura completa da Colab/ipywidgets a FastAPI + SQLite + frontend web (vedi sezione "Cosa è cambiato rispetto alla v24.85" più sotto). |
| v25.1 | 2026-09-04 | Sostituite tutte le emoji dell'interfaccia (☀️🌙👑🥈🥉⏳🛡️📥🖨️🛠️⚠️ ecc.) con un set di icone SVG disegnate su misura, in stile "console operativa". Palette e font invariati. |
| v25.2 | 2026-09-05 | Corretta la visualizzazione delle icone: su alcuni browser risultavano enormi e spingevano fuori pagina la lista dipendenti. Aggiunte dimensioni esplicite alle icone SVG e reso più robusto il layout a "pillola" (chip) delle preferenze, con andare a capo automatico per una migliore visualizzazione anche su tablet. |

## Struttura

```
security-planning/
├── backend/
│   ├── engine.py         # Motore di calcolo (CP-SAT) — la parte più importante
│   ├── models.py         # Tabelle del database (dipendenti, vincoli, correzioni)
│   ├── database.py       # Connessione SQLite
│   ├── schemas.py        # Validazione input/output dell'API
│   ├── excel_export.py   # Generazione del file .xlsx
│   └── main.py           # API FastAPI (le rotte /api/...)
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js            # Chiama l'API e disegna l'interfaccia — nessuna
│                          # regola di business qui
├── requirements.txt
└── README.md
```

## Avvio (in locale, sul tuo computer)

Serve Python 3.11+ e una connessione internet per installare le dipendenze
(qui non ho potuto testare l'esecuzione reale perché l'ambiente in cui ho
scritto il codice non ha accesso alla rete — vedi nota in fondo).

```bash
cd security-planning
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Poi apri il browser su **http://127.0.0.1:8000/**. Il database
(`planning.db`) viene creato automaticamente al primo avvio, nella stessa
cartella.

Per uso "locale singolo" è già così, di fatto un'app desktop mascherata da
pagina web. Se in futuro vuoi renderla raggiungibile da altri computer
dell'ufficio, basta lanciarla su un piccolo server (anche un Raspberry Pi o
un vecchio PC) e aprirla dal browser degli altri postazioni sulla rete
locale — nessuna riscrittura necessaria.

## Cosa è cambiato rispetto alla v24.85

### Bug corretti
- **Vincoli manuali "eterni"**: nella versione originale un vincolo (ferie,
  riposo forzato...) era identificato solo dal numero del giorno, quindi
  restava attivo per sempre, anche generando un mese diverso. Ora ogni
  vincolo è ancorato ad anno+mese+giorno.
- **Correzioni manuali perse al refresh**: nella versione originale, la
  "Correzione Manuale" post-generazione viveva solo in memoria del notebook
  — bastava ricaricare la pagina per perderla. Ora è salvata nel database.
- **Riposo minimo di 2 giorni**: la regola era descritta nel resoconto ma
  non implementata nel modello — un dipendente poteva ricevere un riposo
  isolato di 1 solo giorno. Ora è un vincolo esplicito.
- **Giorni di lavoro isolati**: senza un vincolo dedicato, il solutore poteva
  scatterare singoli giorni di lavoro pur di raggiungere il target
  numerico, invece di rispettare davvero il ritmo 2-2. Ora è impedito.
- **Conteggio dei blocchi**: sostituita l'euristica `>= 7 blocchi` con una
  struttura che deriva il numero corretto di blocchi direttamente dai
  vincoli su dimensione minima/massima dei blocchi (più robusto, meno
  soggetto a bug nascosti).
- **Riposo dopo un blocco di notti**: la condizione dipendeva da un'altra
  variabile decisa altrove nel modello, con rischio di comportamento non
  garantito. Ora è un'implicazione diretta.

### Funzionalità del resoconto che mancavano e sono state aggiunte
- **Opzione 3-3 (🔄)**: ora il blocco da 3 giorni, per chi ha questa
  preferenza, viene effettivamente premiato quando segue il pattern
  Giorno+Notte+Notte (prima era descritto ma non modellato).
- **Diritto ai weekend** (almeno 2 weekend interi liberi al mese) e
  **sincronizzazione weekend** (Venerdì di preferenza Giorno, Lunedì di
  rientro di preferenza Notte): implementati come obiettivi "morbidi" (il
  motore li premia quando può, ma non li rende obbligatori) per non
  rischiare che il planning diventi irrisolvibile in mesi con calendari
  sfavorevoli.

### Cambi di architettura
- Interfaccia ipywidgets/Colab → **pagina web** autonoma, con stampa A4 nativa
  del browser al posto dell'iniezione di JavaScript nella finestra.
- File JSON → **SQLite**: stessa semplicità (un file unico), ma con
  transazioni vere, niente rischio di corruzione.
- Motore separato dall'interfaccia: `engine.py` non sa nulla di HTTP o di
  interfaccia, è testabile da solo.
- Peso gerarchico: la tabella per cognome (ROMEO 9, BERTRAND 8, ecc.) resta
  identica, ma ora ogni dipendente può anche avere un peso personalizzato
  impostabile dall'interfaccia, senza dover toccare il codice.

## Nota importante

Ho scritto e controllato tutto il codice con la massima attenzione (sintassi
verificata, logica dei vincoli ragionata passo per passo), ma **non ho
potuto eseguire davvero il generatore di planning** in questo ambiente,
perché non ha accesso a internet per installare `ortools`/`fastapi`. Prima
di usarlo in produzione, testalo con la tua squadra reale su un mese vero e
verifica i risultati riga per riga — soprattutto le nuove regole (riposo
minimo, blocchi di lavoro) potrebbero rendere infeasible un mese con vincoli
manuali già molto stretti: se succede, il messaggio d'errore te lo segnala
e la correzione più semplice è allentare qualche vincolo manuale per quel
mese.

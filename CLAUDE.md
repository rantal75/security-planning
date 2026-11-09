# Gestione Sicurezza — Planning Turni

Riscrittura completa (in corso, sviluppata insieme a Claude) del vecchio
strumento v24.85 (Python + Google OR-Tools CP-SAT, eseguito su Google Colab
con interfaccia ipywidgets) usato per generare il planning turni H24 di una
squadra di sicurezza (Giorno / Notte / Riposo / Ferie / Malattia).

La nuova architettura (dalla v25.0 in poi) è: **backend FastAPI** + **database
SQLite** + **frontend web** (HTML/CSS/JS vanilla, nessun framework). Stessa
logica di calcolo di fondo (CP-SAT), ma applicazione vera invece di un
notebook.

## Struttura del progetto

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
│   ├── index.html        # Contiene anche lo sprite SVG delle icone (<defs>/<symbol>)
│   ├── style.css
│   └── app.js            # Chiama l'API e disegna l'interfaccia — nessuna
│                          # regola di business qui
├── requirements.txt
└── README.md
```

## Identità visiva

Console operativa dark-theme, non un dashboard SaaS generico. Palette con
significato semantico: ambra calda = Giornata, blu freddo = Notte, grigio =
Riposo, rosso smorzato = Ferie/Malattia, oro = Capo/Titolare. Font: IBM Plex
Sans (UI) + IBM Plex Mono (dati/tabelle). Icone: sprite SVG inline in
`index.html` (niente emoji — sostituite tutte in v25.1 perché ritenute poco
professionali). Interfaccia bilingue IT/FR.

## Schema di versionamento (IMPORTANTE — seguire sempre)

Il salto da v24.x a **v25.x** segna il cambio di architettura. Da qui in
avanti la numerazione continua in modo progressivo (v25.2, v25.3, v25.4, ...)
a **ogni modifica** fatta al progetto. Ad ogni nuova versione, aggiornare
SEMPRE e insieme questi tre punti (mai uno solo):

1. Il badge versione nell'interfaccia: `<span class="version-tag">` in
   `frontend/index.html`, vicino al titolo in alto a sinistra.
2. La tabella changelog nel README, sezione "## Versione".
3. Un tag Git annotato (`git tag -a vXX.Y -m "..."`).

### Cronologia versioni

- **v25.0** — Prima consegna della nuova architettura: riscrittura completa
  da Colab/ipywidgets a FastAPI + SQLite + frontend web.
- **v25.1** — Sostituite tutte le emoji dell'interfaccia con icone SVG
  professionali disegnate su misura, stile "console operativa". Palette e
  font invariati.
- **v25.2** — Corretto un bug di layout: le icone (chip di preferenza/ruolo
  nel form dipendenti, tab Vincoli e Planning) risultavano enormi su alcuni
  browser, spingendo la lista dipendenti e altri contenuti fuori pagina.
  Aggiunte dimensioni esplicite (`width`/`height`/`viewBox`) a ogni
  `<svg class="icon">`, sia in `index.html` sia nell'helper `icon()` in
  `app.js`; rinforzato il CSS delle `.chip` (`flex: 0 0 auto` su chip/input/
  icona) e aggiunto `flex-wrap: wrap` a `.field-row` per non rompere il
  layout su tablet (768px) e PC.
- **v25.3** — Le funzioni sviluppate a settembre (straordinario/recupero,
  planning salvati, correzioni manuali, continuità mese precedente) erano
  partite dalla v25.0 senza le icone: riunite con la v25.2. Le emoji delle
  parti nuove sono diventate icone SVG (`save`, `eye`, `arrow-left`,
  `archive`, `plus-circle` — quest'ultima con classe `icon-ot`, verde
  come lo straordinario). Regola: un elemento con icona tiene `data-i18n`
  su uno `<span>` interno, mai sull'elemento stesso, perché `applyI18n()`
  sostituisce `textContent` e cancellerebbe l'icona.
- **v25.4** — Regola Natale/Capodanno (dettagli nella nota v25.4 in testa
  a `engine.py`). Blocco Natale = G/N del 24-25; blocco Capodanno = G/N del
  31 + G del 1° gennaio; vincolo rigido "mai entrambi". Rotazione tra gli
  anni come penalità nell'obiettivo (tabella `holiday_history`, `year` =
  anno del dicembre). Gennaio legge il dicembre SALVATO (`prev_december`):
  se dicembre non è salvato, il 1° gennaio non ha regole. Lo storico si
  aggiorna al salvataggio (`_record_holidays` in `main.py`, righe
  `auto_dic`/`auto_gen`); le righe `manuale` non si toccano mai. Diagnosi:
  nuova categoria `festivita`. Provato con i dati reali di dicembre 2026 e
  gennaio 2027 (su una copia del db).
- **v25.5** — Form vincoli: niente più errori scartati in silenzio
  (`#constraint-status`), "Al giorno" segue "Dal giorno", mese mostrato in
  `#constraint-period` (il form usa il mese della tab Planning). Motore: la
  regola "rientro dalle ferie si lavora" salta i riposi forzati/recuperi
  messi subito dopo l'assenza.
- **v25.6** — All'avvio (`init()` in `app.js`) mese/anno della tab Planning
  partono dal mese prossimo invece che da Gennaio.

## Repository Git

Il progetto è versionato con Git e pubblicato su
`https://github.com/rantal75/security-planning` (branch locale `master`,
che corrisponde a `main` su GitHub). La cartella sta su Google Drive
(`G:\Il mio Drive\Lavoro\Prog planning\security-planning`) e l'utente ci
lavora da due PC Windows. Serve Python 3.12 (Python 3.14 non è compatibile
con `pydantic-core`/PyO3 al momento). Ogni PC ha il suo virtualenv: il
`.venv` dentro la cartella è quello del portatile; sul PC fisso il
virtualenv è `C:\venvs\security-planning`, fuori da Drive. Non avviare il
gestionale su entrambi i PC insieme: `planning.db` è sincronizzato da Drive.

## Avvio locale

```bash
cd security-planning
.venv\Scripts\activate        # portatile
uvicorn backend.main:app --reload
# PC fisso: C:\venvs\security-planning\Scripts\uvicorn backend.main:app --reload
```

Poi aprire il browser su http://127.0.0.1:8000/. Il database `planning.db`
viene creato automaticamente al primo avvio.

## Note per chi continua lo sviluppo

- L'utente (Alex) non è uno sviluppatore esperto: scrivere spiegazioni
  chiare, passo per passo, e chiedere sempre conferma prima di comandi
  potenzialmente distruttivi.
- Il codice non è mai stato testato con un ambiente OR-Tools reale prima
  della v25.x: prima di considerare "finita" una modifica alla logica del
  motore (`engine.py`), va verificata con un mese vero e vincoli reali.
- Tab "Ferie & Vincoli" e "Planning" sono state verificate su viewport
  tablet (768px) e desktop (1280px) dopo il fix v25.2: nessuna icona
  sovradimensionata, nessun overflow orizzontale della pagina (la tabella
  del planning scorre correttamente solo al proprio interno, tramite
  `#planning-table-wrap { overflow-x: auto; }`). Nessuna modifica
  aggiuntiva è stata necessaria: il fix CSS di v25.2 era già globale
  (classi `.icon`, `.chip`, `.field-row` condivise da tutte le tab).
- Esiste un secondo progetto separato dell'utente (revisione di schede PDF
  di sicurezza antincendio) che NON ha nulla a che fare con questo — non
  confondere i due contesti.

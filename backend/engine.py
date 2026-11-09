"""
engine.py — Motore di generazione del planning turni.

Riscrittura completa del motore originale. Rispetto alla versione v24.85:

CORREZIONI DI BUG:
  - I vincoli manuali (ferie/malattia/riposo forzato/ecc.) ora sono correttamente
    ancorati a (anno, mese, giorno) e non solo al numero del giorno: nella
    versione originale un vincolo sul "giorno 15" restava valido per SEMPRE,
    anche generando un mese diverso.
  - La regola "riposo minimo di 2 giorni consecutivi" (Sez. 4 del resoconto)
    non era implementata: un dipendente poteva ricevere un giorno di riposo
    isolato. Ora è un vincolo esplicito.
  - La regola simmetrica "nessun giorno di lavoro isolato" (necessaria per
    ottenere davvero il ritmo 2-2-2-2-2-2-3 descritto) non esisteva: senza di
    essa il solutore poteva sparpagliare singoli giorni di lavoro pur di
    raggiungere il target numerico. Ora è un vincolo esplicito.
  - Il conteggio dei "blocchi" (per garantire il pattern 2-2 con un solo
    blocco da 3) usava una euristica (`starts >= 7`) invece di derivare la
    struttura direttamente dai vincoli sulla dimensione dei blocchi: ora il
    numero di blocchi non è più imposto a mano, emerge automaticamente da
    "blocco minimo 2, massimo 3, un solo blocco da 3".
  - Il vincolo "riposo di almeno 2 giorni dopo un blocco di notti" dipendeva,
    nella versione originale, da un'altra variabile già decisa altrove
    (rischio di infeasibility "silenziosa" o di comportamento non garantito).
    Ora è un'implicazione diretta e autosufficiente.

NUOVE REGOLE IMPLEMENTATE (assenti nella v24.85, presenti nel resoconto):
  - Sez. 4 Opzione 3-3 (🔄): per chi la attiva, il blocco unico da 3 giorni
    viene premiato (bonus nell'obiettivo) se segue il pattern preferito
    Giorno + Notte + Notte, invece di essere lasciato del tutto casuale.
  - Sez. 7 "Diritto ai weekend": bonus nell'obiettivo per chi ottiene almeno
    2 weekend interi liberi al mese (regola trattata come obiettivo morbido,
    non vincolo rigido, per non rischiare di rendere il modello infeasible
    in mesi con calendari sfavorevoli).
  - Sez. 7 "Sincronizzazione weekend": bonus per Venerdì-Giorno prima di un
    weekend di riposo e Lunedì-Notte al rientro da un weekend di riposo.

REGOLE CONFERMATE E MANTENUTE (già presenti, verificate corrette):
  - Formula dei "Sacri 15" (target pro-rata in caso di assenza).
  - Divieto di 4+ giorni consecutivi di lavoro o di riposo (riposo escluse
    ferie/malattia).
  - Mai turno Giorno il giorno successivo a un turno Notte.
  - Range di notti mensili secondo la preferenza (Notte/Giorno/Neutro).
  - Modalità "Jolly" per chi ha assenze nel mese: perde i vincoli di ritmo
    rigido (blocco da 3, niente giorni isolati) per dare flessibilità al
    solutore nel coprire i buchi.
  - Rientro dalle ferie: il primo giorno dopo un'assenza deve essere lavorato.
  - Pesi gerarchici (ROMEO 9, BERTRAND 8, ZUPPARDO 8, FUSCO 7, altri 5).
  - Esubero/carenza squadra: allargamento della copertura giornaliera.

MODIFICA (2026-09-18): il calcolo dei "Sacri 15" produceva internamente un
valore `riposo_dovuto` (giorni di riposo pro-rata, escluse ferie/malattia)
usato SOLO come passaggio intermedio per derivare il target di giorni di
LAVORO, e poi scartato — non era mai esposto. Ora viene conservato in
`self.riposi_dovuti` e restituito in `EngineResult.riposi_dovuti`, così da
poter mostrare quanti giorni di riposo spettano a ciascun dipendente nel
mese (valore che varia in base a ferie/malattia), non solo i giorni di
lavoro dovuti.

MODIFICA (2026-09-25): aggiunto il meccanismo "straordinario". Il vincolo
`sum(work[w,d]) == target` era un'uguaglianza ESATTA senza alcun margine:
se un'assenza prolungata (es. malattia per tutto il mese) toglie un
lavoratore dalla rotazione, il solutore può non avere più alcuna soluzione
ammissibile per ridistribuire quel carico sugli altri, anche quando in
teoria ci sarebbe abbastanza "capacità umana" per farlo — da qui i
"Nessuna soluzione trovata" su mesi con assenze pesanti. Per i soli
dipendenti scelti esplicitamente come disponibili per lo straordinario
(`overtime_ids`), il vincolo diventa un range [target, target+extra] con
una penalità nell'obiettivo che scoraggia (senza vietare) il superamento
della quota: il solutore usa lo straordinario solo se e quanto serve per
trovare una soluzione, mai per scelta "gratuita". I giorni di lavoro
eccedenti la quota vengono poi individuati (gli ultimi N giorni lavorati
in ordine cronologico, N = extra effettivamente usato) e restituiti in
`EngineResult.overtime_days` per l'evidenziazione in blu lato UI/export.

Aggiunto anche il tipo di vincolo "recupero": si comporta esattamente come
"riposo forzato" nel motore (giorno bloccato a non-lavoro, quota mensile
invariata) — la differenza è puramente amministrativa e vive fuori dal
motore (main.py): scala un giorno dal "bilancio" di giorni di recupero
maturati con lo straordinario.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from ortools.sat.python import cp_model

# --- Festività fisse (stesse della versione originale) ---
FIXED_HOLIDAYS = {(1, 1), (27, 1), (1, 5), (15, 8), (1, 11), (19, 11), (8, 12), (25, 12)}

# --- Pesi gerarchici di default, per cognome (Sez. 6 del resoconto) ---
DEFAULT_WEIGHTS = {"ROMEO": 9, "BERTRAND": 8, "ZUPPARDO": 8, "FUSCO": 7}
DEFAULT_WEIGHT = 5

ASSIGNABLE_TYPES = {"giorno", "notte", "riposo", "ferie", "malattia", "chef2", "recupero"}


def get_employee_weight(employee: dict) -> int:
    """Peso gerarchico: usa il peso personalizzato se impostato, altrimenti
    ricade sulla tabella per cognome, altrimenti il default."""
    if employee.get("custom_weight") is not None:
        return int(employee["custom_weight"])
    last_name = (employee.get("last_name") or "").upper()
    return DEFAULT_WEIGHTS.get(last_name, DEFAULT_WEIGHT)


@dataclass
class EngineResult:
    ok: bool
    days: dict = field(default_factory=dict)  # {day: {"giorno": [...], "notte": [...], ...}}
    targets: dict = field(default_factory=dict)
    night_targets: dict = field(default_factory=dict)
    riposi_dovuti: dict = field(default_factory=dict)
    # {employee_id: [giorni]} — giorni di lavoro eccedenti la quota mensile
    # (Sacri 15), assegnati per necessità di copertura ai soli dipendenti
    # scelti come disponibili per lo straordinario. Vuoto per chi non ha
    # superato la propria quota.
    overtime_days: dict = field(default_factory=dict)
    # Diagnosi automatica quando ok=False (vedi ShiftEngine._diagnose):
    # [{"type": "chef2"|"riposo"|"recupero", "culprits": [{"day": int, "employee_id": str}, ...]}]
    # "culprits" vuoto = la categoria è implicata ma non si è riusciti a
    # isolare la singola voce responsabile entro il budget di prove.
    diagnosis: list = field(default_factory=list)
    error: Optional[str] = None


class ShiftEngine:
    """Genera il planning per un mese dato un elenco di dipendenti e un
    insieme di vincoli manuali già filtrati per quel mese/anno."""

    def __init__(self, employees: list[dict], year: int, month: int,
                 manual_constraints: dict[tuple[int, str], str], chef_present: bool,
                 overtime_ids: Optional[set[str]] = None, overtime_max_extra: int = 0):
        """
        employees: lista di dict dipendente (id, first_name, last_name,
            pref_night, pref_day, pref_33, is_titular, is_adjoint, is_equipe,
            is_temp, custom_weight)
        manual_constraints: dict {(giorno, employee_id): tipo} GIÀ filtrato
            per l'anno/mese corrente (vedi main.py: la scelta di filtrare qui
            e non nel motore mantiene il motore stesso puro e testabile).
        overtime_ids: id dei dipendenti disponibili per lo straordinario in
            questo mese (scelta ad-hoc, non un attributo fisso del
            dipendente — vedi nota 2026-09-25 sopra).
        overtime_max_extra: numero massimo di giorni di lavoro oltre la
            quota mensile che ciascun dipendente in overtime_ids può
            ricevere. 0 (default) equivale a nessuno straordinario, anche
            se overtime_ids non è vuoto.
        """
        self.employees = sorted(employees, key=lambda e: -get_employee_weight(e))
        self.year, self.month = year, month
        self.manual_constraints = manual_constraints
        self.chef_present = chef_present
        self.num_days = calendar.monthrange(year, month)[1]
        self.overtime_ids = set(overtime_ids or set())
        self.overtime_max_extra = max(0, int(overtime_max_extra or 0))

        self.titular = next((e for e in self.employees if e.get("is_titular")), None)
        self.workers = [e for e in self.employees if not e.get("is_titular")]

        self.targets: dict[str, int] = {}
        self.night_targets: dict[str, tuple[int, int]] = {}
        self.is_jolly: dict[str, bool] = {}
        # Giorni di riposo dovuti nel mese per dipendente, formula "Sacri 15"
        # pro-rata sui giorni di presenza effettiva (esclusi ferie/malattia).
        # Varia in funzione delle assenze: in un mese di 30gg senza assenze
        # il riposo teorico è 15gg; con ferie/malattia viene riproporzionato
        # sui soli giorni di presenza.
        self.riposi_dovuti: dict[str, int] = {}

        riposo_teorico = self.num_days - 15
        total_target_capacity = 0

        for emp in self.workers:
            eid = emp["id"]
            abs_days = sum(
                1 for (d, name), t in self.manual_constraints.items()
                if name == eid and t in ("ferie", "malattia")
            )
            self.is_jolly[eid] = abs_days > 0
            presenza = self.num_days - abs_days
            # Sacri 15: formula pro-rata, arrotondamento "0.5 verso l'alto"
            riposo_dovuto = int((presenza * riposo_teorico / self.num_days) + 0.5)
            target = max(0, presenza - riposo_dovuto)
            self.targets[eid] = target
            self.riposi_dovuti[eid] = riposo_dovuto
            total_target_capacity += target

            if self.is_jolly[eid]:
                self.night_targets[eid] = (1, 12)
            elif emp.get("pref_night"):
                self.night_targets[eid] = (8, 12)
            elif emp.get("pref_day"):
                self.night_targets[eid] = (1, 5)
            else:
                self.night_targets[eid] = (3, 8)

        # Capacità standard di copertura: 4 posti/giorno + 3 posti/notte.
        # Se il target complessivo richiesto supera questa capacità (squadra
        # ridotta rispetto al numero di "quote" da coprire), si passa alla
        # copertura allargata (5 giorno + 4 notte), come da Sez. 3 del resoconto.
        standard_capacity = self.num_days * (4 + 3)
        self.is_overflow = total_target_capacity > standard_capacity

    # ------------------------------------------------------------------
    def _diagnose(self) -> list[dict]:
        """Quando il modello non ha soluzione, prova a capire perché invece
        di limitarsi a "Nessuna soluzione trovata". Approccio: per ogni
        categoria di vincolo manuale che ha senso "rilassare" a scopo
        diagnostico (sostituzione capo, riposo forzato, recupero — NON
        ferie/malattia, che sono assenze reali e non un errore da
        segnalare), rigenera rapidamente (poche secondi, sola
        soddisfacibilità) SENZA quella categoria: se diventa risolvibile,
        la categoria è coinvolta. In quel caso prova a restringere
        ulteriormente rimuovendo una singola voce alla volta, per indicare
        il giorno/dipendente specifico responsabile invece di una
        categoria generica. Il numero di prove è limitato (budget) per non
        far esplodere i tempi di attesa su mesi con molti vincoli."""
        findings: list[dict] = []
        relaxable_types = ("chef2", "riposo", "recupero")
        probes_budget = 20
        probes_used = 0

        for t in relaxable_types:
            entries = [(d, eid) for (d, eid), ty in self.manual_constraints.items() if ty == t]
            if not entries or probes_used >= probes_budget:
                continue

            reduced = {k: v for k, v in self.manual_constraints.items() if v != t}
            probe = ShiftEngine(self.employees, self.year, self.month, reduced, self.chef_present,
                                 overtime_ids=self.overtime_ids, overtime_max_extra=self.overtime_max_extra)
            probes_used += 1
            if not probe.generate(time_limit=6.0, feasibility_only=True, diagnose=False).ok:
                continue  # rimuovere l'intera categoria non basta: non è (solo) lei

            culprits = []
            for (d, eid) in entries:
                if probes_used >= probes_budget:
                    break
                reduced2 = dict(self.manual_constraints)
                del reduced2[(d, eid)]
                probe2 = ShiftEngine(self.employees, self.year, self.month, reduced2, self.chef_present,
                                      overtime_ids=self.overtime_ids, overtime_max_extra=self.overtime_max_extra)
                probes_used += 1
                if probe2.generate(time_limit=4.0, feasibility_only=True, diagnose=False).ok:
                    culprits.append({"day": d, "employee_id": eid})
            findings.append({"type": t, "culprits": culprits})

        return findings

    # ------------------------------------------------------------------
    def generate(self, time_limit: float = 50.0, feasibility_only: bool = False,
                 diagnose: bool = True) -> EngineResult:
        """
        time_limit: secondi massimi concessi al solutore. Usato più basso
            (poche secondi) dalle prove di diagnosi (vedi _diagnose sotto),
            dove serve solo sapere SE esiste una soluzione, non la migliore.
        feasibility_only: se True, il modello non ha obiettivo da
            ottimizzare (nessuna model.Maximize) — il solutore si ferma
            alla prima soluzione trovata, molto più veloce. Usato solo
            dalle prove di diagnosi.
        diagnose: se True (default per una chiamata "vera") e il modello
            risulta senza soluzione, prova a individuare la causa più
            probabile rieseguendo prove rapide con singoli vincoli
            rimossi (vedi _diagnose). Le prove interne passano False per
            evitare ricorsione.
        """
        model = cp_model.CpModel()
        W = len(self.workers)
        nd = self.num_days

        x_day: dict[tuple[int, int], cp_model.IntVar] = {}
        x_night: dict[tuple[int, int], cp_model.IntVar] = {}
        work: dict[tuple[int, int], cp_model.IntVar] = {}
        is_abs: dict[tuple[int, int], int] = {}
        rest: dict[tuple[int, int], cp_model.IntVar] = {}

        for w in range(W):
            eid = self.workers[w]["id"]
            for d in range(1, nd + 1):
                x_day[w, d] = model.NewBoolVar(f"day_{w}_{d}")
                x_night[w, d] = model.NewBoolVar(f"night_{w}_{d}")
                work[w, d] = model.NewBoolVar(f"work_{w}_{d}")
                rest[w, d] = model.NewBoolVar(f"rest_{w}_{d}")
                is_abs[w, d] = 1 if self.manual_constraints.get((d, eid)) in ("ferie", "malattia") else 0

                # Un solo turno al giorno (giorno XOR notte XOR niente)
                model.Add(x_day[w, d] + x_night[w, d] <= 1)
                model.Add(work[w, d] == x_day[w, d] + x_night[w, d])
                if is_abs[w, d]:
                    model.Add(work[w, d] == 0)
                # riposo effettivo = non lavora e non è assente (le ferie non sono "riposo")
                model.Add(rest[w, d] == 1 - work[w, d] - is_abs[w, d])

                # Vincolo manuale esplicito "riposo forzato" — "recupero" si
                # comporta identicamente nel motore (blocca il giorno), la
                # differenza è solo amministrativa (bilancio ore recupero,
                # gestito fuori dal motore).
                if self.manual_constraints.get((d, eid)) in ("riposo", "recupero"):
                    model.Add(work[w, d] == 0)

                # Sostituzione del capo (chef2): quel giorno chi sostituisce
                # lavora la Giornata (07-19) come farebbe il capo titolare —
                # NON è un giorno di riposo. Prima questo vincolo non
                # esisteva: "chef2" era solo un'etichetta applicata DOPO la
                # generazione, senza alcun legame col motore. Se il
                # solutore assegnava comunque un riposo quel giorno al
                # sostituto, il dipendente "spariva" da tutte le colonne
                # (non Giornata/Notte perché a riposo per il motore, non
                # Riposo perché già "occupato" come capo nell'etichettatura
                # finale) — falsando il conteggio mensile lavoro/riposo
                # mostrato in UI (bug segnalato dall'utente il 2026-09-25).
                if self.manual_constraints.get((d, eid)) == "chef2":
                    model.Add(x_day[w, d] == 1)

        # Giorni con sostituzione del capo, e chi (indice worker) sostituisce
        # — usato per escludere il sostituto dal conteggio minimo di
        # copertura: quel giorno lui FA il capo, non è uno dei security
        # agent "di pattuglia". Devono comunque esserci almeno 2 agenti
        # normali IN PIÙ a lui, esattamente come quando c'è il capo
        # titolare Faure (che non è nemmeno un worker del motore e quindi
        # non entra mai in questo conteggio) — segnalato dall'utente il
        # 2026-09-25.
        eid_to_widx = {self.workers[w]["id"]: w for w in range(W)}
        chef2_widx_by_day: dict[int, int] = {}
        for (d, eid), t in self.manual_constraints.items():
            if t == "chef2" and eid in eid_to_widx:
                chef2_widx_by_day[d] = eid_to_widx[eid]

        # --- Copertura giornaliera (Sez. 3: allargamento in caso di esubero/carenza) ---
        max_g, max_n = (5, 4) if self.is_overflow else (4, 3)
        for d in range(1, nd + 1):
            chef_w = chef2_widx_by_day.get(d)
            day_workers = [w for w in range(W) if w != chef_w] if chef_w is not None else list(range(W))
            model.Add(sum(x_day[w, d] for w in day_workers) >= 2)
            model.Add(sum(x_day[w, d] for w in range(W)) <= max_g)
            model.Add(sum(x_night[w, d] for w in range(W)) >= 2)
            model.Add(sum(x_night[w, d] for w in range(W)) <= max_n)

        objective_terms = []
        extra_vars: dict[int, cp_model.IntVar] = {}

        for w in range(W):
            emp = self.workers[w]
            eid = emp["id"]
            target = self.targets[eid]
            if target == 0:
                # Assente tutto il mese: nessun turno da assegnare.
                for d in range(1, nd + 1):
                    model.Add(work[w, d] == 0)
                continue

            if eid in self.overtime_ids and self.overtime_max_extra > 0:
                # Straordinario: la quota diventa un range [target, target+extra]
                # invece di un'uguaglianza rigida. Una forte penalità
                # nell'obiettivo scoraggia il solutore dall'usare lo
                # straordinario a meno che non sia l'unico modo per trovare
                # una soluzione ammissibile (vedi nota 2026-09-25 in testa
                # al file).
                extra = model.NewIntVar(0, self.overtime_max_extra, f"extra_{w}")
                model.Add(sum(work[w, d] for d in range(1, nd + 1)) == target + extra)
                objective_terms.append(extra * -2000)
                extra_vars[w] = extra
            else:
                model.Add(sum(work[w, d] for d in range(1, nd + 1)) == target)

            n_min, n_max = self.night_targets[eid]
            model.AddLinearConstraint(sum(x_night[w, d] for d in range(1, nd + 1)), n_min, n_max)

            # --- Sicurezza fisica (Sez. 5), SEMPRE valide, anche per i Jolly ---
            # Mai giorno dopo notte
            for d in range(1, nd):
                model.Add(x_night[w, d] + x_day[w, d + 1] <= 1)

            # Almeno 2 giorni di riposo dopo un blocco di notti
            for d in range(1, nd - 1):
                model.Add(work[w, d + 2] == 0).OnlyEnforceIf([x_night[w, d], work[w, d + 1].Not()])

            # Divieto di 4+ giorni consecutivi di lavoro
            for d in range(1, nd - 2):
                model.Add(sum(work[w, d + i] for i in range(4)) <= 3)

            # Divieto di 4+ giorni consecutivi di riposo (le ferie non contano come riposo)
            for d in range(1, nd - 2):
                model.Add(sum(rest[w, d + i] for i in range(4)) <= 3)

            # Rientro dalle ferie: il primo giorno dopo un'assenza si lavora
            for d in range(1, nd):
                if is_abs[w, d] and not is_abs.get((w, d + 1), 0):
                    model.Add(work[w, d + 1] == 1)

            # --- Ritmo 2-2 (Sez. 4), rilassato per i Jolly ---
            if not self.is_jolly[eid]:
                # Nessun giorno di riposo isolato (blocco minimo di riposo = 2),
                # eccetto in prossimità di un'assenza (sincronizzazione post-ferie).
                for d in range(2, nd):
                    if is_abs[w, d - 1] or is_abs[w, d + 1]:
                        continue
                    model.AddBoolOr([work[w, d - 1].Not(), rest[w, d].Not(), work[w, d + 1].Not()])

                # Nessun giorno di lavoro isolato (blocco minimo di lavoro = 2)
                for d in range(2, nd):
                    model.AddBoolOr([rest[w, d - 1].Not(), work[w, d].Not(), rest[w, d + 1].Not()])

                # Individua l'inizio di ogni blocco di lavoro (linearizzazione AND)
                is_start = {}
                for d in range(1, nd + 1):
                    is_start[d] = model.NewBoolVar(f"start_{w}_{d}")
                    prev_work = work[w, d - 1] if d > 1 else model.NewConstant(0)
                    model.Add(is_start[d] <= work[w, d])
                    model.Add(is_start[d] <= 1 - prev_work)
                    model.Add(is_start[d] >= work[w, d] - prev_work)

                # Blocco da 3 giorni: esattamente uno al mese (Sez. 4, "Numero 15")
                is_block3 = []
                for d in range(1, nd - 1):
                    b3 = model.NewBoolVar(f"block3_{w}_{d}")
                    model.Add(b3 <= is_start[d])
                    model.Add(b3 <= work[w, d + 1])
                    model.Add(b3 <= work[w, d + 2])
                    model.Add(b3 >= is_start[d] + work[w, d + 1] + work[w, d + 2] - 2)
                    is_block3.append((d, b3))
                model.Add(sum(b for _, b in is_block3) == 1)

                # Opzione 3-3 (🔄): se attiva, premia il pattern Giorno+Notte+Notte
                # nell'unico blocco da 3 giorni disponibile.
                if emp.get("pref_33"):
                    for d, b3 in is_block3:
                        pattern_gnn = model.NewBoolVar(f"gnn_{w}_{d}")
                        model.Add(pattern_gnn <= b3)
                        model.Add(pattern_gnn <= x_day[w, d])
                        model.Add(pattern_gnn <= x_night[w, d + 1])
                        model.Add(pattern_gnn <= x_night[w, d + 2])
                        model.Add(pattern_gnn >= b3 + x_day[w, d] + x_night[w, d + 1] + x_night[w, d + 2] - 3)
                        objective_terms.append(pattern_gnn * 50)

            # --- Weekend (Sez. 7), trattati come bonus morbido ---
            free_weekends = []
            for d in range(1, nd - 1):
                dt = date(self.year, self.month, d)
                if dt.weekday() == 5:  # Sabato
                    sat, sun = d, d + 1
                    fw = model.NewBoolVar(f"freeweekend_{w}_{d}")
                    model.Add(fw <= 1 - work[w, sat])
                    model.Add(fw <= 1 - work[w, sun])
                    model.Add(fw >= (1 - work[w, sat]) + (1 - work[w, sun]) - 1)
                    free_weekends.append(fw)
                    objective_terms.append(fw * 30)

                    # Venerdì preferibilmente Giorno, se il weekend è di riposo
                    if sat - 1 >= 1:
                        fri_day_ok = model.NewBoolVar(f"friday_day_{w}_{d}")
                        model.Add(fri_day_ok <= fw)
                        model.Add(fri_day_ok <= x_day[w, sat - 1])
                        model.Add(fri_day_ok >= fw + x_day[w, sat - 1] - 1)
                        objective_terms.append(fri_day_ok * 10)

                    # Lunedì di rientro preferibilmente Notte
                    if sun + 1 <= nd:
                        mon_night_ok = model.NewBoolVar(f"monday_night_{w}_{d}")
                        model.Add(mon_night_ok <= fw)
                        model.Add(mon_night_ok <= x_night[w, sun + 1])
                        model.Add(mon_night_ok >= fw + x_night[w, sun + 1] - 1)
                        objective_terms.append(mon_night_ok * 10)

            if not self.is_jolly[eid] and free_weekends:
                # Bonus extra se si raggiungono almeno 2 weekend liberi (soft,
                # non hard, per non rischiare infeasibility su mesi sfavorevoli)
                at_least_two = model.NewBoolVar(f"two_weekends_{w}")
                model.Add(sum(free_weekends) >= 2).OnlyEnforceIf(at_least_two)
                objective_terms.append(at_least_two * 100)

        # --- Priorità post-assenza: preferenza per rientro in notte (comportamento
        # ereditato dalla v24.85, mantenuto) ---
        for w in range(W):
            eid = self.workers[w]["id"]
            for d in range(1, nd):
                if is_abs.get((w, d), 0) and not is_abs.get((w, d + 1), 0):
                    objective_terms.append(x_night[w, d + 1] * 5)

        if not feasibility_only:
            model.Maximize(sum(objective_terms) if objective_terms else 0)
        # feasibility_only=True: nessun obiettivo -> problema di sola
        # soddisfacibilità, il solutore si ferma alla prima soluzione.

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit
        solver.parameters.num_search_workers = 8
        status = solver.Solve(model)

        if status not in (cp_model.FEASIBLE, cp_model.OPTIMAL):
            diagnosis = self._diagnose() if diagnose else []
            return EngineResult(ok=False, error="no_solution", diagnosis=diagnosis)

        # Giorni di straordinario per dipendente: gli ultimi N giorni
        # lavorati in ordine cronologico, dove N = extra realmente usato dal
        # solutore per quel dipendente (può essere 0 anche se il dipendente
        # era disponibile per lo straordinario, se non è servito).
        overtime_days: dict[str, list[int]] = {}
        for w, extra_var in extra_vars.items():
            extra_used = solver.Value(extra_var)
            if extra_used <= 0:
                continue
            eid = self.workers[w]["id"]
            worked_days = [d for d in range(1, nd + 1)
                           if solver.Value(x_day[w, d]) or solver.Value(x_night[w, d])]
            overtime_days[eid] = worked_days[-extra_used:]

        days_out = {
            d: {"giorno": [], "notte": [], "riposo": [], "ferie": [], "malattia": [], "chef": None}
            for d in range(1, nd + 1)
        }

        for d in range(1, nd + 1):
            for w in range(W):
                eid = self.workers[w]["id"]
                if solver.Value(x_day[w, d]):
                    days_out[d]["giorno"].append(eid)
                elif solver.Value(x_night[w, d]):
                    days_out[d]["notte"].append(eid)

            for emp in self.employees:
                t = self.manual_constraints.get((d, emp["id"]))
                if t in ("ferie", "malattia"):
                    days_out[d][t].append(emp["id"])

            dt = date(self.year, self.month, d)
            is_holiday = (d, self.month) in FIXED_HOLIDAYS
            if not (dt.weekday() >= 5 or is_holiday):
                substitute_id = next(
                    (eid for (day, eid), t in self.manual_constraints.items()
                     if day == d and t == "chef2"), None
                )
                if substitute_id:
                    days_out[d]["chef"] = substitute_id
                elif self.chef_present and self.titular:
                    if self.manual_constraints.get((d, self.titular["id"])) is None:
                        days_out[d]["chef"] = self.titular["id"]

            for emp in self.employees:
                eid = emp["id"]
                is_chef_today = days_out[d]["chef"] == eid
                already_placed = (
                    eid in days_out[d]["giorno"] or eid in days_out[d]["notte"]
                    or eid in days_out[d]["ferie"] or eid in days_out[d]["malattia"]
                    or is_chef_today
                )
                if not already_placed:
                    days_out[d]["riposo"].append(eid)

        return EngineResult(
            ok=True,
            days=days_out,
            targets=dict(self.targets),
            night_targets=dict(self.night_targets),
            riposi_dovuti=dict(self.riposi_dovuti),
            overtime_days=overtime_days,
        )

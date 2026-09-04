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

ASSIGNABLE_TYPES = {"giorno", "notte", "riposo", "ferie", "malattia", "chef2"}


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
    error: Optional[str] = None


class ShiftEngine:
    """Genera il planning per un mese dato un elenco di dipendenti e un
    insieme di vincoli manuali già filtrati per quel mese/anno."""

    def __init__(self, employees: list[dict], year: int, month: int,
                 manual_constraints: dict[tuple[int, str], str], chef_present: bool):
        """
        employees: lista di dict dipendente (id, first_name, last_name,
            pref_night, pref_day, pref_33, is_titular, is_adjoint, is_equipe,
            is_temp, custom_weight)
        manual_constraints: dict {(giorno, employee_id): tipo} GIÀ filtrato
            per l'anno/mese corrente (vedi main.py: la scelta di filtrare qui
            e non nel motore mantiene il motore stesso puro e testabile).
        """
        self.employees = sorted(employees, key=lambda e: -get_employee_weight(e))
        self.year, self.month = year, month
        self.manual_constraints = manual_constraints
        self.chef_present = chef_present
        self.num_days = calendar.monthrange(year, month)[1]

        self.titular = next((e for e in self.employees if e.get("is_titular")), None)
        self.workers = [e for e in self.employees if not e.get("is_titular")]

        self.targets: dict[str, int] = {}
        self.night_targets: dict[str, tuple[int, int]] = {}
        self.is_jolly: dict[str, bool] = {}

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
    def generate(self) -> EngineResult:
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

                # Vincolo manuale esplicito "riposo forzato"
                if self.manual_constraints.get((d, eid)) == "riposo":
                    model.Add(work[w, d] == 0)

        # --- Copertura giornaliera (Sez. 3: allargamento in caso di esubero/carenza) ---
        max_g, max_n = (5, 4) if self.is_overflow else (4, 3)
        for d in range(1, nd + 1):
            model.Add(sum(x_day[w, d] for w in range(W)) >= 2)
            model.Add(sum(x_day[w, d] for w in range(W)) <= max_g)
            model.Add(sum(x_night[w, d] for w in range(W)) >= 2)
            model.Add(sum(x_night[w, d] for w in range(W)) <= max_n)

        objective_terms = []

        for w in range(W):
            emp = self.workers[w]
            eid = emp["id"]
            target = self.targets[eid]
            if target == 0:
                # Assente tutto il mese: nessun turno da assegnare.
                for d in range(1, nd + 1):
                    model.Add(work[w, d] == 0)
                continue

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

        model.Maximize(sum(objective_terms) if objective_terms else 0)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 50.0
        solver.parameters.num_search_workers = 8
        status = solver.Solve(model)

        if status not in (cp_model.FEASIBLE, cp_model.OPTIMAL):
            return EngineResult(ok=False, error="no_solution")

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
        )

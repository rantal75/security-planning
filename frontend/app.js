// app.js — Logica dell'interfaccia. Nessuna regola di business qui:
// tutto il calcolo del planning avviene lato server (backend/engine.py).
// Questo file si occupa solo di chiamare l'API e presentare i dati.

const API = "/api";

const I18N = {
  IT: {
    app_title: "Gestione Sicurezza", app_sub: "Planning turni H24",
    tab_staff: "Personale", tab_constraints: "Ferie & Vincoli", tab_planning: "Planning",
    staff_form_title: "Aggiungi / modifica dipendente",
    lbl_lastname: "Cognome", lbl_firstname: "Nome",
    lbl_pref_night: "🌙 Pref. Notte", lbl_pref_day: "☀️ Pref. Giorno", lbl_pref_33: "🔄 Pref. 3-3",
    lbl_titular: "👑 Titolare", lbl_adjoint: "🥈 Aggiunto", lbl_equipe: "🥉 Equipe", lbl_temp: "⏳ Temporaneo",
    lbl_weight: "Peso gerarchico personalizzato (opzionale)",
    btn_save: "Salva dipendente", btn_new: "Nuovo",
    staff_list_title: "Squadra",
    constraints_title: "Ferie, malattie e vincoli manuali",
    lbl_from: "Dal giorno", lbl_to: "Al giorno", lbl_employee: "Dipendente", lbl_type: "Tipo",
    type_ferie: "Ferie", type_malattia: "Malattia", type_riposo: "Riposo forzato", type_chef2: "Sostituzione capo",
    btn_add: "Aggiungi", btn_reset_constraints: "⚠️ Azzera vincoli del mese",
    lbl_month: "Mese", lbl_year: "Anno", lbl_chef_present: "Capo titolare presente",
    btn_generate: "Genera planning", opt_none: "— Evidenzia nessuno —",
    btn_export: "📥 Esporta Excel", btn_print: "🖨 Stampa A4",
    correction_title: "🛠️ Correzione manuale", lbl_day: "Giorno", lbl_move_to: "Sposta in",
    type_giorno: "Giornata", type_notte: "Notte",
    btn_apply: "Applica", counts_title: "Riepilogo turni per dipendente",
    col_day: "Giorno", col_date: "Data", col_giorno: "Giornata (07-19)", col_notte: "Notte (19-07)",
    col_riposo: "Riposo", col_chef: "Capo", col_ferie: "Ferie", col_malattia: "Malattia",
    none_sol: "Nessuna soluzione trovata: i vincoli attuali sono in conflitto tra loro per questo mese.",
    generated_ok: "Planning generato.",
    months: ["Gennaio","Febbraio","Marzo","Aprile","Maggio","Giugno","Luglio","Agosto","Settembre","Ottobre","Novembre","Dicembre"],
    days_abbr: ["Lun","Mar","Mer","Gio","Ven","Sab","Dom"],
  },
  FR: {
    app_title: "Gestion Sécurité", app_sub: "Planning des équipes H24",
    tab_staff: "Personnel", tab_constraints: "Congés & Contraintes", tab_planning: "Planning",
    staff_form_title: "Ajouter / modifier un agent",
    lbl_lastname: "Nom", lbl_firstname: "Prénom",
    lbl_pref_night: "🌙 Préf. Nuit", lbl_pref_day: "☀️ Préf. Jour", lbl_pref_33: "🔄 Préf. 3-3",
    lbl_titular: "👑 Titulaire", lbl_adjoint: "🥈 Adjoint", lbl_equipe: "🥉 Équipe", lbl_temp: "⏳ Temporaire",
    lbl_weight: "Poids hiérarchique personnalisé (optionnel)",
    btn_save: "Enregistrer", btn_new: "Nouveau",
    staff_list_title: "Équipe",
    constraints_title: "Congés, maladies et contraintes manuelles",
    lbl_from: "Du jour", lbl_to: "Au jour", lbl_employee: "Agent", lbl_type: "Type",
    type_ferie: "Congés", type_malattia: "Maladie", type_riposo: "Repos forcé", type_chef2: "Remplacement chef",
    btn_add: "Ajouter", btn_reset_constraints: "⚠️ Réinitialiser les contraintes du mois",
    lbl_month: "Mois", lbl_year: "Année", lbl_chef_present: "Chef titulaire présent",
    btn_generate: "Générer le planning", opt_none: "— Ne rien surligner —",
    btn_export: "📥 Exporter Excel", btn_print: "🖨 Imprimer A4",
    correction_title: "🛠️ Correction manuelle", lbl_day: "Jour", lbl_move_to: "Déplacer vers",
    type_giorno: "Journée", type_notte: "Nuit",
    btn_apply: "Appliquer", counts_title: "Récapitulatif des services par agent",
    col_day: "Jour", col_date: "Date", col_giorno: "Journée (07-19)", col_notte: "Nuit (19-07)",
    col_riposo: "Repos", col_chef: "Chef", col_ferie: "Congés", col_malattia: "Maladie",
    none_sol: "Aucune solution trouvée : les contraintes actuelles sont en conflit pour ce mois.",
    generated_ok: "Planning généré.",
    months: ["Janvier","Février","Mars","Avril","Mai","Juin","Juillet","Août","Septembre","Octobre","Novembre","Décembre"],
    days_abbr: ["Lun","Mar","Mer","Jeu","Ven","Sam","Dim"],
  },
};

let LANG = "IT";
let EMPLOYEES = [];
let LAST_RESULT = null; // { year, month, num_days, days: {...}, targets, night_targets }

function t(key) { return I18N[LANG][key] || key; }

function applyI18n() {
  document.querySelectorAll("[data-i18n]").forEach(el => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll(".lang-btn").forEach(b => b.classList.toggle("active", b.dataset.lang === LANG));
}

// ---------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------
document.querySelectorAll(".tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
    document.querySelectorAll(".panel").forEach(x => x.classList.remove("active"));
    tab.classList.add("active");
    document.getElementById("tab-" + tab.dataset.tab).classList.add("active");
  });
});

document.querySelectorAll(".lang-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    LANG = btn.dataset.lang;
    applyI18n();
    renderEmployeeList();
    renderEmployeeSelects();
    populateMonthYear();
    if (LAST_RESULT) renderPlanningTable();
  });
});

// ---------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------
async function api(path, options = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Errore ${res.status}`);
  }
  return res.json();
}

// ---------------------------------------------------------------
// Dipendenti
// ---------------------------------------------------------------
async function loadEmployees() {
  EMPLOYEES = await api("/employees");
  renderEmployeeList();
  renderEmployeeSelects();
}

function employeeName(id) {
  const e = EMPLOYEES.find(x => x.id === id);
  return e ? `${e.last_name.toUpperCase()} ${e.first_name}` : id;
}

function renderEmployeeList() {
  const el = document.getElementById("employee-list");
  el.innerHTML = "";
  EMPLOYEES.forEach(e => {
    const icons = [
      e.is_titular ? "👑" : "", e.is_adjoint ? "🥈" : "", e.is_equipe ? "🥉" : "",
      e.pref_night ? "🌙" : (e.pref_day ? "☀️" : "⚖️"), e.pref_33 ? "🔄" : "",
    ].join("");
    const badge = document.createElement("div");
    badge.className = "emp-badge";
    badge.innerHTML = `<span>${e.last_name.toUpperCase()}</span><span class="icons">${icons}</span><span class="del" data-id="${e.id}">✕</span>`;
    badge.addEventListener("click", (ev) => {
      if (ev.target.classList.contains("del")) return;
      fillEmployeeForm(e);
    });
    badge.querySelector(".del").addEventListener("click", async (ev) => {
      ev.stopPropagation();
      if (!confirm(`${e.last_name.toUpperCase()} — confermi l'eliminazione?`)) return;
      await api(`/employees/${e.id}`, { method: "DELETE" });
      await loadEmployees();
    });
    el.appendChild(badge);
  });
}

function fillEmployeeForm(e) {
  document.getElementById("emp-id-hidden").value = e.id;
  document.getElementById("emp-lastname").value = e.last_name;
  document.getElementById("emp-firstname").value = e.first_name;
  document.getElementById("emp-pref-night").checked = e.pref_night;
  document.getElementById("emp-pref-day").checked = e.pref_day;
  document.getElementById("emp-pref-33").checked = e.pref_33;
  document.getElementById("emp-titular").checked = e.is_titular;
  document.getElementById("emp-adjoint").checked = e.is_adjoint;
  document.getElementById("emp-equipe").checked = e.is_equipe;
  document.getElementById("emp-temp").checked = e.is_temp;
  document.getElementById("emp-weight").value = e.custom_weight ?? "";
}

document.getElementById("btn-clear-form").addEventListener("click", () => {
  document.getElementById("employee-form").reset();
  document.getElementById("emp-id-hidden").value = "";
});

document.getElementById("employee-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const payload = {
    last_name: document.getElementById("emp-lastname").value.trim(),
    first_name: document.getElementById("emp-firstname").value.trim(),
    pref_night: document.getElementById("emp-pref-night").checked,
    pref_day: document.getElementById("emp-pref-day").checked,
    pref_33: document.getElementById("emp-pref-33").checked,
    is_titular: document.getElementById("emp-titular").checked,
    is_adjoint: document.getElementById("emp-adjoint").checked,
    is_equipe: document.getElementById("emp-equipe").checked,
    is_temp: document.getElementById("emp-temp").checked,
    custom_weight: document.getElementById("emp-weight").value ? parseInt(document.getElementById("emp-weight").value) : null,
  };
  await api("/employees", { method: "POST", body: JSON.stringify(payload) });
  document.getElementById("employee-form").reset();
  document.getElementById("emp-id-hidden").value = "";
  await loadEmployees();
});

function renderEmployeeSelects() {
  const opts = EMPLOYEES.map(e => `<option value="${e.id}">${e.last_name.toUpperCase()} ${e.first_name}</option>`).join("");
  ["c-employee", "corr-employee"].forEach(id => {
    const sel = document.getElementById(id);
    const current = sel.value;
    sel.innerHTML = opts;
    if (current) sel.value = current;
  });
}

// ---------------------------------------------------------------
// Vincoli manuali (ferie/malattia/riposo/chef2)
// ---------------------------------------------------------------
function currentPeriod() {
  return {
    year: parseInt(document.getElementById("p-year").value),
    month: parseInt(document.getElementById("p-month").value),
  };
}

async function loadConstraints() {
  const { year, month } = currentPeriod();
  const rows = await api(`/constraints?year=${year}&month=${month}`);
  const el = document.getElementById("constraint-list");
  el.innerHTML = "";
  // raggruppa per dipendente+tipo per una vista più leggibile
  const grouped = {};
  rows.forEach(r => {
    const key = `${r.employee_id}__${r.type}`;
    grouped[key] = grouped[key] || { ids: [], days: [], type: r.type, employee_id: r.employee_id };
    grouped[key].ids.push(r.id);
    grouped[key].days.push(r.day);
  });
  Object.values(grouped).forEach(g => {
    g.days.sort((a, b) => a - b);
    const row = document.createElement("div");
    row.className = "constraint-row";
    row.innerHTML = `<span>${employeeName(g.employee_id)} — ${t("type_" + g.type) || g.type} (${g.days[0]}–${g.days[g.days.length - 1]})</span><span class="del">✕</span>`;
    row.querySelector(".del").addEventListener("click", async () => {
      for (const id of g.ids) await api(`/constraints/${id}`, { method: "DELETE" });
      await loadConstraints();
    });
    el.appendChild(row);
  });
}

document.getElementById("constraint-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const { year, month } = currentPeriod();
  const payload = {
    year, month,
    day_from: parseInt(document.getElementById("c-day-from").value),
    day_to: parseInt(document.getElementById("c-day-to").value),
    employee_id: document.getElementById("c-employee").value,
    type: document.getElementById("c-type").value,
  };
  if (!payload.employee_id) return;
  await api("/constraints", { method: "POST", body: JSON.stringify(payload) });
  await loadConstraints();
});

document.getElementById("btn-clear-constraints").addEventListener("click", async () => {
  const { year, month } = currentPeriod();
  if (!confirm(t("btn_reset_constraints") + "?")) return;
  await api(`/constraints?year=${year}&month=${month}`, { method: "DELETE" });
  await loadConstraints();
});

// ---------------------------------------------------------------
// Mese / Anno
// ---------------------------------------------------------------
function populateMonthYear() {
  const monthSel = document.getElementById("p-month");
  const prevMonth = monthSel.value;
  monthSel.innerHTML = I18N[LANG].months.map((m, i) => `<option value="${i + 1}">${m}</option>`).join("");
  if (prevMonth) monthSel.value = prevMonth;

  const yearSel = document.getElementById("p-year");
  if (!yearSel.dataset.filled) {
    const now = new Date();
    for (let y = now.getFullYear(); y <= now.getFullYear() + 2; y++) {
      const opt = document.createElement("option");
      opt.value = y; opt.textContent = y;
      yearSel.appendChild(opt);
    }
    yearSel.dataset.filled = "1";
  }
}

document.getElementById("p-month").addEventListener("change", loadConstraints);
document.getElementById("p-year").addEventListener("change", loadConstraints);

// ---------------------------------------------------------------
// Generazione planning
// ---------------------------------------------------------------
document.getElementById("btn-generate").addEventListener("click", async () => {
  const { year, month } = currentPeriod();
  const chef_present = document.getElementById("p-chef-present").checked;
  const statusEl = document.getElementById("planning-status");
  statusEl.textContent = "…";
  statusEl.className = "status-msg";
  try {
    LAST_RESULT = await api("/planning/generate", {
      method: "POST",
      body: JSON.stringify({ year, month, chef_present }),
    });
    statusEl.textContent = t("generated_ok");
    statusEl.className = "status-msg ok";
    populateHighlightSelect();
    populateCorrectionDaySelect();
    renderPlanningTable();
    renderCounts();
  } catch (e) {
    statusEl.textContent = t("none_sol");
    statusEl.className = "status-msg error";
  }
});

function populateHighlightSelect() {
  const sel = document.getElementById("p-highlight");
  sel.innerHTML = `<option value="">${t("opt_none")}</option>` +
    EMPLOYEES.map(e => `<option value="${e.id}">${e.last_name.toUpperCase()}</option>`).join("");
}
document.getElementById("p-highlight").addEventListener("change", renderPlanningTable);

function populateCorrectionDaySelect() {
  if (!LAST_RESULT) return;
  const sel = document.getElementById("corr-day");
  sel.innerHTML = "";
  for (let d = 1; d <= LAST_RESULT.num_days; d++) {
    const opt = document.createElement("option");
    opt.value = d; opt.textContent = d;
    sel.appendChild(opt);
  }
}

function renderPlanningTable() {
  if (!LAST_RESULT) return;
  const wrap = document.getElementById("planning-table-wrap");
  const highlight = document.getElementById("p-highlight").value;
  const daysAbbr = I18N[LANG].days_abbr;

  let html = `<table class="planning"><thead><tr>
    <th>${t("col_day")}</th><th>${t("col_date")}</th>
    <th>${t("col_giorno")}</th><th>${t("col_notte")}</th><th>${t("col_riposo")}</th>
    <th>${t("col_chef")}</th><th>${t("col_ferie")}</th><th>${t("col_malattia")}</th>
  </tr></thead><tbody>`;

  for (let d = 1; d <= LAST_RESULT.num_days; d++) {
    const dt = new Date(LAST_RESULT.year, LAST_RESULT.month - 1, d);
    const weekday = (dt.getDay() + 6) % 7; // 0 = lunedì
    const isWeekend = weekday >= 5;
    const rd = LAST_RESULT.days[d];

    const fmt = (ids) => ids
      .slice().sort()
      .map(id => shortName(id))
      .map(s => highlight && s === shortName(highlight) ? `<mark class="hl">${s}</mark>` : s)
      .join(", ");

    const chefName = rd.chef ? employeeName(rd.chef).split(" ")[0] : "";

    html += `<tr class="${isWeekend ? "weekend" : ""}">
      <td>${daysAbbr[weekday]}</td><td>${d}</td>
      <td class="col-giorno">${fmt(rd.giorno)}</td>
      <td class="col-notte">${fmt(rd.notte)}</td>
      <td class="col-riposo">${fmt(rd.riposo)}</td>
      <td class="col-chef">${chefName}</td>
      <td class="col-ferie">${fmt(rd.ferie)}</td>
      <td class="col-malattia">${fmt(rd.malattia)}</td>
    </tr>`;
  }
  html += "</tbody></table>";
  wrap.innerHTML = html;
}

function shortName(id) {
  const e = EMPLOYEES.find(x => x.id === id);
  return e ? e.last_name.slice(0, 3).toUpperCase() : "???";
}

function renderCounts() {
  if (!LAST_RESULT) return;
  const el = document.getElementById("counts-list");
  el.innerHTML = "";
  const counts = {};
  EMPLOYEES.forEach(e => counts[e.id] = { work: 0, night: 0 });
  for (let d = 1; d <= LAST_RESULT.num_days; d++) {
    LAST_RESULT.days[d].giorno.forEach(id => { counts[id] && counts[id].work++; });
    LAST_RESULT.days[d].notte.forEach(id => { counts[id] && (counts[id].work++, counts[id].night++); });
  }
  EMPLOYEES.forEach(e => {
    const target = LAST_RESULT.targets[e.id] ?? 0;
    if (target === 0 && counts[e.id].work === 0) return;
    const c = counts[e.id];
    const ok = c.work === target;
    const row = document.createElement("div");
    row.className = "count-row " + (ok ? "ok" : "warn");
    row.textContent = `${ok ? "✅" : "⚠️"} ${e.last_name.toUpperCase()}: ${c.work}/${target}g (${c.night} notti)`;
    el.appendChild(row);
  });
}

// ---------------------------------------------------------------
// Correzione manuale
// ---------------------------------------------------------------
document.getElementById("correction-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  if (!LAST_RESULT) return;
  const { year, month } = currentPeriod();
  const payload = {
    year, month,
    day: parseInt(document.getElementById("corr-day").value),
    employee_id: document.getElementById("corr-employee").value,
    assignment: document.getElementById("corr-dest").value,
  };
  await api("/planning/override", { method: "POST", body: JSON.stringify(payload) });

  // aggiorna la vista locale senza dover rigenerare tutto il planning
  const rd = LAST_RESULT.days[payload.day];
  ["giorno", "notte", "riposo"].forEach(k => {
    const idx = rd[k].indexOf(payload.employee_id);
    if (idx !== -1) rd[k].splice(idx, 1);
  });
  rd[payload.assignment].push(payload.employee_id);
  renderPlanningTable();
  renderCounts();
});

// ---------------------------------------------------------------
// Export / Stampa
// ---------------------------------------------------------------
document.getElementById("btn-export").addEventListener("click", () => {
  const { year, month } = currentPeriod();
  const chef_present = document.getElementById("p-chef-present").checked;
  window.location.href = `${API}/planning/export?year=${year}&month=${month}&chef_present=${chef_present}&lang=${LANG}`;
});

document.getElementById("btn-print").addEventListener("click", () => window.print());

// ---------------------------------------------------------------
// Avvio
// ---------------------------------------------------------------
(async function init() {
  applyI18n();
  populateMonthYear();
  await loadEmployees();
  await loadConstraints();
})();

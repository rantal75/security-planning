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
    lbl_pref_night: "Pref. Notte", lbl_pref_day: "Pref. Giorno", lbl_pref_33: "Pref. 3-3",
    lbl_titular: "Titolare", lbl_adjoint: "Aggiunto", lbl_equipe: "Equipe", lbl_temp: "Temporaneo",
    lbl_weight: "Peso gerarchico personalizzato (opzionale)",
    btn_save: "Salva dipendente", btn_new: "Nuovo",
    btn_show_advanced: "▸ Opzioni avanzate (preferenze, ruolo)",
    btn_hide_advanced: "▾ Nascondi opzioni avanzate",
    staff_list_title: "Squadra",
    constraints_title: "Ferie, malattie e vincoli manuali",
    lbl_from: "Dal giorno", lbl_to: "Al giorno", lbl_employee: "Dipendente", lbl_type: "Tipo",
    type_ferie: "Ferie", type_malattia: "Malattia", type_riposo: "Riposo forzato", type_chef2: "Sostituzione capo",
    type_recupero: "Recupero straordinario",
    btn_add: "Aggiungi", btn_reset_constraints: "Azzera vincoli del mese",
    recovery_balance_title: "Bilancio giorni di recupero",
    recovery_balance_hint: "Un giorno di straordinario lavorato matura un giorno di recupero. Il bilancio è cumulativo: può essere speso il mese successivo o in quello corrente (vincolo \"Recupero straordinario\" qui sopra).",
    recovery_row_label: "{name}: {balance} disponibili ({earned} maturati, {spent} usati)",
    recovery_empty: "Nessun giorno di straordinario maturato per ora.",
    recovery_pending_title: "Giorni di recupero ancora da scontare",
    recovery_pending_empty: "Nessuno ha giorni di recupero pendenti al momento.",
    insufficient_recovery_balance: "Il dipendente non ha abbastanza giorni di recupero maturati per questo intervallo.",
    lbl_month: "Mese", lbl_year: "Anno", lbl_chef_present: "Capo titolare presente",
    btn_generate: "Genera planning", opt_none: "— Evidenzia nessuno —",
    btn_export: "Esporta Excel", btn_print: "Stampa A4",
    opt_landscape: "Stampa: Orizzontale", opt_portrait: "Stampa: Verticale",
    correction_title: "Correzione manuale", lbl_day: "Giorno", lbl_move_to: "Sposta in",
    type_giorno: "Giornata", type_notte: "Notte",
    btn_apply: "Applica", counts_title: "Riepilogo turni per dipendente",
    col_day: "Giorno", col_date: "Data", col_giorno: "Giornata (07-19)", col_notte: "Notte (19-07)",
    col_riposo: "Riposo", col_chef: "Capo", col_ferie: "Ferie", col_malattia: "Malattia",
    lbl_work_short: "g lav.", lbl_rest_short: "g riposo",
    none_sol: "Nessuna soluzione trovata: i vincoli attuali sono in conflitto tra loro per questo mese.",
    generated_ok: "Planning generato.",
    months: ["Gennaio","Febbraio","Marzo","Aprile","Maggio","Giugno","Luglio","Agosto","Settembre","Ottobre","Novembre","Dicembre"],
    days_abbr: ["Lun","Mar","Mer","Gio","Ven","Sab","Dom"],
    correction_warning_intro: "Questa modifica manuale viola una o più regole del planning:",
    correction_warning_confirm: "Vuoi applicarla comunque?",
    warn_day_after_night: "Il dipendente ha fatto Notte il giorno prima: non dovrebbe fare Giornata subito dopo (riposo insufficiente).",
    warn_night_before_day: "Il giorno dopo il dipendente è già di Giornata: non dovrebbe essere messo di Notte oggi (riposo insufficiente).",
    warn_rest_after_nights: "Il dipendente ha fatto Notte nei due giorni precedenti: dopo un blocco di notti è previsto un riposo, non un turno di lavoro.",
    warn_return_from_absence: "Il dipendente rientra da Ferie/Malattia: il giorno del rientro dovrebbe essere lavorato, non un riposo.",
    warn_4_consecutive_work: "Questa modifica crea una sequenza di 4 o più giorni di lavoro consecutivi senza riposo.",
    warn_4_consecutive_rest: "Questa modifica crea una sequenza di 4 o più giorni di riposo consecutivi.",
    warn_exceeds_work_quota: "Con questa modifica il dipendente arriverebbe a {cur}/{target} giorni di lavoro nel mese: supera il numero di giorni lavorativi dovuti (regola dei \"Sacri 15\").",
    warn_exceeds_rest_quota: "Con questa modifica il dipendente arriverebbe a {cur}/{target} giorni di riposo nel mese: supera il numero di giorni di riposo dovuti.",
    btn_save_planning: "Salva planning",
    planning_saved_ok: "Planning salvato.",
    planning_save_error: "Errore durante il salvataggio del planning.",
    confirm_overwrite_saved: "Questo mese è già stato salvato in precedenza. Vuoi sovrascrivere il planning salvato con quello attuale?",
    viewing_saved_banner: "Stai visionando un planning salvato (sola lettura).",
    btn_exit_view: "Torna al planning corrente",
    saved_title: "Planning salvati",
    lbl_saved_month: "Mese salvato",
    btn_view_saved: "Visualizza",
    saved_empty: "Nessun planning salvato per ora.",
    saved_select_none: "— Seleziona un mese —",
    boundary_warning_title: "Continuità con il mese precedente salvato",
    boundary_night_to_day: "{name}: Notte l'ultimo giorno del mese salvato, Giornata il primo giorno di questo mese — riposo insufficiente.",
    boundary_work_run: "{name}: sommando gli ultimi giorni di lavoro del mese precedente salvato e i primi di questo mese, risultano 4 o più giorni di lavoro consecutivi senza riposo.",
    boundary_rest_run: "{name}: sommando gli ultimi giorni di riposo del mese precedente salvato e i primi di questo mese, risultano 4 o più giorni di riposo consecutivi.",
    btn_reset_overrides: "Azzera correzioni manuali del mese",
    overrides_list_title: "Correzioni manuali attive questo mese",
    override_row_label: "{name} — giorno {day}: {type}",
    overtime_panel_title: "Nessuna soluzione — disponi qualcuno allo straordinario?",
    overtime_panel_hint: "Il motore non trova una soluzione rispettando la quota mensile di tutti. Puoi permettere a uno o più dipendenti di superarla temporaneamente (giorni di straordinario, evidenziati in blu, che maturano un giorno di recupero ciascuno).",
    lbl_overtime_max: "Giorni extra max a testa",
    btn_overtime_regenerate: "Rigenera con straordinario",
    overtime_still_no_solution: "Ancora nessuna soluzione, anche con lo straordinario selezionato. Prova ad aggiungere altri dipendenti disponibili o ad aumentare i giorni extra.",
    overtime_used_ok: "Planning generato con {n} giorno/i di straordinario.",
    diag_intro: "Causa probabile:",
    diag_chef2: "la sostituzione del capo per {name} il giorno {day} è in conflitto con le regole di sicurezza (es. impossibile lavorare Giornata il giorno subito dopo una Notte, o copertura insufficiente quel giorno).",
    diag_riposo: "il riposo forzato per {name} il giorno {day} è in conflitto con le altre regole del mese (es. nessun giorno di riposo isolato, massimo 4 giorni di riposo consecutivi).",
    diag_recupero: "il giorno di recupero per {name} il giorno {day} è in conflitto con le altre regole del mese.",
    diag_category_chef2: "una o più sostituzioni del capo sono in conflitto tra loro o con le regole di sicurezza.",
    diag_category_riposo: "uno o più riposi forzati sono in conflitto tra loro o con le altre regole del mese.",
    diag_category_recupero: "uno o più giorni di recupero sono in conflitto tra loro o con le altre regole del mese.",
  },
  FR: {
    app_title: "Gestion Sécurité", app_sub: "Planning des équipes H24",
    tab_staff: "Personnel", tab_constraints: "Congés & Contraintes", tab_planning: "Planning",
    staff_form_title: "Ajouter / modifier un agent",
    lbl_lastname: "Nom", lbl_firstname: "Prénom",
    lbl_pref_night: "Préf. Nuit", lbl_pref_day: "Préf. Jour", lbl_pref_33: "Préf. 3-3",
    lbl_titular: "Titulaire", lbl_adjoint: "Adjoint", lbl_equipe: "Équipe", lbl_temp: "Temporaire",
    lbl_weight: "Poids hiérarchique personnalisé (optionnel)",
    btn_save: "Enregistrer", btn_new: "Nouveau",
    btn_show_advanced: "▸ Options avancées (préférences, rôle)",
    btn_hide_advanced: "▾ Masquer les options avancées",
    staff_list_title: "Équipe",
    constraints_title: "Congés, maladies et contraintes manuelles",
    lbl_from: "Du jour", lbl_to: "Au jour", lbl_employee: "Agent", lbl_type: "Type",
    type_ferie: "Congés", type_malattia: "Maladie", type_riposo: "Repos forcé", type_chef2: "Remplacement chef",
    type_recupero: "Récupération heures sup.",
    btn_add: "Ajouter", btn_reset_constraints: "Réinitialiser les contraintes du mois",
    recovery_balance_title: "Solde des jours de récupération",
    recovery_balance_hint: "Un jour d'heures supplémentaires travaillé crédite un jour de récupération. Le solde est cumulatif : il peut être utilisé le mois suivant ou le mois en cours (contrainte \"Récupération heures sup.\" ci-dessus).",
    recovery_row_label: "{name} : {balance} disponibles ({earned} acquis, {spent} utilisés)",
    recovery_empty: "Aucun jour d'heures supplémentaires acquis pour l'instant.",
    recovery_pending_title: "Jours de récupération encore à prendre",
    recovery_pending_empty: "Personne n'a de jours de récupération en attente pour le moment.",
    insufficient_recovery_balance: "L'agent n'a pas assez de jours de récupération acquis pour cette période.",
    lbl_month: "Mois", lbl_year: "Année", lbl_chef_present: "Chef titulaire présent",
    btn_generate: "Générer le planning", opt_none: "— Ne rien surligner —",
    btn_export: "Exporter Excel", btn_print: "Imprimer A4",
    opt_landscape: "Impression : Paysage", opt_portrait: "Impression : Portrait",
    correction_title: "Correction manuelle", lbl_day: "Jour", lbl_move_to: "Déplacer vers",
    type_giorno: "Journée", type_notte: "Nuit",
    btn_apply: "Appliquer", counts_title: "Récapitulatif des services par agent",
    col_day: "Jour", col_date: "Date", col_giorno: "Journée (07-19)", col_notte: "Nuit (19-07)",
    col_riposo: "Repos", col_chef: "Chef", col_ferie: "Congés", col_malattia: "Maladie",
    lbl_work_short: "j trav.", lbl_rest_short: "j repos",
    none_sol: "Aucune solution trouvée : les contraintes actuelles sont en conflit pour ce mois.",
    generated_ok: "Planning généré.",
    months: ["Janvier","Février","Mars","Avril","Mai","Juin","Juillet","Août","Septembre","Octobre","Novembre","Décembre"],
    days_abbr: ["Lun","Mar","Mer","Jeu","Ven","Sam","Dim"],
    correction_warning_intro: "Cette modification manuelle viole une ou plusieurs règles du planning :",
    correction_warning_confirm: "Voulez-vous l'appliquer quand même ?",
    warn_day_after_night: "L'agent a fait Nuit la veille : il ne devrait pas faire Journée juste après (repos insuffisant).",
    warn_night_before_day: "Le lendemain l'agent est déjà en Journée : il ne devrait pas être mis de Nuit aujourd'hui (repos insuffisant).",
    warn_rest_after_nights: "L'agent a fait Nuit les deux jours précédents : après un bloc de nuits un repos est prévu, pas un service.",
    warn_return_from_absence: "L'agent revient de Congés/Maladie : le jour du retour devrait être travaillé, pas un repos.",
    warn_4_consecutive_work: "Cette modification crée une séquence de 4 jours de travail consécutifs ou plus sans repos.",
    warn_4_consecutive_rest: "Cette modification crée une séquence de 4 jours de repos consécutifs ou plus.",
    warn_exceeds_work_quota: "Avec cette modification, l'agent atteindrait {cur}/{target} jours de travail ce mois-ci : cela dépasse le nombre de jours dus (règle des \"Sacri 15\").",
    warn_exceeds_rest_quota: "Avec cette modification, l'agent atteindrait {cur}/{target} jours de repos ce mois-ci : cela dépasse le nombre de jours de repos dus.",
    btn_save_planning: "Enregistrer le planning",
    planning_saved_ok: "Planning enregistré.",
    planning_save_error: "Erreur lors de l'enregistrement du planning.",
    confirm_overwrite_saved: "Ce mois a déjà été enregistré. Voulez-vous écraser le planning enregistré avec celui-ci ?",
    viewing_saved_banner: "Vous consultez un planning enregistré (lecture seule).",
    btn_exit_view: "Revenir au planning en cours",
    saved_title: "Plannings enregistrés",
    lbl_saved_month: "Mois enregistré",
    btn_view_saved: "Afficher",
    saved_empty: "Aucun planning enregistré pour l'instant.",
    saved_select_none: "— Sélectionner un mois —",
    boundary_warning_title: "Continuité avec le mois précédent enregistré",
    boundary_night_to_day: "{name} : Nuit le dernier jour du mois enregistré, Journée le premier jour de ce mois — repos insuffisant.",
    boundary_work_run: "{name} : en cumulant les derniers jours de travail du mois précédent enregistré et les premiers de ce mois, cela fait 4 jours de travail consécutifs ou plus sans repos.",
    boundary_rest_run: "{name} : en cumulant les derniers jours de repos du mois précédent enregistré et les premiers de ce mois, cela fait 4 jours de repos consécutifs ou plus.",
    btn_reset_overrides: "Réinitialiser les corrections manuelles du mois",
    overrides_list_title: "Corrections manuelles actives ce mois-ci",
    override_row_label: "{name} — jour {day} : {type}",
    overtime_panel_title: "Aucune solution — rendre quelqu'un disponible pour des heures sup. ?",
    overtime_panel_hint: "Le moteur ne trouve pas de solution en respectant le quota mensuel de tout le monde. Vous pouvez autoriser un ou plusieurs agents à le dépasser temporairement (jours d'heures sup., surlignés en bleu, qui créditent chacun un jour de récupération).",
    lbl_overtime_max: "Jours sup. max par agent",
    btn_overtime_regenerate: "Régénérer avec heures sup.",
    overtime_still_no_solution: "Toujours aucune solution, même avec les heures sup. sélectionnées. Essayez d'ajouter d'autres agents disponibles ou d'augmenter le nombre de jours.",
    overtime_used_ok: "Planning généré avec {n} jour(s) d'heures sup.",
    diag_intro: "Cause probable :",
    diag_chef2: "le remplacement du chef pour {name} le jour {day} est en conflit avec les règles de sécurité (ex. impossible de faire une Journée le lendemain d'une Nuit, ou couverture insuffisante ce jour-là).",
    diag_riposo: "le repos forcé pour {name} le jour {day} est en conflit avec les autres règles du mois (ex. pas de jour de repos isolé, maximum 4 jours de repos consécutifs).",
    diag_recupero: "le jour de récupération pour {name} le jour {day} est en conflit avec les autres règles du mois.",
    diag_category_chef2: "un ou plusieurs remplacements du chef sont en conflit entre eux ou avec les règles de sécurité.",
    diag_category_riposo: "un ou plusieurs repos forcés sont en conflit entre eux ou avec les autres règles du mois.",
    diag_category_recupero: "un ou plusieurs jours de récupération sont en conflit entre eux ou avec les autres règles du mois.",
  },
};

let LANG = "IT";
let EMPLOYEES = [];
let LAST_RESULT = null; // { year, month, num_days, days: {...}, targets, night_targets, riposi_dovuti, overtime_days }
let VIEWING_SAVED = false; // true mentre si visualizza uno snapshot salvato (sola lettura)
let LIVE_RESULT_BACKUP = null; // conserva il planning corrente mentre si visiona uno snapshot

// Selezione ad-hoc (non persistente, valida solo per il mese/generazione
// corrente) dei dipendenti disponibili per lo straordinario — Scelta B
// confermata dall'utente: non un attributo fisso del dipendente, ma una
// scelta fatta al momento, tipicamente dopo un "Nessuna soluzione trovata".
// Viene riportata anche su export ed eventuale salvataggio, così il file
// scaricato e lo snapshot salvato restano coerenti con quanto mostrato a
// schermo.
let OVERTIME_SELECTION = { ids: [], maxExtra: 0 };

function t(key) { return I18N[LANG][key] || key; }

// Restituisce il markup di un'icona SVG dallo sprite in index.html (vedi <defs>).
function icon(name, extraClass = "") {
  return `<svg class="icon ${extraClass}" width="16" height="16" viewBox="0 0 24 24" aria-hidden="true"><use href="#icon-${name}"></use></svg>`;
}

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
    loadRecoveryBalances();
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
    const detail = body.detail;
    // /planning/generate e /planning/save restituiscono un detail
    // strutturato {error, diagnosis} invece di una semplice stringa,
    // così la UI può spiegare la causa probabile del "Nessuna soluzione
    // trovata" invece del solo messaggio generico. Manteniamo comunque
    // e.message come stringa semplice (retrocompatibile con already_saved,
    // insufficient_recovery_balance, ecc.) e aggiungiamo e.detail per chi
    // vuole leggere la diagnosi strutturata.
    const isStructured = detail && typeof detail === "object";
    const err = new Error(isStructured ? (detail.error || `Errore ${res.status}`) : (detail || `Errore ${res.status}`));
    err.detail = detail;
    throw err;
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
    const roleLabels = [];
    const icons = [];
    if (e.is_titular) { icons.push(icon("crown")); roleLabels.push(t("lbl_titular")); }
    if (e.is_adjoint) { icons.push(icon("user-check")); roleLabels.push(t("lbl_adjoint")); }
    if (e.is_equipe) { icons.push(icon("users")); roleLabels.push(t("lbl_equipe")); }
    if (e.is_temp) { icons.push(icon("hourglass")); roleLabels.push(t("lbl_temp")); }
    if (e.pref_night) { icons.push(icon("moon")); roleLabels.push(t("lbl_pref_night")); }
    else if (e.pref_day) { icons.push(icon("sun")); roleLabels.push(t("lbl_pref_day")); }
    if (e.pref_33) { icons.push(icon("repeat")); roleLabels.push(t("lbl_pref_33")); }
    const badge = document.createElement("div");
    badge.className = "emp-badge";
    badge.title = roleLabels.join(" · ");
    badge.innerHTML = `<span>${e.last_name.toUpperCase()}</span><span class="icons">${icons.join("")}</span><span class="del" data-id="${e.id}">${icon("x")}</span>`;
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

// ---------------------------------------------------------------
// Toggle "Opzioni avanzate" (preferenze, ruolo, peso) nel form dipendente
// ---------------------------------------------------------------
function setAdvancedOpen(open) {
  const panel = document.getElementById("emp-advanced");
  const btn = document.getElementById("btn-toggle-advanced");
  panel.classList.toggle("hidden", !open);
  const key = open ? "btn_hide_advanced" : "btn_show_advanced";
  btn.dataset.i18n = key;
  btn.textContent = t(key);
}

document.getElementById("btn-toggle-advanced").addEventListener("click", () => {
  const isHidden = document.getElementById("emp-advanced").classList.contains("hidden");
  setAdvancedOpen(isHidden);
});

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
  // Apri automaticamente le opzioni avanzate se il dipendente ne ha già
  // impostata almeno una, così modificandolo non "sparisce" nulla.
  const hasAdvanced = e.pref_night || e.pref_day || e.pref_33 || e.is_titular
    || e.is_adjoint || e.is_equipe || e.is_temp || e.custom_weight != null;
  setAdvancedOpen(hasAdvanced);
}

document.getElementById("btn-clear-form").addEventListener("click", () => {
  document.getElementById("employee-form").reset();
  document.getElementById("emp-id-hidden").value = "";
  setAdvancedOpen(false);
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
  setAdvancedOpen(false);
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
    row.innerHTML = `<span>${employeeName(g.employee_id)} — ${t("type_" + g.type) || g.type} (${g.days[0]}–${g.days[g.days.length - 1]})</span><span class="del">${icon("x")}</span>`;
    row.querySelector(".del").addEventListener("click", async () => {
      for (const id of g.ids) await api(`/constraints/${id}`, { method: "DELETE" });
      await loadConstraints();
      if (g.type === "recupero") await loadRecoveryBalances();
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
  try {
    await api("/constraints", { method: "POST", body: JSON.stringify(payload) });
  } catch (e) {
    if (e.message === "insufficient_recovery_balance") {
      alert(t("insufficient_recovery_balance"));
      return;
    }
    throw e;
  }
  await loadConstraints();
  if (payload.type === "recupero") await loadRecoveryBalances();
});

document.getElementById("btn-clear-constraints").addEventListener("click", async () => {
  const { year, month } = currentPeriod();
  if (!confirm(t("btn_reset_constraints") + "?")) return;
  await api(`/constraints?year=${year}&month=${month}`, { method: "DELETE" });
  await loadConstraints();
  await loadRecoveryBalances();
});

// ---------------------------------------------------------------
// Bilancio giorni di recupero (cumulativo, su tutti i mesi) — earned da
// giorni di straordinario maturati e salvati, spent da vincoli
// "recupero" già inseriti. Vedi main.py: /api/recovery/balances.
// ---------------------------------------------------------------
function recoveryRowHtml(r) {
  const label = t("recovery_row_label")
    .replace("{name}", employeeName(r.employee_id))
    .replace("{balance}", r.balance)
    .replace("{earned}", r.earned)
    .replace("{spent}", r.spent);
  const cls = "recovery-row" + (r.balance < 0 ? " negative" : "");
  return `<div class="${cls}">${label}</div>`;
}

async function loadRecoveryBalances() {
  const rows = await api("/recovery/balances"); // [{employee_id, earned, spent, balance}]

  // Elenco completo (tab Ferie & Vincoli): chiunque abbia mai maturato
  // straordinario, anche se ormai a saldo zero (storico).
  const fullEl = document.getElementById("recovery-balance-list");
  const withHistory = rows.filter(r => r.earned > 0);
  fullEl.innerHTML = withHistory.length === 0
    ? `<div class="status-msg">${t("recovery_empty")}</div>`
    : withHistory.slice().sort((a, b) => b.balance - a.balance).map(recoveryRowHtml).join("");

  // Elenco "da scontare" (tab Planning): SOLO chi ha ancora un credito
  // residuo positivo — quello che serve controllare mese per mese prima
  // di considerare qualcuno "regolare". Richiesta utente 2026-09-25.
  const pendingEl = document.getElementById("recovery-pending-list");
  if (pendingEl) {
    const pending = rows.filter(r => r.balance > 0).sort((a, b) => b.balance - a.balance);
    pendingEl.innerHTML = pending.length === 0
      ? `<div class="status-msg">${t("recovery_pending_empty")}</div>`
      : pending.map(recoveryRowHtml).join("");
  }
}

// ---------------------------------------------------------------
// Correzioni manuali attive per il mese — elenco e cancellazione.
// MODIFICA (2026-09-24): prima non esisteva alcun modo di rimuovere una
// correzione manuale una volta salvata: ogni "Genera planning" la
// riapplicava per sempre, anche da sessioni di test passate, facendo
// accumulare nel tempo sforamenti della quota mensile senza che l'utente
// avesse toccato nulla di recente. Ora le correzioni attive sono visibili
// e cancellabili, singolarmente o tutte insieme, come già avviene per i
// vincoli (ferie/malattia/riposo).
// ---------------------------------------------------------------
async function loadOverrides() {
  const { year, month } = currentPeriod();
  const rows = await api(`/planning/overrides?year=${year}&month=${month}`);
  const el = document.getElementById("override-list");
  el.innerHTML = "";
  rows
    .slice()
    .sort((a, b) => a.day - b.day)
    .forEach(o => {
      const row = document.createElement("div");
      row.className = "constraint-row";
      const label = t("override_row_label")
        .replace("{name}", employeeName(o.employee_id))
        .replace("{day}", o.day)
        .replace("{type}", t("type_" + o.assignment) || o.assignment);
      row.innerHTML = `<span>${label}</span><span class="del">${icon("x")}</span>`;
      row.querySelector(".del").addEventListener("click", async () => {
        await api(`/planning/override/${o.id}`, { method: "DELETE" });
        await loadOverrides();
      });
      el.appendChild(row);
    });
  return rows;
}

document.getElementById("btn-clear-overrides").addEventListener("click", async () => {
  const { year, month } = currentPeriod();
  if (!confirm(t("btn_reset_overrides") + "?")) return;
  await api(`/planning/overrides?year=${year}&month=${month}`, { method: "DELETE" });
  await loadOverrides();
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

document.getElementById("p-month").addEventListener("change", () => { loadConstraints(); loadOverrides(); });
document.getElementById("p-year").addEventListener("change", () => { loadConstraints(); loadOverrides(); });

// ---------------------------------------------------------------
// Generazione planning
// ---------------------------------------------------------------
document.getElementById("btn-generate").addEventListener("click", async () => {
  // Una nuova generazione "pulita" parte sempre senza straordinario: la
  // selezione precedente (se c'era) riguardava un tentativo passato.
  OVERTIME_SELECTION = { ids: [], maxExtra: 0 };
  hideOvertimePanel();
  await doGenerate();
});

async function doGenerate() {
  const { year, month } = currentPeriod();
  const chef_present = document.getElementById("p-chef-present").checked;
  const statusEl = document.getElementById("planning-status");
  statusEl.textContent = "…";
  statusEl.className = "status-msg";
  document.getElementById("save-status").textContent = "";
  exitSavedView(); // una nuova generazione abbandona sempre la vista storica
  try {
    LAST_RESULT = await api("/planning/generate", {
      method: "POST",
      body: JSON.stringify({
        year, month, chef_present,
        overtime_employee_ids: OVERTIME_SELECTION.ids,
        overtime_max_extra: OVERTIME_SELECTION.maxExtra,
      }),
    });
    const otCount = Object.keys(LAST_RESULT.overtime_days || {}).length;
    statusEl.textContent = otCount > 0 ? t("overtime_used_ok").replace("{n}", otCount) : t("generated_ok");
    statusEl.className = "status-msg ok";
    hideOvertimePanel();
    populateHighlightSelect();
    populateCorrectionDaySelect();
    renderPlanningTable();
    renderCounts();
    await loadOverrides();
    await checkMonthBoundary();
    await loadRecoveryBalances();
    return true;
  } catch (e) {
    const base = OVERTIME_SELECTION.ids.length > 0 ? t("overtime_still_no_solution") : t("none_sol");
    statusEl.textContent = base + formatDiagnosis(e.detail && e.detail.diagnosis);
    statusEl.className = "status-msg error";
    showOvertimePanel();
    return false;
  }
}

// Traduce la diagnosi strutturata restituita dal backend quando la
// generazione fallisce (vedi engine.py ShiftEngine._diagnose e main.py
// _generate_full) in una spiegazione leggibile, invece del solo
// "Nessuna soluzione trovata" — richiesta utente 2026-09-25.
function formatDiagnosis(diagnosis) {
  if (!diagnosis || diagnosis.length === 0) return "";
  const lines = [];
  diagnosis.forEach(finding => {
    if (finding.culprits && finding.culprits.length > 0) {
      finding.culprits.forEach(c => {
        lines.push(t("diag_" + finding.type)
          .replace("{name}", employeeName(c.employee_id))
          .replace("{day}", c.day));
      });
    } else {
      lines.push(t("diag_category_" + finding.type));
    }
  });
  if (lines.length === 0) return "";
  return "\n" + t("diag_intro") + "\n" + lines.map(l => "• " + l).join("\n");
}

// ---------------------------------------------------------------
// Pannello straordinario: mostrato quando la generazione fallisce, per
// permettere di rendere disponibili uno o più dipendenti oltre la quota
// mensile (vedi engine.py, meccanismo "straordinario").
// ---------------------------------------------------------------
function populateOvertimeEmpList() {
  const el = document.getElementById("overtime-emp-list");
  el.innerHTML = EMPLOYEES.filter(e => !e.is_titular).map(e => `
    <label class="chip">
      <input type="checkbox" class="overtime-check" value="${e.id}" ${OVERTIME_SELECTION.ids.includes(e.id) ? "checked" : ""}>
      <span>${e.last_name.toUpperCase()}</span>
    </label>
  `).join("");
}

function showOvertimePanel() {
  populateOvertimeEmpList();
  document.getElementById("overtime-max-extra").value = OVERTIME_SELECTION.maxExtra || 2;
  document.getElementById("overtime-panel").classList.remove("hidden");
}

function hideOvertimePanel() {
  document.getElementById("overtime-panel").classList.add("hidden");
}

document.getElementById("btn-overtime-regenerate").addEventListener("click", async () => {
  const ids = Array.from(document.querySelectorAll(".overtime-check:checked")).map(c => c.value);
  const maxExtra = parseInt(document.getElementById("overtime-max-extra").value) || 0;
  if (ids.length === 0 || maxExtra <= 0) return;
  OVERTIME_SELECTION = { ids, maxExtra };
  await doGenerate();
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
    const otToday = overtimeIdsForDay(d);

    const fmt = (ids) => ids
      .slice().sort()
      .map(id => {
        let s = shortName(id);
        if (highlight && s === shortName(highlight)) s = `<mark class="hl">${s}</mark>`;
        if (otToday.has(id)) s = `<span class="ot-name" title="${t("overtime_panel_title")}">${s}</span>`;
        return s;
      })
      .join(",");

    const chefName = rd.chef ? shortName(rd.chef) : "";

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

// Set di employee_id in straordinario per un dato giorno, da
// LAST_RESULT.overtime_days = {employee_id: [giorni]}.
function overtimeIdsForDay(day) {
  const out = new Set();
  const od = LAST_RESULT.overtime_days || {};
  Object.keys(od).forEach(eid => { if (od[eid].includes(day)) out.add(eid); });
  return out;
}

function shortName(id) {
  const e = EMPLOYEES.find(x => x.id === id);
  if (!e) return "??";
  // short_code arriva dal backend (main.py._compute_short_codes): di
  // norma 2 lettere, allungata solo per chi altrimenti collide con un
  // collega (es. BERTRAND/BEJAOUI -> "BER"/"BEJ") — unica fonte di
  // verità, stessa sigla usata anche nell'export Excel/stampa.
  return e.short_code || e.last_name.slice(0, 2).toUpperCase();
}

function renderCounts() {
  if (!LAST_RESULT) return;
  const el = document.getElementById("counts-list");
  el.innerHTML = "";
  const counts = {};
  EMPLOYEES.forEach(e => counts[e.id] = { work: 0, night: 0, rest: 0 });
  for (let d = 1; d <= LAST_RESULT.num_days; d++) {
    LAST_RESULT.days[d].giorno.forEach(id => { counts[id] && counts[id].work++; });
    LAST_RESULT.days[d].notte.forEach(id => { counts[id] && (counts[id].work++, counts[id].night++); });
    LAST_RESULT.days[d].riposo.forEach(id => { counts[id] && counts[id].rest++; });
  }
  EMPLOYEES.forEach(e => {
    const target = LAST_RESULT.targets[e.id] ?? 0;
    // Giorni di riposo dovuti nel mese (formula "Sacri 15" pro-rata, esclusi
    // ferie/malattia): varia se il dipendente ha assenze nel mese.
    const restDue = (LAST_RESULT.riposi_dovuti && LAST_RESULT.riposi_dovuti[e.id]) ?? 0;
    if (target === 0 && counts[e.id].work === 0) return;
    const c = counts[e.id];
    const otDays = (LAST_RESULT.overtime_days && LAST_RESULT.overtime_days[e.id]) || [];
    // Con lo straordinario il target di LAVORO viene superato
    // "legittimamente" — e ogni giorno extra lavorato è, per costruzione,
    // un giorno che altrimenti sarebbe stato di riposo (lavoro + riposo +
    // ferie + malattia = giorni del mese, sempre). Quindi anche la quota
    // di RIPOSO attesa va scontata degli stessi giorni, altrimenti il
    // riepilogo segnala come "fuori quota" un dipendente che in realtà è
    // perfettamente in linea (bug corretto il 2026-09-25).
    const expectedWork = target + otDays.length;
    const expectedRest = restDue - otDays.length;
    const ok = c.work === expectedWork && c.rest === expectedRest;
    const row = document.createElement("div");
    row.className = "count-row " + (ok ? "ok" : "warn");
    const otBadge = otDays.length > 0 ? `<span class="ot-badge">+${otDays.length}</span>` : "";
    row.innerHTML = `<span class="label">${icon(ok ? "check-circle" : "warning")}${e.last_name.toUpperCase()}</span><span class="figures">${c.work}/${target}${otBadge}${t("lbl_work_short")} (${c.night} notti) — ${c.rest}/${restDue}${t("lbl_rest_short")}</span>`;
    el.appendChild(row);
  });
}

// ---------------------------------------------------------------
// Salvataggio planning e archivio mesi salvati
// ---------------------------------------------------------------

function monthLabel(year, month) {
  return `${I18N[LANG].months[month - 1]} ${year}`;
}

function formatSavedAt(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d)) return "";
  return d.toLocaleString(LANG === "IT" ? "it-IT" : "fr-FR", {
    day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

async function loadSavedList() {
  const rows = await api("/planning/saved"); // [{year, month, num_days, chef_present, saved_at}]
  const sel = document.getElementById("saved-select");
  const emptyEl = document.getElementById("saved-empty");
  sel.innerHTML = rows.map(r =>
    `<option value="${r.year}-${r.month}">${monthLabel(r.year, r.month)} — ${formatSavedAt(r.saved_at)}</option>`
  ).join("");
  emptyEl.style.display = rows.length ? "none" : "";
  sel.style.display = rows.length ? "" : "none";
  document.getElementById("btn-view-saved").disabled = rows.length === 0;
  return rows;
}

document.getElementById("btn-save-planning").addEventListener("click", async () => {
  if (!LAST_RESULT || VIEWING_SAVED) return;
  const { year, month } = currentPeriod();
  const chef_present = document.getElementById("p-chef-present").checked;
  const saveStatus = document.getElementById("save-status");
  saveStatus.textContent = "…";
  saveStatus.className = "status-msg";

  async function doSave(confirmOverwrite) {
    return api("/planning/save", {
      method: "POST",
      body: JSON.stringify({
        year, month, chef_present, confirm_overwrite: confirmOverwrite,
        overtime_employee_ids: OVERTIME_SELECTION.ids,
        overtime_max_extra: OVERTIME_SELECTION.maxExtra,
      }),
    });
  }

  try {
    try {
      await doSave(false);
    } catch (e) {
      if (e.message === "already_saved") {
        if (!confirm(t("confirm_overwrite_saved"))) {
          saveStatus.textContent = "";
          return;
        }
        await doSave(true);
      } else {
        throw e;
      }
    }
    saveStatus.textContent = t("planning_saved_ok");
    saveStatus.className = "status-msg ok";
    await loadSavedList();
    // Il salvataggio azzera lato server le correzioni manuali del mese
    // (sono ormai congelate nello snapshot): aggiorna anche qui l'elenco,
    // che risulterà vuoto.
    await loadOverrides();
    // Il salvataggio ricalcola anche il bilancio giorni di recupero
    // (nuovi crediti da eventuale straordinario in questo mese).
    await loadRecoveryBalances();
  } catch (e) {
    saveStatus.textContent = t("planning_save_error") + formatDiagnosis(e.detail && e.detail.diagnosis);
    saveStatus.className = "status-msg error";
  }
});

function setViewingSaved(on) {
  VIEWING_SAVED = on;
  document.getElementById("view-saved-banner").classList.toggle("hidden", !on);
  // In sola lettura: niente correzioni, salvataggi o export su uno storico.
  document.querySelectorAll("#correction-form input, #correction-form select, #correction-form button")
    .forEach(el => { el.disabled = on; });
  document.getElementById("btn-save-planning").disabled = on;
  document.getElementById("btn-export").disabled = on;
  document.getElementById("btn-clear-overrides").disabled = on;
}

document.getElementById("btn-view-saved").addEventListener("click", async () => {
  const sel = document.getElementById("saved-select");
  if (!sel.value) return;
  const [y, m] = sel.value.split("-").map(Number);
  try {
    const saved = await api(`/planning/saved/${y}/${m}`);
    if (!VIEWING_SAVED) LIVE_RESULT_BACKUP = LAST_RESULT;
    LAST_RESULT = saved;
    setViewingSaved(true);
    populateHighlightSelect();
    renderPlanningTable();
    renderCounts();
    document.getElementById("boundary-warnings").classList.add("hidden");
  } catch (e) {
    // nessun planning salvato per quel mese (non dovrebbe accadere, la
    // select è popolata solo con mesi effettivamente salvati)
  }
});

function exitSavedView() {
  if (!VIEWING_SAVED) return;
  LAST_RESULT = LIVE_RESULT_BACKUP;
  LIVE_RESULT_BACKUP = null;
  setViewingSaved(false);
  populateHighlightSelect();
  populateCorrectionDaySelect();
  if (LAST_RESULT) {
    renderPlanningTable();
    renderCounts();
  } else {
    document.getElementById("planning-table-wrap").innerHTML = "";
    document.getElementById("counts-list").innerHTML = "";
  }
}

document.getElementById("btn-exit-view").addEventListener("click", exitSavedView);

// ---------------------------------------------------------------
// Continuità tra mesi: confronta il fine mese precedente SALVATO con
// l'inizio del mese appena generato, per segnalare (non bloccare) le
// stesse regole fisiche già controllate nelle correzioni manuali, ma a
// cavallo tra due generazioni separate — il motore genera un mese alla
// volta e non "vede" quello prima o dopo.
// ---------------------------------------------------------------
async function checkMonthBoundary() {
  const box = document.getElementById("boundary-warnings");
  box.classList.add("hidden");
  box.innerHTML = "";
  if (!LAST_RESULT) return;

  let prevYear = LAST_RESULT.year, prevMonth = LAST_RESULT.month - 1;
  if (prevMonth < 1) { prevMonth = 12; prevYear -= 1; }

  let prev;
  try {
    prev = await api(`/planning/saved/${prevYear}/${prevMonth}`);
  } catch (e) {
    return; // mese precedente non salvato: nessun confronto possibile
  }

  const issues = [];
  EMPLOYEES.forEach(e => {
    const eid = e.id;
    const lastOfPrev = prev.days[prev.num_days] ? getAssignmentFrom(prev, prev.num_days, eid) : null;
    const secondLastOfPrev = prev.num_days > 1 ? getAssignmentFrom(prev, prev.num_days - 1, eid) : null;
    const thirdLastOfPrev = prev.num_days > 2 ? getAssignmentFrom(prev, prev.num_days - 2, eid) : null;
    const firstOfNew = getAssignment(1, eid);
    const secondOfNew = LAST_RESULT.num_days > 1 ? getAssignment(2, eid) : null;
    const thirdOfNew = LAST_RESULT.num_days > 2 ? getAssignment(3, eid) : null;

    if (lastOfPrev === "notte" && firstOfNew === "giorno") {
      issues.push(t("boundary_night_to_day").replace("{name}", e.last_name.toUpperCase()));
    }

    // Sequenza di lavoro/riposo a cavallo: fino a 3 giorni finali del mese
    // salvato + fino a 3 giorni iniziali del nuovo mese, stessa logica di
    // checkRuleViolations() ma su due generazioni separate.
    const seq = [thirdLastOfPrev, secondLastOfPrev, lastOfPrev, firstOfNew, secondOfNew, thirdOfNew];
    let workRun = 0, restRun = 0, maxWorkRun = 0, maxRestRun = 0;
    seq.forEach(a => {
      workRun = isWorkAssignment(a) ? workRun + 1 : 0;
      restRun = a === "riposo" ? restRun + 1 : 0;
      maxWorkRun = Math.max(maxWorkRun, workRun);
      maxRestRun = Math.max(maxRestRun, restRun);
    });
    if (maxWorkRun >= 4) issues.push(t("boundary_work_run").replace("{name}", e.last_name.toUpperCase()));
    if (maxRestRun >= 4) issues.push(t("boundary_rest_run").replace("{name}", e.last_name.toUpperCase()));
  });

  if (issues.length > 0) {
    box.innerHTML = `<strong>${icon("warning")}${t("boundary_warning_title")}</strong><ul>${issues.map(i => `<li>${i}</li>`).join("")}</ul>`;
    box.classList.remove("hidden");
  }
}

function getAssignmentFrom(result, day, eid) {
  const rd = result.days[day];
  if (!rd) return null;
  for (const k of ["giorno", "notte", "riposo", "ferie", "malattia"]) {
    if (rd[k] && rd[k].includes(eid)) return k;
  }
  return null;
}

// ---------------------------------------------------------------
// Correzione manuale — controllo regole prima di applicare
// ---------------------------------------------------------------

// Legge il tipo di assegnazione di un dipendente in un dato giorno dal
// risultato corrente (LAST_RESULT.days). Ritorna "giorno" | "notte" |
// "riposo" | "ferie" | "malattia" | null (giorno fuori mese / non trovato).
function getAssignment(day, eid) {
  const rd = LAST_RESULT.days[day];
  if (!rd) return null;
  for (const k of ["giorno", "notte", "riposo", "ferie", "malattia"]) {
    if (rd[k] && rd[k].includes(eid)) return k;
  }
  return null;
}

function isWorkAssignment(a) {
  return a === "giorno" || a === "notte";
}

// Conta i giorni di lavoro e di riposo effettivamente assegnati a un
// dipendente in tutto il mese corrente (LAST_RESULT.days), come mostrato
// nel riepilogo "Riepilogo turni per dipendente".
function countMonthlyTotals(eid) {
  let work = 0, rest = 0;
  for (let d = 1; d <= LAST_RESULT.num_days; d++) {
    const a = getAssignment(d, eid);
    if (isWorkAssignment(a)) work++;
    else if (a === "riposo") rest++;
  }
  return { work, rest };
}

// Verifica, usando le stesse regole "dure" del motore (engine.py), se
// assegnare `newAssignment` a `eid` nel giorno `day` violerebbe una regola.
// Ritorna un array di chiavi I18N (warn_...) — vuoto se nessuna violazione.
// Il controllo è solo informativo: la decisione finale resta all'utente.
function checkRuleViolations(day, eid, newAssignment) {
  const warnings = [];
  const numDays = LAST_RESULT.num_days;

  const prevA = day - 1 >= 1 ? getAssignment(day - 1, eid) : null;
  const nextA = day + 1 <= numDays ? getAssignment(day + 1, eid) : null;
  const prev2A = day - 2 >= 1 ? getAssignment(day - 2, eid) : null;

  // 1. Giornata subito dopo una Notte: riposo insufficiente.
  if (prevA === "notte" && newAssignment === "giorno") {
    warnings.push("warn_day_after_night");
  }
  // 1b. Notte oggi, ma il giorno dopo è già Giornata per lo stesso dipendente.
  if (newAssignment === "notte" && nextA === "giorno") {
    warnings.push("warn_night_before_day");
  }

  // 2. Dopo un blocco di due Notti consecutive è previsto un riposo, non
  //    un altro turno di lavoro.
  if (prev2A === "notte" && prevA === "notte" && isWorkAssignment(newAssignment)) {
    warnings.push("warn_rest_after_nights");
  }

  // 3. Rientro da Ferie/Malattia: il giorno del rientro va lavorato, non
  //    messo a riposo.
  if ((prevA === "ferie" || prevA === "malattia") && newAssignment === "riposo") {
    warnings.push("warn_return_from_absence");
  }

  // 4. Nessuna sequenza di 4+ giorni di lavoro (giorno/notte) o di 4+
  //    giorni di riposo consecutivi, considerando l'assegnazione ipotetica.
  const seq = [];
  for (let d = Math.max(1, day - 3); d <= Math.min(numDays, day + 3); d++) {
    seq.push(d === day ? newAssignment : getAssignment(d, eid));
  }
  let workRun = 0, restRun = 0, maxWorkRun = 0, maxRestRun = 0;
  seq.forEach((a) => {
    workRun = isWorkAssignment(a) ? workRun + 1 : 0;
    restRun = a === "riposo" ? restRun + 1 : 0;
    maxWorkRun = Math.max(maxWorkRun, workRun);
    maxRestRun = Math.max(maxRestRun, restRun);
  });
  if (maxWorkRun >= 4) warnings.push("warn_4_consecutive_work");
  if (maxRestRun >= 4) warnings.push("warn_4_consecutive_rest");

  // 5. Conteggio mensile: la formula dei "Sacri 15" fissa un numero preciso
  //    di giorni di lavoro/riposo dovuti nel mese. Il motore lo rispetta
  //    sempre alla generazione (vincolo rigido), ma una correzione manuale
  //    aggira quel vincolo spostando un singolo giorno: qui verifichiamo
  //    se il totale del mese, dopo la modifica, sforerebbe la quota.
  const target = LAST_RESULT.targets ? (LAST_RESULT.targets[eid] ?? null) : null;
  const restDue = LAST_RESULT.riposi_dovuti ? (LAST_RESULT.riposi_dovuti[eid] ?? null) : null;
  if (target != null || restDue != null) {
    const totals = countMonthlyTotals(eid);
    // Rimuove il conteggio del giorno che si sta modificando (l'assegnazione
    // attuale, prima della modifica) e aggiunge la nuova ipotetica.
    const before = getAssignment(day, eid);
    if (isWorkAssignment(before)) totals.work--;
    else if (before === "riposo") totals.rest--;
    if (isWorkAssignment(newAssignment)) totals.work++;
    else if (newAssignment === "riposo") totals.rest++;

    if (target != null && totals.work > target) {
      warnings.push({ key: "warn_exceeds_work_quota", cur: totals.work, target });
    }
    if (restDue != null && totals.rest > restDue) {
      warnings.push({ key: "warn_exceeds_rest_quota", cur: totals.rest, target: restDue });
    }
  }

  return warnings;
}

// Traduce una voce di avviso (chiave semplice o oggetto con placeholder
// {cur}/{target}) nel testo da mostrare nel popup.
function formatWarning(w) {
  if (typeof w === "string") return t(w);
  return t(w.key).replace("{cur}", w.cur).replace("{target}", w.target);
}

document.getElementById("correction-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  if (!LAST_RESULT || VIEWING_SAVED) return;
  const { year, month } = currentPeriod();
  const payload = {
    year, month,
    day: parseInt(document.getElementById("corr-day").value),
    employee_id: document.getElementById("corr-employee").value,
    assignment: document.getElementById("corr-dest").value,
  };

  const warnings = checkRuleViolations(payload.day, payload.employee_id, payload.assignment);
  if (warnings.length > 0) {
    const msg = t("correction_warning_intro") + "\n\n"
      + warnings.map(w => "• " + formatWarning(w)).join("\n")
      + "\n\n" + t("correction_warning_confirm");
    if (!confirm(msg)) return;
  }

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
  await loadOverrides();
});

// ---------------------------------------------------------------
// Export / Stampa
// ---------------------------------------------------------------
document.getElementById("btn-export").addEventListener("click", () => {
  const { year, month } = currentPeriod();
  const chef_present = document.getElementById("p-chef-present").checked;
  const otIds = OVERTIME_SELECTION.ids.join(",");
  window.location.href = `${API}/planning/export?year=${year}&month=${month}&chef_present=${chef_present}&lang=${LANG}`
    + `&overtime_employee_ids=${encodeURIComponent(otIds)}&overtime_max_extra=${OVERTIME_SELECTION.maxExtra}`;
});

// Calcola font-size e padding delle celle per la stampa. Il comportamento
// dipende dall'orientamento scelto:
// - Orizzontale (A4 landscape, il layout originale): la larghezza basta
//   per stare su una riga sola, quindi qui il vincolo è l'ALTEZZA — un
//   mese più corto ha più spazio verticale libero e può usare un font più
//   grande restando su una pagina sola. Soglie tarate su un'area utile di
//   stampa di ~733px, line-height 1.15, bordi 1px/riga.
// - Verticale (A4 portrait, MODIFICA 2026-09-25, richiesta utente): qui è
//   la LARGHEZZA a mancare (circa il 70% di quella orizzontale), quindi le
//   celle con più nomi (tipicamente Riposo) vanno spesso a capo su più
//   righe — combinato con le sigle a 2 lettere e le virgole senza spazio
//   (vedi shortName()/fmt() sopra) per ridurre quanto possibile quanto
//   spesso serve andare a capo. Non si forza più una pagina sola: con 31
//   giorni e una squadra numerosa è realistico che serva una seconda
//   pagina, ed è preferibile a un font illeggibile.
function applyPrintSizing() {
  const numDays = LAST_RESULT ? LAST_RESULT.num_days : 31;
  const portrait = document.getElementById("p-print-orientation").value === "portrait";
  let fontSize, padV, padH;
  if (portrait) {
    fontSize = "9.5px"; padV = "2.5px"; padH = "3px";
  } else if (numDays <= 28) {
    fontSize = "12px"; padV = "3.5px"; padH = "6px";
  } else if (numDays <= 30) {
    fontSize = "11.5px"; padV = "3.5px"; padH = "6px";
  } else {
    fontSize = "11px"; padV = "3px"; padH = "5px"; // 31 giorni: il caso più stretto
  }
  const root = document.documentElement.style;
  root.setProperty("--print-font-size", fontSize);
  root.setProperty("--print-cell-pad-v", padV);
  root.setProperty("--print-cell-pad-h", padH);
  document.querySelector(".shell").classList.toggle("print-portrait", portrait);
}

document.getElementById("btn-print").addEventListener("click", () => {
  applyPrintSizing();
  window.print();
});

// ---------------------------------------------------------------
// Avvio
// ---------------------------------------------------------------
(async function init() {
  applyI18n();
  populateMonthYear();
  await loadEmployees();
  await loadConstraints();
  await loadOverrides();
  await loadSavedList();
  await loadRecoveryBalances();
})();
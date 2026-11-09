"""excel_export.py — Genera il file .xlsx del planning (A4 orizzontale, su
un'unica pagina).

MODIFICA (2026-09-25): supporto per l'evidenziazione in blu dei giorni di
straordinario (vedi engine.py / main.py, meccanismo "straordinario"). Le
celle Giornata/Notte non vengono più scritte tramite pandas.to_excel (che
applica un formato uniforme per colonna): sono scritte cella per cella, in
modo da poter colorare di blu solo il nome del dipendente interessato
all'interno di una cella che può contenere più nomi (write_rich_string).
"""

import io
from calendar import monthrange
from datetime import date

DAYS_ABBR = {
    "IT": ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"],
    "FR": ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"],
}

COLS = {
    "IT": ["Giorno", "Data", "Giornata (07-19)", "Notte (19-07)", "Riposo", "Capo", "Ferie", "Malattia"],
    "FR": ["Jour", "Date", "Journée (07-19)", "Nuit (19-07)", "Repos", "Chef", "Congés", "Maladie"],
}

COL_WIDTHS = [10, 5, 25, 20, 25, 10, 15, 15]


def short_name(employees_by_id: dict, eid: str) -> str:
    """Sigla del dipendente: usa 'short_code' se presente nel dict
    (calcolato una volta sola su tutta la squadra da
    main.py._compute_short_codes — 2 lettere di default, allungata solo
    per chi altrimenti collide con un collega), altrimenti ricade sul
    troncamento a 2 lettere (compatibilità se il campo manca)."""
    if str(eid).startswith("BOSS:"):  # v25.9: esterno agenzia Boss
        return "BOSS"
    e = employees_by_id.get(eid)
    if not e:
        return "??"
    return e.get("short_code") or (e.get("last_name") or "")[:2].upper()


def build_excel(year: int, month: int, days_out: dict, employees: list[dict], lang: str = "IT",
                 overtime_days: dict | None = None) -> bytes:
    """overtime_days: {employee_id: [giorni]} — giorni in cui quel
    dipendente ha lavorato in straordinario (oltre la quota mensile). Il
    suo nome viene evidenziato in blu nella cella Giornata/Notte di quei
    giorni specifici."""
    employees_by_id = {e["id"]: e for e in employees}
    num_days = monthrange(year, month)[1]
    cols = COLS.get(lang, COLS["IT"])
    abbr = DAYS_ABBR.get(lang, DAYS_ABBR["IT"])

    # {giorno: set(employee_id)} — lookup rapido "è straordinario oggi?"
    overtime_by_day: dict[int, set] = {}
    for eid, days in (overtime_days or {}).items():
        for d in days:
            overtime_by_day.setdefault(d, set()).add(eid)

    import xlsxwriter  # import locale: usato solo qui, evita dipendenza globale non necessaria

    buffer = io.BytesIO()
    workbook = xlsxwriter.Workbook(buffer, {"in_memory": True})
    worksheet = workbook.add_worksheet("Planning")

    cell_fmt = workbook.add_format({"border": 1, "text_wrap": True, "valign": "top"})
    overtime_fmt = workbook.add_format({
        "border": 1, "text_wrap": True, "valign": "top",
        # Verde (non blu): il blu è già il colore della colonna Notte,
        # confonderebbe i due significati a colpo d'occhio.
        "font_color": "#1B7A3D", "bold": True,
    })
    header_fmt = workbook.add_format({"border": 1, "bold": True, "bg_color": "#F2F2F2"})

    for i, width in enumerate(COL_WIDTHS):
        worksheet.set_column(i, i, width)
    for i, col_name in enumerate(cols):
        worksheet.write(0, i, col_name, header_fmt)

    def write_names_cell(row: int, col: int, ids: list[str], overtime_ids_today: set):
        if not ids:
            worksheet.write(row, col, "", cell_fmt)
            return
        pairs = sorted(((short_name(employees_by_id, eid), eid) for eid in ids), key=lambda p: p[0])
        if len(pairs) == 1:
            # xlsxwriter.write_rich_string() richiede ALMENO 2 coppie
            # formato/stringa (a parte l'eventuale formato finale della
            # cella): con un solo nome non c'è comunque nulla da
            # "mischiare" all'interno della cella, quindi si scrive
            # normalmente con il formato giusto (blu se straordinario).
            name, eid = pairs[0]
            fmt = overtime_fmt if eid in overtime_ids_today else cell_fmt
            worksheet.write(row, col, name, fmt)
            return
        if not any(eid in overtime_ids_today for _, eid in pairs):
            worksheet.write(row, col, ",".join(n for n, _ in pairs), cell_fmt)
            return
        # Due o più nomi in questa cella, almeno uno in straordinario:
        # costruiamo una rich string per colorare di blu solo quello,
        # lasciando gli altri nomi nel formato normale. Virgola SENZA
        # spazio (richiesta utente 2026-09-25, per stringere le colonne).
        parts = []
        for i, (name, eid) in enumerate(pairs):
            fmt = overtime_fmt if eid in overtime_ids_today else cell_fmt
            if i > 0:
                parts.append(cell_fmt)
                parts.append(",")
            parts.append(fmt)
            parts.append(name)
        worksheet.write_rich_string(row, col, *parts, cell_fmt)

    for d in range(1, num_days + 1):
        row = d  # riga 0 = intestazione
        dt = date(year, month, d)
        res_d = days_out[d]
        chef_name = short_name(employees_by_id, res_d["chef"]) if res_d["chef"] else ""
        overtime_today = overtime_by_day.get(d, set())

        worksheet.write(row, 0, abbr[dt.weekday()], cell_fmt)
        worksheet.write(row, 1, d, cell_fmt)
        write_names_cell(row, 2, res_d["giorno"], overtime_today)
        write_names_cell(row, 3, res_d["notte"], overtime_today)
        worksheet.write(row, 4, ",".join(sorted(short_name(employees_by_id, e) for e in res_d["riposo"])), cell_fmt)
        worksheet.write(row, 5, chef_name, cell_fmt)
        worksheet.write(row, 6, ",".join(sorted(short_name(employees_by_id, e) for e in res_d["ferie"])), cell_fmt)
        worksheet.write(row, 7, ",".join(sorted(short_name(employees_by_id, e) for e in res_d["malattia"])), cell_fmt)

    worksheet.set_landscape()
    worksheet.set_paper(9)  # A4

    # Margini ridotti per sfruttare l'intera pagina prima che Excel debba
    # ricorrere al ridimensionamento automatico (pollici).
    worksheet.set_margins(left=0.3, right=0.3, top=0.35, bottom=0.35)
    worksheet.set_header("")
    worksheet.set_footer("")

    # fit_to_pages(1, 1) vincola ENTRAMBE le dimensioni a una sola pagina:
    # Excel calcola da solo la scala minima necessaria.
    worksheet.fit_to_pages(1, 1)

    # Centra la tabella sulla pagina stampata, invece di lasciarla ancorata
    # in alto a sinistra con spazio vuoto attorno.
    worksheet.center_horizontally()
    worksheet.center_vertically()

    workbook.close()
    buffer.seek(0)
    return buffer.read()

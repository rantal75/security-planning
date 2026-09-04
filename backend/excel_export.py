"""excel_export.py — Genera il file .xlsx del planning (A4 orizzontale)."""

import io
from calendar import monthrange
from datetime import date

import pandas as pd

DAYS_ABBR = {
    "IT": ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"],
    "FR": ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"],
}

COLS = {
    "IT": ["Giorno", "Data", "Giornata (07-19)", "Notte (19-07)", "Riposo", "Capo", "Ferie", "Malattia"],
    "FR": ["Jour", "Date", "Journée (07-19)", "Nuit (19-07)", "Repos", "Chef", "Congés", "Maladie"],
}


def short_name(employees_by_id: dict, eid: str) -> str:
    e = employees_by_id.get(eid)
    return e["last_name"][:3].upper() if e else "???"


def build_excel(year: int, month: int, days_out: dict, employees: list[dict], lang: str = "IT") -> bytes:
    employees_by_id = {e["id"]: e for e in employees}
    num_days = monthrange(year, month)[1]
    cols = COLS.get(lang, COLS["IT"])
    abbr = DAYS_ABBR.get(lang, DAYS_ABBR["IT"])

    rows = []
    for d in range(1, num_days + 1):
        dt = date(year, month, d)
        res_d = days_out[d]
        chef_name = employees_by_id.get(res_d["chef"], {}).get("last_name", "").upper() if res_d["chef"] else ""
        rows.append({
            cols[0]: abbr[dt.weekday()],
            cols[1]: d,
            cols[2]: ", ".join(sorted(short_name(employees_by_id, e) for e in res_d["giorno"])),
            cols[3]: ", ".join(sorted(short_name(employees_by_id, e) for e in res_d["notte"])),
            cols[4]: ", ".join(sorted(short_name(employees_by_id, e) for e in res_d["riposo"])),
            cols[5]: chef_name,
            cols[6]: ", ".join(sorted(short_name(employees_by_id, e) for e in res_d["ferie"])),
            cols[7]: ", ".join(sorted(short_name(employees_by_id, e) for e in res_d["malattia"])),
        })

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df = pd.DataFrame(rows)
        df.to_excel(writer, index=False, sheet_name="Planning")
        workbook = writer.book
        worksheet = writer.sheets["Planning"]
        cell_fmt = workbook.add_format({"border": 1, "text_wrap": True, "valign": "top"})
        header_fmt = workbook.add_format({"border": 1, "bold": True, "bg_color": "#F2F2F2"})
        for i, width in enumerate([10, 5, 25, 20, 25, 10, 15, 15]):
            worksheet.set_column(i, i, width, cell_fmt)
        for i, col_name in enumerate(cols):
            worksheet.write(0, i, col_name, header_fmt)
        worksheet.set_landscape()
        worksheet.set_paper(9)  # A4
        worksheet.fit_to_pages(1, 0)

    buffer.seek(0)
    return buffer.read()

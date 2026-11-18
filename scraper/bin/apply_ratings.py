"""
Applies pre-computed ratings (from in-session Claude sub-agents) to an
existing xlsx: adds Match Score (color-coded), Match Notes, and Missing
Requirements columns, then re-sorts rows by score.

Usage:
    python3 bin/apply_ratings.py --xlsx <path_to.xlsx> --ratings <path_to_ratings.json>

ratings.json format: a JSON array of
    {"file": "<description filename>", "score": <1-5>, "reason": "<...>", "missing": "<...>"}
"""

import argparse
import json

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

SCORE_FILLS = {
    1: PatternFill("solid", fgColor="00B050"),  # green
    2: PatternFill("solid", fgColor="92D050"),  # light green
    3: PatternFill("solid", fgColor="FFFF00"),  # yellow
    4: PatternFill("solid", fgColor="FFC000"),  # orange
    5: PatternFill("solid", fgColor="FF0000"),  # red
}
SCORE_FONTS = {
    1: Font(name="Arial", size=10, bold=True, color="FFFFFF"),
    2: Font(name="Arial", size=10, bold=True, color="000000"),
    3: Font(name="Arial", size=10, bold=True, color="000000"),
    4: Font(name="Arial", size=10, bold=True, color="000000"),
    5: Font(name="Arial", size=10, bold=True, color="FFFFFF"),
}


def update_xlsx(xlsx_path, ratings_by_file):
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb.active

    # Find or create Match Score, Match Notes, Missing Requirements columns
    headers = {ws.cell(1, c).value: c for c in range(1, ws.max_column + 1)}
    if "Match Score" not in headers:
        score_col   = ws.max_column + 1
        notes_col   = ws.max_column + 2
        missing_col = ws.max_column + 3
        ws.cell(1, score_col,   "Match Score")
        ws.cell(1, notes_col,   "Match Notes")
        ws.cell(1, missing_col, "Missing Requirements")
        header_fill = PatternFill("solid", fgColor="1F4E79")
        header_font = Font(name="Arial", size=11, bold=True, color="FFFFFF")
        center = Alignment(horizontal="center", vertical="top", wrap_text=True)
        for col in (score_col, notes_col, missing_col):
            c = ws.cell(1, col)
            c.fill = header_fill
            c.font = header_font
            c.alignment = center
        ws.column_dimensions[get_column_letter(score_col)].width   = 14
        ws.column_dimensions[get_column_letter(notes_col)].width   = 55
        ws.column_dimensions[get_column_letter(missing_col)].width = 45
    else:
        score_col   = headers["Match Score"]
        notes_col   = headers["Match Notes"]
        missing_col = headers.get("Missing Requirements")
        if not missing_col:
            missing_col = ws.max_column + 1
            ws.cell(1, missing_col, "Missing Requirements")
            header_fill = PatternFill("solid", fgColor="1F4E79")
            header_font = Font(name="Arial", size=11, bold=True, color="FFFFFF")
            center = Alignment(horizontal="center", vertical="top", wrap_text=True)
            c = ws.cell(1, missing_col)
            c.fill = header_fill
            c.font = header_font
            c.alignment = center
            ws.column_dimensions[get_column_letter(missing_col)].width = 45

    # Find the Description File column to look up filenames
    desc_col = headers.get("Description File")

    top_wrap = Alignment(vertical="top", wrap_text=True)
    score_align = Alignment(horizontal="center", vertical="top")

    for row in range(2, ws.max_row + 1):
        fname = ws.cell(row, desc_col).value if desc_col else None
        if not fname:
            continue
        rating = ratings_by_file.get(fname)
        if not rating:
            continue
        score   = rating["score"]
        reason  = rating["reason"]
        missing = rating.get("missing", "")

        sc = ws.cell(row, score_col, score)
        sc.fill = SCORE_FILLS.get(score, SCORE_FILLS[3])
        sc.font = SCORE_FONTS.get(score, SCORE_FONTS[3])
        sc.alignment = score_align

        nc = ws.cell(row, notes_col, reason)
        nc.font = Font(name="Arial", size=10)
        nc.alignment = top_wrap

        mc = ws.cell(row, missing_col, missing)
        mc.font = Font(name="Arial", size=10)
        mc.alignment = top_wrap

    # Sort data rows by Match Score (ascending), keeping header in place
    data_rows = []
    for row in range(2, ws.max_row + 1):
        data_rows.append([ws.cell(row, c).value for c in range(1, ws.max_column + 1)])

    data_rows.sort(key=lambda r: (r[score_col - 1] or 99))

    row_fills = [PatternFill("solid", fgColor="D6E4F0"), PatternFill("solid", fgColor="FFFFFF")]
    for i, row_data in enumerate(data_rows):
        excel_row = i + 2
        base_fill = row_fills[i % 2]
        score_val = row_data[score_col - 1]
        for col_idx, val in enumerate(row_data, start=1):
            cell = ws.cell(excel_row, col_idx, val)
            if col_idx == score_col and score_val and isinstance(score_val, int):
                cell.fill = SCORE_FILLS.get(score_val, base_fill)
                cell.font = SCORE_FONTS.get(score_val, Font(name="Arial", size=10))
                cell.alignment = score_align
            elif col_idx in (notes_col, missing_col):
                cell.fill = base_fill
                cell.font = Font(name="Arial", size=10)
                cell.alignment = top_wrap
            else:
                cell.fill = base_fill
                cell.font = Font(name="Arial", size=10)
                cell.alignment = Alignment(vertical="top", wrap_text=True)

    wb.save(xlsx_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--xlsx", required=True)
    parser.add_argument("--ratings", required=True, help="Path to JSON file: list of {file,score,reason,missing}")
    args = parser.parse_args()

    with open(args.ratings) as f:
        ratings = json.load(f)

    ratings_by_file = {
        r["file"]: {"score": r["score"], "reason": r["reason"], "missing": r.get("missing", "")}
        for r in ratings
    }
    update_xlsx(args.xlsx, ratings_by_file)
    print(f"Applied {len(ratings_by_file)} ratings to {args.xlsx}")


if __name__ == "__main__":
    main()

import json
import os
import re
import sys
from datetime import datetime

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

# Workplace values from ai_work_arrangement that indicate fully remote — keep regardless of location.
# "Remote" is a legacy value from an older scraper (kept for backward compat).
REMOTE_ARRANGEMENTS = {"Remote Solely", "Remote OK", "Remote"}

def is_local(location, local_keywords):
    """True if the location string contains any of the local-area keywords
    (case-insensitive substring match). The keywords come from
    searchArea.local.keywords in input/keywords_search.json."""
    loc = (location or "").lower()
    return any(kw.lower() in loc for kw in (local_keywords or []))


def format_date(raw):
    """YYYY-MM-DD from any ISO-style timestamp. Takes the date prefix rather
    than matching exact formats: the actor's timestamps vary (with/without
    'Z', with/without fractional seconds), and an unlisted variant used to
    fall through and show the raw timestamp in the spreadsheet."""
    if not raw:
        return ""
    m = re.match(r"\d{4}-\d{2}-\d{2}", raw)
    return m.group(0) if m else raw


def is_expired(valid_through):
    """True if valid_through is a parseable timestamp already in the past.
    Missing/unparseable values are treated as unknown, not expired — the
    actor leaves this field null for a meaningful fraction of postings."""
    if not valid_through:
        return False
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(valid_through, fmt) < datetime.utcnow()
        except ValueError:
            continue
    return False


def format_salary(salary_info):
    if not salary_info:
        return ""
    if isinstance(salary_info, list):
        parts = [s.strip() for s in salary_info if s]
        return " - ".join(parts) if parts else ""
    return str(salary_info)


def sanitize_filename(s, max_len=40):
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", "_", s.strip())
    return s[:max_len]


def write_description_file(job, row_num, desc_dir):
    company = sanitize_filename(job.get("companyName", "Unknown"))
    title = sanitize_filename(job.get("jobTitle", "Unknown"))
    filename = f"{row_num:03d}_{company}_{title}.txt"
    filepath = os.path.join(desc_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"Job Title:  {job.get('jobTitle', '')}\n")
        f.write(f"Company:    {job.get('companyName', '')}\n")
        f.write(f"Location:   {job.get('location', '')}\n")
        f.write(f"Workplace:  {job.get('workplace', '')}\n")
        f.write(f"Posted:     {format_date(job.get('publishedAt', ''))}\n")
        f.write(f"URL:        {job.get('jobUrl', '')}\n")
        f.write("\n" + "-" * 60 + "\n\n")
        f.write(job.get("jobDescription", "No description available."))
    return filename


def build_excel(jobs, search_term, output_path, skip_filter=False, limit=None, local_keywords=None):
    included = []
    excluded = 0
    expired = 0

    for job in jobs:
        location  = job.get("location", "")
        workplace = job.get("workplace", "")
        if is_expired(job.get("validThrough", "")):
            expired += 1
            continue
        if not skip_filter and workplace not in REMOTE_ARRANGEMENTS and not is_local(location, local_keywords):
            excluded += 1
            continue
        included.append(job)
        if limit and len(included) >= limit:
            break

    excluded += max(0, len(jobs) - len(included) - excluded - expired) if limit else 0

    print(f"Total scraped: {len(jobs)} | Included: {len(included)} | Excluded (onsite, outside local area): {excluded} | Excluded (expired): {expired}")

    stats = {
        "total_scraped": len(jobs),
        "included": len(included),
        "excluded": excluded,
        "expired": expired,
    }

    if not included:
        print("No jobs passed the filter. No file created.")
        return stats

    # Set up description files directory
    # Same spaces->underscores slug that run_search.py (archiving/clearing) and
    # write_rating_summary.py use to find this directory --
    # any other transform would make them miss it for group names with
    # punctuation.
    search_slug = search_term.replace(" ", "_")
    desc_dir = os.path.join(os.path.dirname(output_path), search_slug)
    os.makedirs(desc_dir, exist_ok=True)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"{search_term} Jobs"

    headers = [
        "Job Title", "Company", "Location", "Date Posted", "Salary Range",
        "Seniority Level", "Employment Type", "Workplace", "Search Term",
        "LinkedIn URL", "Description File", "Dup Of",
    ]
    col_widths = [45, 30, 28, 14, 32, 18, 18, 12, 22, 60, 35, 9]

    header_fill = PatternFill("solid", fgColor="1F4E79")
    header_font = Font(name="Arial", size=11, bold=True, color="FFFFFF")
    row_fills = [PatternFill("solid", fgColor="D6E4F0"), PatternFill("solid", fgColor="FFFFFF")]
    data_font = Font(name="Arial", size=10)
    center = Alignment(horizontal="center", vertical="top", wrap_text=True)
    top_wrap = Alignment(vertical="top", wrap_text=True)

    ws.row_dimensions[1].height = 30
    for col_idx, (header, width) in enumerate(zip(headers, col_widths), start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    # Same title + company under a different linkedin_id: could be one job reposted
    # in several countries, or separate openings sharing a generic title. Flag rather
    # than drop: the "Dup Of" cell holds the first occurrence's entry number (its
    # description file prefix, which stays valid after ratings re-sort the rows), and
    # whether description/location match is tallied for the summary, so there's data
    # to decide on a real dedup rule later.
    first_by_title_org = {}
    possible_duplicates = 0
    dup_same_desc = 0
    dup_same_loc = 0

    for row_idx, job in enumerate(included, start=1):
        desc_filename = write_description_file(job, row_idx, desc_dir)
        fill = row_fills[(row_idx - 1) % 2]

        title_org = (job.get("jobTitle", "").strip().lower(), job.get("companyName", "").strip().lower())
        duplicate_of = ""
        if title_org in first_by_title_org:
            first_row, first_job = first_by_title_org[title_org]
            duplicate_of = f"{first_row:03d}"
            possible_duplicates += 1
            dup_same_desc += job.get("jobDescription", "").strip() == first_job.get("jobDescription", "").strip()
            dup_same_loc += job.get("location", "").strip().lower() == first_job.get("location", "").strip().lower()
        else:
            first_by_title_org[title_org] = (row_idx, job)

        values = [
            job.get("jobTitle", ""),
            job.get("companyName", ""),
            job.get("location", ""),
            format_date(job.get("publishedAt", "")),
            format_salary(job.get("salaryInfo")),
            job.get("experienceLevel", ""),
            job.get("contractType", ""),
            job.get("workplace", ""),
            search_term,
            job.get("jobUrl", ""),
            desc_filename,
            duplicate_of,
        ]
        excel_row = row_idx + 1
        url_col = 10  # LinkedIn URL column
        for col_idx, value in enumerate(values, start=1):
            if col_idx == url_col and value:
                safe = value.replace('"', '%22')
                cell = ws.cell(row=excel_row, column=col_idx, value=f'=HYPERLINK("{safe}","{safe}")')
                cell.font = Font(name="Arial", size=10, color="0563C1", underline="single")
            else:
                cell = ws.cell(row=excel_row, column=col_idx, value=value)
                cell.font = data_font
            cell.fill = fill
            cell.alignment = top_wrap

    ws.freeze_panes = "B2"
    ws.auto_filter.ref = ws.dimensions

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    wb.save(output_path)
    print(f"Saved spreadsheet: {output_path}")
    print(f"Saved {len(included)} description files to: {desc_dir}/")
    print(f"Possible duplicates (same title + company, different LinkedIn ID): {possible_duplicates} "
          f"(same description: {dup_same_desc}, same location: {dup_same_loc})")
    stats["possible_duplicates"] = possible_duplicates
    stats["dup_same_desc"] = dup_same_desc
    stats["dup_same_loc"] = dup_same_loc
    return stats


if __name__ == "__main__":
    data_file = sys.argv[1]
    search_term = sys.argv[2]
    output_path = sys.argv[3]
    skip_filter = "--skip-filter" in sys.argv
    limit = None
    for arg in sys.argv:
        if arg.startswith("--limit="):
            limit = int(arg.split("=")[1])

    with open(data_file) as f:
        jobs = json.load(f)

    build_excel(jobs, search_term, output_path, skip_filter=skip_filter, limit=limit)

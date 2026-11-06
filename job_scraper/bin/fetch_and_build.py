"""
Fetches Apify datasets for a remote run (and optionally a local-area run),
normalizes fields from the
fantastic-jobs/advanced-linkedin-job-search-api actor, combines, deduplicates,
and calls build_excel to produce the spreadsheet and description files.

Usage:
    python3 bin/fetch_and_build.py \
        --remote  <datasetId> \
        [--local  <datasetId>] \
        --term    "High Signal" \
        --output  output/High_Signal_LinkedIn_Jobs.xlsx \
        [--limit  100] \
        [--token  apify_api_...] \
        [--skip-filter]

The Apify token comes from --token if given, otherwise the APIFY_TOKEN
environment variable. Local-area keywords for the location filter are read
from searchArea.local.keywords in input/keywords_search.json, if present.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_excel import build_excel

API_BASE = "https://api.apify.com/v2/datasets"


def get_token():
    """Apify token from the APIFY_TOKEN environment variable (inherited from the
    shell that launched this process — set it in ~/.tcshrc). Deliberately not read
    from ~/.claude.json: the apify-http MCP header there is "Bearer ${APIFY_TOKEN}",
    a reference Claude Code expands for itself, not a usable token."""
    token = os.environ.get("APIFY_TOKEN", "").strip()
    if not token:
        print("ERROR: APIFY_TOKEN is not set. Set it in your shell startup file and "
              "start a new shell (and restart Claude Code if running from there).")
        sys.exit(1)
    return token


def normalize_job(item):
    """Map fantastic-jobs output fields to our internal schema."""
    locations = item.get("locations_derived") or []
    location = locations[0] if locations else ""

    min_val = item.get("ai_salary_min_value")
    max_val = item.get("ai_salary_max_value")
    unit = item.get("ai_salary_unit_text") or ""
    unit_suffix = {"YEAR": "/yr", "MONTH": "/mo", "HOUR": "/hr", "WEEK": "/wk"}.get(unit, "")
    salary_parts = []
    if min_val:
        salary_parts.append(f"${int(min_val):,}")
    if max_val and max_val != min_val:
        salary_parts.append(f"${int(max_val):,}")
    salary_str = (" - ".join(salary_parts) + unit_suffix) if salary_parts else ""

    emp_types = item.get("ai_employment_type") or []
    contract_type = emp_types[0].replace("_", " ").title() if emp_types else ""

    return {
        "jobId":           str(item.get("linkedin_id", "")),
        "jobTitle":        item.get("title", ""),
        "companyName":     item.get("organization", ""),
        "location":        location,
        "publishedAt":     item.get("date_posted", ""),
        "salaryInfo":      salary_str,
        "experienceLevel": item.get("seniority", ""),
        "contractType":    contract_type,
        "workplace":       item.get("ai_work_arrangement", ""),
        "jobUrl":          item.get("url", ""),
        "jobDescription":  item.get("description_text", ""),
        "validThrough":    item.get("date_valid_through") or "",
    }


def _get_json_with_retry(url, token, attempts=4):
    # Apify occasionally returns transient 5xx (e.g. 502 Bad Gateway, seen 2026-10-13),
    # which used to kill a whole multi-group run mid-way. Retry those with backoff.
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read())
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            transient = not isinstance(e, urllib.error.HTTPError) or e.code >= 500
            if not transient or attempt == attempts:
                raise
            wait = 5 * 2 ** (attempt - 1)
            print(f"  {e} — retrying in {wait}s ({attempt}/{attempts - 1})...")
            time.sleep(wait)


def fetch_dataset(dataset_id, token):
    offset = 0
    page = 200
    items = []
    while True:
        url = (
            f"{API_BASE}/{dataset_id}/items"
            f"?limit={page}&offset={offset}&clean=true"
        )
        batch = _get_json_with_retry(url, token)
        if not batch:
            break
        items.extend(normalize_job(item) for item in batch)
        print(f"  fetched {len(items)} so far...")
        if len(batch) < page:
            break
        offset += page
    return items


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--remote",      required=True)
    parser.add_argument("--local",       default=None)
    parser.add_argument("--term",        required=True)
    parser.add_argument("--output",      required=True)
    parser.add_argument("--token",       default=None)
    parser.add_argument("--limit",       type=int, default=100)
    parser.add_argument("--skip-filter", action="store_true")
    args = parser.parse_args()

    token = args.token or get_token()

    local_keywords = []
    config = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "input", "keywords_search.json")
    if os.path.exists(config):
        with open(config) as f:
            data = json.load(f)
        if isinstance(data, dict):
            local_keywords = ((data.get("searchArea") or {}).get("local") or {}).get("keywords", [])

    print("Fetching datasets...")
    remote_items = fetch_dataset(args.remote, token)
    local_items = fetch_dataset(args.local, token) if args.local else []

    print(f"\nRaw counts — Remote: {len(remote_items)} | Local: {len(local_items)}")

    combined = []
    seen = set()
    for item in (remote_items + local_items):
        jid = item.get("jobId")
        if jid and jid in seen:
            continue
        seen.add(jid)
        combined.append(item)

    print(f"After dedup: {len(combined)} unique jobs")

    build_excel(combined, args.term, args.output, skip_filter=args.skip_filter, limit=args.limit,
                local_keywords=local_keywords)


if __name__ == "__main__":
    main()

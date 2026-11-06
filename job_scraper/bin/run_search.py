"""
Orchestration script. Reads input/keywords_search.json and, for each group,
fires one Apify run per keyword for remote jobs (plus one for on-site/hybrid
jobs in the local area, if searchArea.local is set), waits for completion,
then builds the spreadsheet and description files in output/.

The Apify token comes from the APIFY_TOKEN environment variable.

Usage:
    python3 bin/run_search.py
    python3 bin/run_search.py --group "High Signal"
    python3 bin/run_search.py --dry-run
"""

import argparse
import itertools
import json
import os
import shutil
import sys
import time
import urllib.request
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_and_build import fetch_dataset, get_token
from build_excel import build_excel

ACTOR = "fantastic-jobs~advanced-linkedin-job-search-api"
APIFY_BASE = "https://api.apify.com/v2"

# Runs per keyword: remote jobs in the search country, plus (optionally)
# on-site/hybrid jobs in the local area. Both come from the "searchArea"
# section of input/keywords_search.json.
# NOTE: Only run one group at a time — 2 concurrent runs per keyword is within
# account limits; running multiple groups in parallel risks HTTP 402.
#
# The remote run must have a locationSearch: without one the actor returns
# English-language remote jobs worldwide (one test run came back 10/10 UK/EU
# postings). locationSearch is phrase matching, so "United States" matches any
# "..., United States" location.
DEFAULT_SEARCH_AREA = {"remote": {"locationSearch": ["United States"]}}


def build_runs(search_area):
    """[(run_name, extra_actor_input), ...] for one keyword."""
    area = search_area or DEFAULT_SEARCH_AREA
    remote = area.get("remote") or DEFAULT_SEARCH_AREA["remote"]
    runs = [("remote", {
        "locationSearch": remote.get("locationSearch", ["United States"]),
        "aiWorkArrangementFilter": ["Remote Solely", "Remote OK"],
        "aiLanguageFilter": remote.get("languages", ["English"]),
    })]
    local = area.get("local")
    if local:
        runs.append(("local", {
            "locationSearch": local["locationSearch"],
            "aiWorkArrangementFilter": ["On-site", "Hybrid"],
        }))
    return runs


def apify_post(url, token, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def apify_get(url, token):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def start_run(token, keywords, run_name, extra_input, fetch_limit, search_field="descriptionSearch", companies=None, time_range="7d", actor_input=None, dry_run=False):
    input_data = {
        search_field: keywords,
        "timeRange": time_range,
        "descriptionType": "text",
        "limit": fetch_limit,
        **extra_input,
        # Group-level extra actor filters (e.g. aiExperienceLevelFilter). Applied
        # last so a group can narrow broad title searches without code changes.
        **(actor_input or {}),
    }
    if companies:
        input_data["organizationSearch"] = companies
    if dry_run:
        suffix = f" | companies: {companies}" if companies else ""
        if actor_input:
            suffix += f" | actorInput: {actor_input}"
        print(f"    [DRY RUN] {run_name} [{search_field}, {time_range}]: {keywords}{suffix}")
        return f"dry-{run_name}"
    url = f"{APIFY_BASE}/acts/{ACTOR}/runs"
    result = apify_post(url, token, input_data)
    run_id = result["data"]["id"]
    print(f"    Started {run_name} run: {run_id}")
    return run_id


def final_run_cost(token, run_id, items_fetched, max_wait_secs=60):
    """Return a run's real cost (usageTotalUsd).

    Apify posts per-item charges a little after a run reports SUCCEEDED, so reading
    the cost right away undercounts badly (confirmed 2026-10-26: a 176-item run read
    as $0.0004, actual $0.88). Re-read until the charged item count catches up with
    the items we downloaded, or give up after max_wait_secs and use the latest value."""
    url = f"{APIFY_BASE}/actor-runs/{run_id}"
    deadline = time.time() + max_wait_secs
    while True:
        data = apify_get(url, token)["data"]
        charged = (data.get("chargedEventCounts") or {}).get("apify-default-dataset-item", 0)
        if charged >= items_fetched or time.time() >= deadline:
            if charged < items_fetched:
                print(f"    WARNING: run {run_id} cost may be understated ({charged}/{items_fetched} items charged so far)")
            return data.get("usageTotalUsd") or 0.0
        time.sleep(5)


def wait_for_run(token, run_id, poll_secs=15, timeout_secs=1200):
    url = f"{APIFY_BASE}/actor-runs/{run_id}"
    """Poll until the run ends. Returns the run object, or None if it is still
    running after timeout_secs (the caller skips that run and keeps going).

    The status is always re-checked after the deadline passes, before giving up:
    on 2026-10-26 the Mac slept during a 15s poll, the clock jumped past the
    deadline, and a run that had finished in 2 seconds killed the whole group."""
    deadline = time.time() + timeout_secs
    while True:
        data = apify_get(url, token)["data"]
        status = data["status"]
        if status == "SUCCEEDED":
            dataset_id = data["defaultDatasetId"]
            item_count = data.get("stats", {}).get("itemCount", "?")
            print(f"    {run_id} → SUCCEEDED ({item_count} items, dataset {dataset_id})")
            return data
        if status in ("FAILED", "ABORTED", "TIMED-OUT"):
            print(f"    WARNING: Run {run_id} ended with status {status}")
            return data
        if time.time() >= deadline:
            print(f"    WARNING: Run {run_id} still {status} after {timeout_secs}s — skipping it")
            return None
        elapsed = int(time.time() - (deadline - timeout_secs))
        print(f"    {run_id} status: {status} ({elapsed}s elapsed) — checking in {poll_secs}s...")
        time.sleep(poll_secs)


def resolve_keywords(group, keyword_categories):
    """Union of any referenced 'keywords-category' names' keyword lists
    plus any literal 'keywords' on the group itself, deduped, first-seen
    order preserved. Either or both may be present; at least one must be."""
    resolved = []
    keywords_category = group.get("keywords-category")
    if keywords_category:
        names = keywords_category if isinstance(keywords_category, list) else [keywords_category]
        for name in names:
            if name not in keyword_categories:
                known = list(keyword_categories)
                raise ValueError(f"Group '{group['group']}' references unknown keywords-category '{name}'. Known categories: {known}")
            for kw in keyword_categories[name]:
                if kw not in resolved:
                    resolved.append(kw)
    for kw in group.get("keywords", []):
        if kw not in resolved:
            resolved.append(kw)
    if not resolved:
        raise ValueError(f"Group '{group['group']}' has neither 'keywords' nor 'keywords-category'")
    if group.get("permuteKeywords"):
        resolved = permute_keywords(resolved)
    return resolved


def permute_keywords(keywords, max_words=3):
    """Add every word order of each 2-3 word keyword.

    titleSearch is phrase matching: word order matters and there is no
    "all of these words" operator (tested 2026-10-26: 'A & B & C' returned nothing).
    All 6 orders of "Systems Software Engineer" returned real, different titles,
    e.g. "Staff Software Engineer, Software Systems" only matches "Engineer Software
    Systems". Keywords longer than max_words are left as-is (24+ orders)."""
    out = []
    for kw in keywords:
        words = kw.split()
        variants = [" ".join(p) for p in itertools.permutations(words)] if 2 <= len(words) <= max_words else [kw]
        for v in variants:
            if v not in out:
                out.append(v)
    return out


def load_archive_state(output_dir):
    path = os.path.join(output_dir, ".archive_state.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def save_archive_state(output_dir, state):
    path = os.path.join(output_dir, ".archive_state.json")
    with open(path, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def archive_stale_output(output_dir, slug, group_name, output_xlsx):
    """If this group's last tracked scrape (per .archive_state.json) was in a
    different ISO week than now, move the existing spreadsheet + description
    dir into OLD/<old-date>/ before the new run overwrites them. Same-week
    reruns are left in place untouched.

    Uses tracked state, not the file's mtime: mtime is unreliable here since
    an unrelated edit (e.g. a rating fix) bumps it without that being a real
    rerun of the scrape, which previously caused this check to wrongly skip
    archiving and silently lose data. State is per-group, not a shared
    invocation date — groups run on different days (via --group) archive
    independently. A file with no tracked state (predates this feature)
    falls back to its mtime as a best guess."""
    if not os.path.exists(output_xlsx):
        return

    state = load_archive_state(output_dir)
    last_scrape = state.get(group_name)
    old_dt = datetime.strptime(last_scrape, "%y%m%d") if last_scrape else \
        datetime.fromtimestamp(os.path.getmtime(output_xlsx))

    now = datetime.now()
    if old_dt.isocalendar()[:2] == now.isocalendar()[:2]:
        return

    old_date = old_dt.strftime("%y%m%d")
    archive_dir = os.path.join(output_dir, "OLD", old_date)
    os.makedirs(archive_dir, exist_ok=True)

    dest_xlsx = os.path.join(archive_dir, os.path.basename(output_xlsx))
    shutil.move(output_xlsx, dest_xlsx)
    print(f"Archived previous spreadsheet → {dest_xlsx}")

    desc_dir = os.path.join(output_dir, slug)
    if os.path.isdir(desc_dir):
        dest_desc_dir = os.path.join(archive_dir, slug)
        shutil.move(desc_dir, dest_desc_dir)
        print(f"Archived previous descriptions → {dest_desc_dir}")


def process_group(group, token, project_root, keyword_categories, runs, local_keywords, dry_run=False, search_field_override=None):
    group_name   = group["group"]
    keywords     = resolve_keywords(group, keyword_categories)
    limit        = group.get("limit", 100)
    fetch_limit  = limit + 50  # Extra buffer to cover dedup loss
    # --search-field on the CLI forces this for the whole invocation (testing/A-B
    # comparisons without editing keywords_search.json); otherwise each group's own
    # "searchField" wins, falling back to titleSearch -- descriptionSearch with a
    # multi-term array is noisy/imprecise (the actor vendor's own docs warn against
    # it: "too intensive... limit to a handful of keywords... prefer titleSearch"),
    # confirmed directly on 2026-08-22 when it missed an exact keyword/title match
    # (a posting with the keyword verbatim in its title) while admitting an unrelated one.
    search_field = search_field_override or group.get("searchField", "titleSearch")
    companies    = group.get("companies")
    time_range   = group.get("timeRange", "7d")
    keywords_category = group.get("keywords-category")
    category_display = " + ".join(keywords_category) if isinstance(keywords_category, list) else keywords_category
    slug         = group_name.replace(" ", "_")

    if time_range == "6m" and search_field == "descriptionSearch":
        print(f"ERROR: Group '{group_name}' uses timeRange=6m with descriptionSearch, which the actor does not support. Set \"searchField\": \"titleSearch\" for this group.")
        return {"group": group_name, "status": "error", "error": "6m timeRange requires titleSearch", "cost": 0.0}

    output_dir = os.path.join(project_root, "output")
    output_xlsx = os.path.join(output_dir, f"{slug}_LinkedIn_Jobs.xlsx")

    print(f"\n{'='*60}")
    print(f"Group:    {group_name}" + (f"  [{category_display}]" if category_display else ""))
    print(f"Keywords: {', '.join(keywords)}")
    print(f"Search:   {search_field}")
    print(f"Window:   {time_range}")
    if companies:
        print(f"Companies: {', '.join(companies)}")
    print(f"Output:   {output_xlsx}")
    print(f"{'='*60}")

    # One remote(+local) run PER KEYWORD, not one run with all keywords combined.
    # Confirmed directly on 2026-08-22: even titleSearch silently drops keywords when
    # given a multi-term array — a 2-term query (["Linux Kernel Engineer", "Platform
    # Software Engineer"]) returned only "Platform Software Engineer" matches, zero
    # "Linux Kernel Engineer" ones, in either term order, despite "Linux Kernel
    # Engineer" alone returning 6 real matches for the same company/window. Combining
    # keywords into one array isn't reliable regardless of searchField, so each
    # keyword gets its own isolated pair of runs; results are merged/deduped locally
    # afterward. Runs are cheap (~$0.0001/run + ~$0.005/item — see Cost Reference in
    # CLAUDE.md) and fast (seconds, not the old "2-5 minutes" estimate), so this is a
    # small cost/time increase for materially more reliable coverage.
    print(f"\nStarting Apify runs ({len(keywords)} keyword(s) × {'+'.join(r for r, _ in runs)})...")
    all_remote_items = []
    all_local_items = []
    finished_runs = []  # (run_id, items fetched) — costs are read at the end, see final_run_cost()
    for i, keyword in enumerate(keywords, 1):
        print(f"\n  [{i}/{len(keywords)}] '{keyword}'")
        run_ids = {}
        for run_name, extra_input in runs:
            try:
                run_ids[run_name] = start_run(token, [keyword], run_name, extra_input, fetch_limit, search_field=search_field, companies=companies, time_range=time_range, actor_input=group.get("actorInput"), dry_run=dry_run)
            except Exception as e:
                print(f"    ERROR starting {run_name} run for '{keyword}': {e}")
                print(f"    Aborting group '{group_name}' — check Apify balance/concurrency limits.")
                cost = sum(final_run_cost(token, rid, n) for rid, n in finished_runs)
                return {"group": group_name, "status": "error", "error": str(e), "cost": cost}

        if dry_run:
            continue

        for run_name, _ in runs:
            run_data = wait_for_run(token, run_ids[run_name]) or {}
            dataset_id = run_data.get("defaultDatasetId")
            if not dataset_id:
                print(f"    WARNING: {run_name} run failed for keyword '{keyword}' — skipping it, continuing with other keywords.")
                finished_runs.append((run_ids[run_name], 0))
                continue
            items = fetch_dataset(dataset_id, token)
            (all_remote_items if run_name == "remote" else all_local_items).extend(items)
            finished_runs.append((run_ids[run_name], len(items)))
            print(f"    {run_name}: {len(items)} items")

    if dry_run:
        print("\n[DRY RUN] Skipping wait and build steps.\n")
        return None

    total_cost = sum(final_run_cost(token, rid, n) for rid, n in finished_runs)

    remote_raw = len(all_remote_items)
    local_raw = len(all_local_items)

    print(f"\nRaw counts (all keywords combined) — Remote: {remote_raw} | Local: {local_raw}")

    combined = []
    seen = set()
    for item in (all_remote_items + all_local_items):
        jid = item.get("jobId")
        if jid and jid in seen:
            continue
        seen.add(jid)
        combined.append(item)

    print(f"After dedup (linkedin_id): {len(combined)} unique jobs")

    # Same title + company under different linkedin_ids is NOT dropped here: it may be
    # one job reposted across countries, or genuinely separate openings (different
    # teams/locations) that share a generic title. build_excel() flags these in a
    # "Dup Of" column instead, so we can gather data before deciding.

    os.makedirs(output_dir, exist_ok=True)
    archive_stale_output(output_dir, slug, group_name, output_xlsx)

    # A same-week rerun deliberately isn't archived (see archive_stale_output),
    # but build_excel() writes description files by row number without ever
    # clearing the directory first -- so a rerun whose result set differs from
    # the prior run (new keywords, fresh data, etc.) leaves the old run's files
    # behind as orphans instead of them being replaced. Clear it before every
    # build so the directory always reflects exactly the current run's rows.
    # The spreadsheet goes too: build_excel() writes nothing when 0 jobs pass,
    # so a same-week rerun that comes back empty would otherwise leave the prior
    # run's xlsx in place, pointing at description files that were just deleted.
    desc_dir = os.path.join(output_dir, slug)
    if os.path.isdir(desc_dir):
        shutil.rmtree(desc_dir)
    if os.path.exists(output_xlsx):
        os.remove(output_xlsx)

    excel_stats = build_excel(combined, group_name, output_xlsx, limit=limit, local_keywords=local_keywords) or {}

    state = load_archive_state(output_dir)
    state[group_name] = datetime.now().strftime("%y%m%d")
    save_archive_state(output_dir, state)

    return {
        "group": group_name,
        "status": "ok",
        "remote_raw": remote_raw,
        "local_raw": local_raw,
        "included": excel_stats.get("included", 0),
        "excluded": excel_stats.get("excluded", 0),
        "expired": excel_stats.get("expired", 0),
        "possible_duplicates": excel_stats.get("possible_duplicates", 0),
        "dup_same_desc": excel_stats.get("dup_same_desc", 0),
        "dup_same_loc": excel_stats.get("dup_same_loc", 0),
        "cost": total_cost,
    }


def write_group_scrape_summary(result, project_root):
    """Writes output/<Group>_scrape_summary.md for a single group's run
    — one file per group, named for the group (like <Group>_LinkedIn_Jobs.xlsx)
    so its cost/results are visible without opening it, rather than one shared
    file across groups. A shared file would need cross-group upsert logic to
    avoid one group's write clobbering another's from earlier in the same week
    (most invocations only run one group at a time — see the "only run one
    group at a time" note); per-group files sidestep that entirely, since a
    same-week rerun of a group overwriting *that group's own* prior data is
    fine. Cost figures come from each run's actual usageTotalUsd (Apify API),
    not an estimate.

    Archived into OLD/<old-date>/ on ISO-week rollover, same mechanics as the
    xlsx archiving below, tracked via its own .archive_state.json key (kept
    separate from the xlsx's tracking key for that group, since the two are
    written at different points and shouldn't drive each other's archiving)."""
    output_dir = os.path.join(project_root, "output")
    os.makedirs(output_dir, exist_ok=True)
    group_name = result["group"]
    slug = group_name.replace(" ", "_")
    summary_path = os.path.join(output_dir, f"{slug}_scrape_summary.md")
    state_key = f"{group_name} (scrape summary)"

    state = load_archive_state(output_dir)
    last = state.get(state_key)
    now = datetime.now()
    if last:
        old_dt = datetime.strptime(last, "%y%m%d")
    elif os.path.exists(summary_path):
        old_dt = datetime.fromtimestamp(os.path.getmtime(summary_path))
    else:
        old_dt = None

    if old_dt and old_dt.isocalendar()[:2] != now.isocalendar()[:2] and os.path.exists(summary_path):
        archive_dir = os.path.join(output_dir, "OLD", old_dt.strftime("%y%m%d"))
        os.makedirs(archive_dir, exist_ok=True)
        dest = os.path.join(archive_dir, f"{slug}_scrape_summary.md")
        shutil.move(summary_path, dest)
        print(f"Archived previous scrape summary → {dest}")

    cost = result.get("cost") or 0.0
    lines = [
        f"# Scrape Summary — {group_name} — {now.strftime('%Y-%m-%d %H:%M')}",
        "",
        "| Group | Remote | Local | Included | Excluded | Expired | Possible Dups | Cost |",
        "|---|---|---|---|---|---|---|---|",
    ]
    if result["status"] == "ok":
        lines.append(
            f"| {group_name} | {result['remote_raw']} | {result['local_raw']} | "
            f"{result['included']} | {result['excluded']} | {result['expired']} | "
            f"{result['possible_duplicates']} | ${cost:.4f} |"
        )
        if result["possible_duplicates"]:
            lines += ["", f"Possible dups detail: same description {result['dup_same_desc']}, "
                          f"same location {result['dup_same_loc']} (of {result['possible_duplicates']})"]
    else:
        lines.append(f"| {group_name} | — | — | — | — | — | — | ${cost:.4f} (ERROR) |")
        lines += ["", "## Errors", f"- {result.get('error', 'unknown error')}"]

    with open(summary_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    state[state_key] = now.strftime("%y%m%d")
    save_archive_state(output_dir, state)

    print(f"Saved scrape summary: {summary_path}")


def main():
    parser = argparse.ArgumentParser(description="Run LinkedIn job searches by keyword group.")
    parser.add_argument("--group",   default=None,  help="Run only this group (default: all groups)")
    parser.add_argument("--search-field", choices=["titleSearch", "descriptionSearch"], default=None,
                         help="Override every group's searchField for this invocation only "
                              "(testing/A-B comparisons) — does not modify keywords_search.json")
    parser.add_argument("--dry-run", action="store_true", help="Show what would run without calling Apify")
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    search_file  = os.path.join(project_root, "input", "keywords_search.json")

    if not os.path.exists(search_file):
        print(f"ERROR: {search_file} not found")
        sys.exit(1)

    with open(search_file) as f:
        data = json.load(f)

    # Schema: {"searchArea": {...}, "keywordCategories": {...}, "groups": [...]}.
    # A bare list of groups (no searchArea or categories) is also accepted.
    if isinstance(data, list):
        search_area, keyword_categories, groups = None, {}, data
    else:
        search_area = data.get("searchArea")
        keyword_categories = data.get("keywordCategories", {})
        groups = data["groups"]
    runs = build_runs(search_area)
    local_keywords = ((search_area or {}).get("local") or {}).get("keywords", [])

    if args.group:
        matched = [g for g in groups if g["group"] == args.group]
        if not matched:
            available = [g["group"] for g in groups]
            print(f"ERROR: Group '{args.group}' not found. Available: {available}")
            sys.exit(1)
        groups = matched

    token = get_token()

    print(f"Running {len(groups)} group(s)")
    if args.search_field:
        print(f"searchField override: {args.search_field} (applies to all groups this run only)")
    for group in groups:
        result = process_group(group, token, project_root, keyword_categories, runs, local_keywords,
                                dry_run=args.dry_run, search_field_override=args.search_field)
        # Write each group's summary as soon as it finishes, so a later group crashing
        # doesn't discard summaries for groups that already completed.
        if result and not args.dry_run:
            write_group_scrape_summary(result, project_root)

    print("\nAll groups complete.")


if __name__ == "__main__":
    main()

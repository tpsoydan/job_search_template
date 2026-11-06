# Job Scraper

Scrapes LinkedIn job listings by keyword with the Apify
`fantastic-jobs/advanced-linkedin-job-search-api` actor, filters them, writes one formatted `.xlsx`
spreadsheet plus one description file per job for each keyword group, rates the jobs against the
user's resume, and reports which skills would raise the ratings most.

Everything personal lives in `input/` (search config) and `output/` (results). The rest of this
folder is generic and comes from the template.

---

## Layout
```
job_scraper/
├── CLAUDE.md                 ← this file
├── bin/
│   ├── run_search.py         ← runs keyword groups end-to-end (the normal entry point)
│   ├── fetch_and_build.py    ← rebuilds a spreadsheet from existing Apify dataset IDs
│   ├── build_excel.py        ← filtering, spreadsheet and description files
│   ├── apply_ratings.py      ← writes sub-agent ratings into a group's spreadsheet
│   ├── write_rating_summary.py ← writes output/rating_summary.md
│   └── skill_gaps.py         ← writes output/skill_gaps.md (what to learn to raise scores)
├── ignore/                   ← scratch space; contents not tracked by git
├── input/
│   ├── example/              ← template-owned examples; copy, don't edit
│   ├── keywords_search.json  ← the search config (personal)
│   └── study_library.json    ← optional: skill → study doc mapping (personal)
└── output/                   ← personal results; not tracked by git
    ├── <Group>_LinkedIn_Jobs.xlsx
    ├── <Group>_scrape_summary.md
    ├── <Group>/001_<Company>_<Title>.txt ...
    ├── rating_summary.md
    ├── skill_gaps.md
    ├── .archive_state.json   ← last-scrape date per group (drives archiving)
    └── OLD/<yymmdd>/         ← previous weeks' results, archived automatically
```

Scripts are run from this folder (`python3 bin/run_search.py ...`).

---

## Setup

- `pip install openpyxl` (the only third-party package; Apify's REST API is called with `urllib`).
- The Apify API token lives **only** in the `APIFY_TOKEN` environment variable, set in the user's
  shell startup file. Never hardcode it, never print its value, never write it to a file. The scripts
  exit with a clear error if it's missing (`fetch_and_build.py` also accepts `--token`).
  - A running Claude Code session keeps the environment it started with: after changing the token,
    the user must open a new terminal and restart Claude Code.
- No LinkedIn login or cookies are needed.
- If `input/keywords_search.json` doesn't exist, build it with the user from
  `input/example/keywords_search.json` and the profile in the workspace's `input/profile.md`.

---

## Running a Search

```bash
python3 bin/run_search.py                          # all groups
python3 bin/run_search.py --group "High Signal"    # one group
python3 bin/run_search.py --dry-run                # show the runs, call nothing
python3 bin/run_search.py --group "X" --search-field descriptionSearch   # one-off override
```

- **Only run one group at a time** (one invocation at a time). Parallel invocations risk HTTP 402
  concurrent-run limits.
- Long runs (hundreds of keywords) take a while: run them in the background, and on macOS under
  `caffeinate -i` so the machine doesn't sleep mid-run.
- Always report the filter summary the scripts print:
  `Total scraped: X | Included: Y | Excluded (onsite, outside local area): Z | Excluded (expired): W`
- If a group returns 0 results, say so plainly. No spreadsheet is written for it.
- **After every weekly scrape, list the groups that returned 0** and suggest a 6-month deep pull for
  them (see below).

### Weekly cadence and the 6-month deep pull
The normal cadence is `timeRange: "7d"`, which only catches postings made in the last week. A req
posted 2+ months ago that's still open is invisible to it. For groups that returned 0, run an
occasional one-off deep pull:

1. Temporarily add `"timeRange": "6m"` and `"searchField": "titleSearch"` to those groups (the two
   are required together, see the `6m` note below).
2. Run them (one `--group` at a time).
3. Revert the config (`git checkout -- input/keywords_search.json` if it had no other edits).

Don't make `6m` a group's permanent setting: it would stop the fresh weekly pulls.

### Required: 6-month backfill whenever a search title is added
The actor's `date_posted` is the **original** posting date. LinkedIn shows reposted jobs as new
("1 week ago"), but the actor doesn't, so a `7d` search never returns them. Weekly runs therefore
only cover postings made *after* a title was added to the search. **Whenever a keyword, word-order
permutation, or broad title is added, run a one-time `6m` + `titleSearch` pull for just the new
phrases** as a temporary group (e.g. "Backfill New Titles"), then remove that group. Rate its
results like any other group. Raise its `limit` so the remote run doesn't hit its fetch cap
(`limit + 50`, max 5000), or the oldest postings are silently cut off.

### Rebuilding from existing datasets
```bash
python3 bin/fetch_and_build.py --remote <datasetId> [--local <datasetId>] \
  --term "High Signal" --output output/High_Signal_LinkedIn_Jobs.xlsx [--limit 100]
```

---

## How the Actor Is Called (and why)

- **One run per keyword, per area.** `titleSearch` accepts an array, but multi-keyword arrays are
  not reliable: a two-keyword array was seen returning matches for only one of them, while the other
  keyword alone returned real matches. So each keyword gets its own run, and results are merged
  locally. Runs cost $0.0001 to start, so this is cheap.
- **Two runs per keyword:**

| Run | Actor input | Returns |
|-----|-------------|---------|
| remote | `locationSearch` = `searchArea.remote.locationSearch` (default `["United States"]`), `aiWorkArrangementFilter: ["Remote Solely", "Remote OK"]`, `aiLanguageFilter` (default `["English"]`) | remote jobs in that country |
| local (only if `searchArea.local` is set) | `locationSearch` = `searchArea.local.locationSearch`, `aiWorkArrangementFilter: ["On-site", "Hybrid"]` | on-site/hybrid jobs in the local area |

- **The remote run must have a `locationSearch`.** Without one the actor returns English-language
  remote jobs from anywhere: one test run came back 10/10 UK/EU postings. `locationSearch` is phrase
  matching, so `"United States"` matches any `"…, United States"` location.
- **Default input per run:** `titleSearch: [keyword]`, `timeRange: "7d"`,
  `descriptionType: "text"`, `limit: group_limit + 50` (extra to cover dedup loss), plus
  `organizationSearch` when the group sets `companies`. The fetch limit applies to *each* run, so a
  group can pull up to (limit + 50) × 2 × keywords raw items before dedup.

---

## `input/keywords_search.json`

```json
{
  "searchArea": {
    "remote": {"locationSearch": ["United States"]},
    "local": {
      "name": "Greater Seattle",
      "locationSearch": ["Washington, United States"],
      "keywords": ["seattle", "bellevue", "redmond", "washington", ", wa"]
    }
  },
  "keywordCategories": {
    "Systems": ["Linux Kernel Engineer", "Escalation Engineer"]
  },
  "groups": [
    {"group": "High Signal", "keywords": ["Linux Kernel Engineer"], "permuteKeywords": true, "limit": 100},
    {"group": "Acme", "keywords-category": "Systems", "companies": ["Acme"], "limit": 100}
  ]
}
```

- **`searchArea`** (optional): `remote.locationSearch` (default `["United States"]`),
  `remote.languages` (default `["English"]`). `local` is optional: leave it out to search remote
  jobs only. `local.keywords` drives the location filter (case-insensitive substring match against
  each job's location), so list the area's towns, its state/region name, and its abbreviation
  pattern (e.g. `", wa"`).
- **`group`**: becomes the spreadsheet name (`<Group>_LinkedIn_Jobs.xlsx`, spaces → underscores),
  the sheet name, and the description folder name.
- **`keywords`** and/or **`keywords-category`**: a group's keyword list is the union of its own
  `keywords` and the referenced `keywordCategories` (a name or an array of names), deduped. An
  unknown category name, or a group with neither field, is an error, never an empty search.
  Categories exist so many company groups can share keyword lists while each company still gets
  its own isolated run (and its own fetch budget: merging companies into one group would let a
  high-volume employer crowd out a low-volume one).
- **`companies`** (optional): passed to `organizationSearch` (prefix match). Use company groups
  *on top of* keyword-only groups, never instead: a company list can't discover employers that
  aren't on it.
- **`searchField`** (default `"titleSearch"`): `titleSearch` matches titles only.
  `descriptionSearch` searches title and description, but the actor's vendor warns it's too
  intensive for broad use, and it has been seen being imprecise in both directions (missing an exact
  title match while admitting unrelated postings). Use it only for 1–3 very specific phrases that
  appear in body text rather than titles.
- **`timeRange`** (default `"7d"`): the actor only accepts `"1h"`, `"24h"`, `"7d"`, `"6m"`.
  **`6m` doesn't support `descriptionSearch`**: `run_search.py` refuses to start that combination.
- **`permuteKeywords`** (default false): also search every word order of each 2–3 word keyword
  ("Systems Software Engineer" → 6 phrases). `titleSearch` is phrase matching: word order matters,
  and there's no "all of these words" operator (`"A & B & C"` returns nothing). Different orders
  return different real titles ("Software Systems Engineer", "Engineer, Software Systems"). Use it
  on keyword-only groups; on company groups it multiplies runs fast.
- **`actorInput`** (optional): extra actor input merged into every run, e.g.
  `{"aiExperienceLevelFilter": ["5-10", "10+"], "titleExclusionSearch": ["Frontend", "iOS"]}`.
  Useful for a "Broad Titles" group of generic senior titles that no niche keyword catches.
- **`limit`** (default 100): max rows in the spreadsheet.
- A bare JSON array of groups (no `searchArea`, no categories) is also accepted.

---

## Combine, Deduplicate, Filter

- **Dedup** on the LinkedIn job ID across all of a group's runs; remote wins over local.
- **Same title + company under different IDs is flagged, not dropped.** It may be one job reposted
  per city, or separate openings sharing a generic title. Later copies get a **Dup Of** value
  pointing at the first copy's entry number, and the scrape summary counts them (with how many share
  the same description or location). Flagged rows count toward the group's row limit.
- **Excluded if** the workplace isn't remote (`"Remote Solely"`, `"Remote OK"`, legacy `"Remote"`)
  **and** the location doesn't match `searchArea.local.keywords`. The actor's
  `aiWorkArrangementFilter` is AI-derived, so remote results are already accurate; the location
  check is a safety net for the local run.
- **Excluded if expired:** `date_valid_through` is a parseable timestamp already in the past at build
  time (applied even with `--skip-filter`). Missing values are treated as unknown, not expired, and a
  row that's valid at build time can still close before anyone reads it.

---

## Output

### Spreadsheet: `output/<Group>_LinkedIn_Jobs.xlsx`, sheet `<Group> Jobs`
| # | Column | Source |
|---|--------|--------|
| 1 | Job Title | `title` |
| 2 | Company | `organization` |
| 3 | Location | `locations_derived[0]` |
| 4 | Date Posted | `date_posted` → `YYYY-MM-DD` |
| 5 | Salary Range | `ai_salary_min_value`/`max_value` → `"$X - $Y"` + unit (`/yr`, `/mo`, `/wk`, `/hr`); `"$X"` if one value; blank if none |
| 6 | Seniority Level | `seniority` |
| 7 | Employment Type | `ai_employment_type[0]` |
| 8 | Workplace | `ai_work_arrangement` |
| 9 | Search Term | group name |
| 10 | LinkedIn URL | `url` (clickable) |
| 11 | Description File | e.g. `001_Company_Title.txt` |
| 12 | Dup Of | blank, or the entry number of the earlier row with the same title + company |

A rating pass appends **Match Score** (color-coded green → red for 1 → 5), **Match Notes** and
**Missing Requirements**, and re-sorts rows best first. Entry numbers follow the original build
order, so use the Description File column to find a row's file after sorting.

Styling: dark blue header (`1F4E79`, white bold Arial 11, height 30), alternating `D6E4F0`/white
rows, Arial 10 wrapped and top-aligned, column widths 45, 30, 28, 14, 32, 18, 18, 12, 22, 60, 35, 9,
frozen first row and column, auto-filter on.

### Description files: `output/<Group>/<NNN>_<Company>_<Title>.txt`
Company and title sanitized (special characters removed, spaces → underscores, 40 chars max each).
Content: a header (Job Title, Company, Location, Workplace, Posted, URL), a 60-dash rule, then the
full description text.

### Scrape summary: `output/<Group>_scrape_summary.md`
Written for every group on every non-dry run:

| Group | Remote | Local | Included | Excluded | Expired | Possible Dups | Cost |

- Remote/Local: raw items from all of the group's runs, before dedup and filtering.
- Excluded also counts jobs dropped by the row limit.
- **Cost is read from Apify, not estimated:** the sum of each run's `usageTotalUsd`, read *after*
  the results are downloaded. Apify posts per-item charges a little after a run finishes, so reading
  at SUCCEEDED undercounts badly (a 176-item run once read as $0.0004 instead of $0.88);
  `final_run_cost()` re-reads until the charged item count matches.
- A failed group shows `—` in the counts and its error under `## Errors`.
- One file per group (not one shared file), so runs of different groups never overwrite each other.

### Archiving
Before writing a group's results, `run_search.py` checks the group's last scrape date in
`output/.archive_state.json`. If it was in a different ISO week, the old spreadsheet and description
folder move to `output/OLD/<yymmdd>/` (the old scrape's date). Same-week reruns replace in place.
- **Tracked dates, not file times:** any edit to a spreadsheet (e.g. applying ratings) changes its
  modification time, which once made a new week's scrape look like a same-week rerun and silently
  overwrote rated data. Only the build step updates the tracked date.
- **Per group:** groups run on different days archive independently, so `OLD/` can hold several
  thin dated folders.
- **The description folder and spreadsheet are always deleted before a rebuild**, same-week reruns
  included: otherwise a rerun with fewer results leaves orphaned files, or an old spreadsheet
  pointing at deleted files.
- A group that returns 0 after archiving has no spreadsheet until its next non-empty run; that's
  intended (the summary shows the 0).
- Scrape summaries and `rating_summary.md` archive the same way, under their own state keys.

---

## Rating Jobs Against the Resume (in-session sub-agents)

Ratings come from Claude sub-agents in the session, reading the resume in the workspace's
`input/resume/` (the newest `resume_<yymmdd>.pdf` unless the user says otherwise) and each job's
description file. There's no API key and no rating script. Split the jobs into batches of about 40
and give every sub-agent **these exact criteria**. The hard-requirements rule is mandatory: never
soften it.

### Step 1: hard requirements
Find the Requirements section (or "Must Have", "Qualifications", "You Will Need", etc.) and list every
hard requirement: specific programming languages, specific tools/platforms/frameworks (AWS,
Kubernetes, CI/CD, Spring Boot, Kafka…), and required certifications or clearances. Check each
against the resume and list what's missing.

### Step 2: score
| Score | Label | Criteria |
|-------|-------|---------|
| 1 | Excellent | Strong domain + skill alignment, right level, **zero missing hard requirements** |
| 2 | Good | Mostly aligned, minor soft gaps only, **zero missing hard requirements** |
| 3 | Moderate | Good domain fit **but at least one hard requirement missing**, OR notable experience/level gap |
| 4 | Weak | Multiple hard requirements missing, OR significantly misaligned domain |
| 5 | Poor | Wrong domain entirely, wrong level, or most required skills absent |

**Missing even ONE hard requirement rules out a 1 or 2**, however well the domain fits.

### Output per job
```json
{"file": "<filename>", "score": <1-5>, "reason": "<one sentence, max 20 words>", "missing": "<comma-separated missing hard requirements, or empty string>"}
```

### After rating
1. **Make identical postings consistent.** The same posting often appears several times (one row per
   city, or in several groups), and different sub-agents can score the copies a point apart. Group
   ratings by identical description text and give every copy the best score among them, with that
   copy's reason and missing list.
2. Apply each group's ratings:
   `python3 bin/apply_ratings.py --xlsx output/<Group>_LinkedIn_Jobs.xlsx --ratings <group.json>`
3. Write the cross-group summary from `{"<Group>": [ratings...], ...}`:
   `python3 bin/write_rating_summary.py --ratings <all.json>`. It produces score distributions per
   group, Top Matches (1–2 with no missing hard requirements), and the most common gaps among 4–5s.
4. Refresh the skill-gap report (below).

---

## Skill Gaps: What to Learn to Raise Scores

```bash
python3 bin/skill_gaps.py                 # this week + OLD/ archives
python3 bin/skill_gaps.py --current-only  # this week only
```
Reads Missing Requirements from every rated spreadsheet, maps each phrase to a learnable topic (the
`TOPICS` table in the script), and writes `output/skill_gaps.md`. Skills are ranked by **leverage**,
not raw frequency, because raw counts are dominated by score 4–5 jobs in the wrong domain, where
learning one tool changes nothing:

`leverage = 3 × one-away + 1 × score-3 jobs listing it + 0.5 × score-4 jobs with at most one other gap`

**One-away** = score-3 jobs where the skill is the only gap. **Near-fit %** = how often the skill
appears in jobs already close to the candidate. Jobs are deduped by company + title. If
`input/study_library.json` exists, a **Study doc** column shows which docs in the workspace's
`library/` cover each skill, or "none yet". The report is rebuilt from all history each run, so it's
overwritten, not archived.

---

## Cost Reference

Pay per event (`PAY_PER_EVENT`): **$0.005 per job returned**, **$0.0001 per run started** (verified
against Apify run objects; older docs claiming $0.01 per start were wrong by 100×). The recruiter
add-on (`recruiterOnly`, +$0.01/job) isn't used.

Ceiling per keyword with `limit: 100` (fetch cap 150/run, 2 runs): about **$1.50**, so about
$1.50 × N for a group of N keywords. Company groups usually cost far less, bounded by the company's
real posting volume; keyword-only groups come closest to the ceiling. Don't estimate: the actual cost
of every run is in its scrape summary (from `usageTotalUsd`, `GET /v2/actor-runs/{runId}`).

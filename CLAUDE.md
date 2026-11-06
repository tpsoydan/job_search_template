# Job Search Workspace

A workspace for one person's job search: find jobs, rate them against the resume, see which skills
would raise the ratings, study, and prepare for interviews. It's a copy of a generic template with the
person's own material added on top.

## Start of every session

1. **Read `input/profile.md`.** It says who the user is, what they're looking for, and their working
   rules for Claude. Follow those rules as if they were written here.
2. **If `input/profile.md` doesn't exist, this is a new workspace:** run First-Time Setup (below)
   before anything else.

---

## Layout and pipeline

```
<workspace>/
├── CLAUDE.md, README.md      ← this file; README is for humans
├── input/                    ← shared personal input
│   ├── profile.md            ← who the user is (personal)
│   ├── resume/               ← resume_<yymmdd>.pdf/.docx versions (personal)
│   └── example/profile.md    ← template example
├── library/                  ← reusable study docs (personal), see library/README.md
├── job_scraper/              ← find and rate jobs; see job_scraper/CLAUDE.md
└── job_interview_prep/       ← per-job interview prep; see job_interview_prep/CLAUDE.md
```
Other top-level folders (e.g. a job-search activity log kept for unemployment benefits) may exist in
a particular workspace. They're personal and described in `input/profile.md`.

How the pieces connect:
1. **Resume** (`input/resume/`) is the basis for everything.
2. **Scrape** jobs weekly (`job_scraper/`), then **rate** them against the resume.
3. **Skill gaps** (`job_scraper/output/skill_gaps.md`) show which skills would raise the most ratings,
   and which have study docs in `library/` yet.
4. **Study:** write docs for the gaps into `library/`.
5. **Prep:** a promising job or an interview invitation becomes a folder in `job_interview_prep/jobs/`,
   which draws on `library/` and promotes reusable docs back into it.

Each sub-project's CLAUDE.md has its details. Read it before working in that folder.

---

## Template files vs. personal files

The workspace mixes files from the template with the user's own. They never share a path, which is
what lets template updates merge cleanly. **Personal content lives only in:**
- `input/` (except `input/README.md` and `input/example/`)
- `library/` (except `library/README.md`)
- `job_scraper/input/` (except `job_scraper/input/example/`) and `job_scraper/output/`
- `job_interview_prep/jobs/` (except `jobs/new_job_skeleton/`)
- any `ignore/` folder, and any top-level folder the template doesn't ship

**Everything else comes from the template:** all CLAUDE.md and README.md files, `.gitignore`,
`.claude/settings.json`, `job_scraper/bin/`, the `example/` folders and `new_job_skeleton/`.

Rules:
- **Never put personal information in a template file:** no names, employers, companies being
  targeted, locations, or dated notes about the user's own search. Those go in `input/profile.md` or
  another personal file. Template files describe how things work, for anyone.
- **Don't edit template files for one person's needs.** If a change to one would help anyone, it's a
  generic improvement: make it as its own commit, with nothing personal in it, and offer to send it
  back to the template (below).
- `ignore/` folders are the user's scratch space: don't read them, and git doesn't track their
  contents.

---

## First-Time Setup

When `input/profile.md` is missing, interview the user and build their personal files. Ask in small
groups, not all at once, and show each file before saving it.

1. **Profile:** background summary, target roles, companies of interest, roles that fit best,
   location and work arrangement (remote, hybrid, on-site), and working rules for Claude. Start from
   `input/example/profile.md`. Save as `input/profile.md`.
2. **Resume:** ask the user to put their resume in `input/resume/` as `resume_<yymmdd>.pdf` (plus the
   `.docx` if they edit it in Word). Read it, and use it to suggest target roles and search keywords.
3. **Job search config:** build `job_scraper/input/keywords_search.json` from
   `job_scraper/input/example/keywords_search.json`: the search country, the local area and its town
   names (or remote only), and keyword groups from their target roles and companies. Explain the
   group types (keyword-only, company-scoped, broad titles) and suggest a starting set.
4. **Apify:** check that `APIFY_TOKEN` is set (without printing it). If it isn't, explain how to get
   a token from apify.com and set it in their shell startup file, then restart Claude Code.
5. **Dry run:** `python3 bin/run_search.py --dry-run` from `job_scraper/`, so they can see what a
   real run would do and cost before spending anything.
6. **Commit** the personal files to the workspace repo, once the user approves.

---

## Template updates and sending improvements back

The workspace is a git clone of the template; the template is the `upstream` remote and the user's
own (private) repo is `origin`, once they have one.

- **Getting updates:** `git pull upstream main`. It merges cleanly as long as personal and template
  files stay separate. If it conflicts, a template file was edited locally: stop and show the user.
- **Sending an improvement back:**
  1. Commit the generic change on its own, never mixed with personal changes.
  2. `git fetch upstream && git switch -c <short-name> upstream/main`
  3. `git cherry-pick <commit>`. Check the branch contains nothing personal (`git diff upstream/main`).
  4. Push and open a pull request. The template owner can push to `upstream` directly; anyone else
     pushes to their own public fork and runs `gh pr create --repo <owner>/<template-repo>`. With a
     local-only template (no GitHub yet), merge it in the template folder:
     `git pull <workspace-path> <short-name>`.
  5. `git switch main && git pull upstream main`.
- **Never push the workspace's `main` to `upstream`:** it contains personal files.

---

## Rules for every part of the workspace

- **Never print, log or commit secrets** (the Apify token, passwords, account numbers).
- **Consistent names:** `input/` and `output/` folders, dates as `yymmdd` in file and folder names
  (`resume_<yymmdd>.pdf`, `<yymmdd>_<Company>_<Role>/`, `OLD/<yymmdd>/`).
- Commit only when the user asks, unless their profile says otherwise.

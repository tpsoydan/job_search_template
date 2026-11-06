# Job Interview Prep

Prepares the candidate for a specific job's interviews: analyzes the resume against the job
description, audits existing study material, and produces study docs and an interview strategy
calibrated to what the candidate already knows. Reusable material from each job is promoted to the
workspace's shared `library/`, so the next job starts from it.

---

## Layout
```
<workspace>/
├── input/profile.md            ← who the candidate is (read it first)
├── input/resume/               ← master resume versions (resume_<yymmdd>.pdf); never edited here
├── library/                    ← reusable study material, shared by every job (see below)
└── job_interview_prep/
    ├── CLAUDE.md               ← this file
    ├── README.md               ← how to start a new job (for humans)
    ├── ignore/                 ← scratch space; never read it, contents not tracked
    └── jobs/
        ├── PRIOR_PREP_PROJECTS.md     ← catalog of every job folder (personal; created with the first job)
        ├── new_job_skeleton/          ← template-owned: copied to start a job, never edited
        └── <yymmdd>_<Company>_<Role>/ ← one folder per job
            ├── PROJECT_STATE.md       ← restore-context snapshot for cold starts
            ├── TIMELINE.md            ← what was written when
            ├── ignore/
            ├── input/                 ← this job's raw material: JD, submitted resume, emails
            └── output/                ← everything generated for this job
```

**`library/` vs. a job's `input/`:** `library/` holds content reused across applications (career
history, domain study docs, behavioral answers). A job's `input/` holds material for that one
application only (its JD, recruiter emails, assessment instructions), never `library/` content.

**`library/` is split by area, not flattened**, e.g. `career_accomplishments/`, `general/`, and one
folder per technical domain or target company (`os/linux/`, `cloud/`, `<company>/` ...). Then a
new job can reference a whole relevant folder instead of picking files one by one. Create a new area
folder when nothing fits.

Paths in this file are relative to `job_interview_prep/`; from inside a job folder, the library is
`../../../library/` and the resume folder is `../../../input/resume/`. Reference library files where
they are: don't copy or symlink them into a job's `input/`.

---

## Workflow

Follow these steps in order when working on a job.

### 0. Create and register the job folder
If the job has no folder yet: copy `jobs/new_job_skeleton/` to `jobs/<yymmdd>_<Company>_<Role>/`
(`yymmdd` = the date the lead came in or the first interview, whichever the candidate prefers; ask
once and note the choice in `input/profile.md`). Then add a stub entry to `jobs/PRIOR_PREP_PROJECTS.md`
(if the file doesn't exist yet, create it with the header shown below) with at least: a bolded `**Path:**` field (`jobs/<folder>`), role and company, how the lead came in
(referral, recruiter, direct application...), and status `In progress`. If an entry already exists,
skip this step.

The catalog is personal, so the template doesn't ship it (a template copy would conflict with your
entries on every template update). Header for a new catalog:

````markdown
# Prior Interview-Prep Projects

Catalog of every job folder in `jobs/`: what it was for, how it went, and what's worth going back to.
This is an index, not a copy: content lives in each job's folder, or in `library/` once promoted.

List every job's location with: `grep '\*\*Path:\*\*' jobs/PRIOR_PREP_PROJECTS.md`

Entry format:

```
## <Company> — <Role> (req <number>, if known)

- **Path:** `jobs/<yymmdd>_<Company>_<Role>`
- **Sourced:** how the lead came in (referral from ..., recruiter outreach, direct application)
- **Status:** In progress | Offer | Rejected <date> | Withdrawn <date>
- **Interview rounds:** <date> — <type> with <interviewer>; ...
- **Promoted:** what moved to library/ and where; what stayed local
```

---
````

### 1. Ingest source material
**Preflight:** the job's `input/` must contain at least one job description (PDF or text) and the
resume snapshot actually submitted (`resume_<yymmdd>.pdf`). If either is missing, stop and say
exactly what's missing and where it goes. Don't substitute other material (a recruiter email, a
resume from another job, a posting found online), and don't start the match analysis without both.
If the candidate says no JD exists (e.g. an unposted req), note that in `PROJECT_STATE.md` and work
from whatever description they can give.

If `input/prompts.txt` exists, read it first. Then read the job's `input/`, the candidate profile,
and the `library/` areas relevant to the role.

### 2. Resume vs. JD match analysis
- Map the resume's skills and experience against each JD's requirements and "nice to have" sections.
- Produce a **strength map** and a **gap analysis**.
- Note **framing opportunities**: experience that maps to a requirement but isn't phrased that way.
- With several JDs, compare them and note where they diverge.
- Save as `output/resume_jd_match_analysis.md`.
- Turn the framing opportunities into `output/resume_tailoring_suggestions.md`: concrete before/after
  wording, each tied to the requirement it addresses. Advisory only (see Resume Handling).

### 3. Audit existing study material
Review the job's `input/` and the relevant `library/` areas for:
- **Redundancies:** content duplicated across files or within one. Say exactly what duplicates what.
- **Missing coverage:** topics the JD requires or prefers that no document covers.
- **Structural issues:** poorly organized files, technical content mixed with pitch content, etc.

Report findings before changing anything.

### 4. Calibrate to the candidate's knowledge
Before writing study docs, ask about each gap from step 3: how familiar the candidate really is
with it, and what prior experience could serve as a bridge. Skip what they know, bridge from what
they know to what's new, and put depth only where the material is genuinely new.

### 5. Produce output documents
Everything new or updated goes in the job's `output/`. Never modify its `input/`.

| File | Purpose |
|---|---|
| `resume_jd_match_analysis.md` | Strengths, gaps, framing advice |
| `consolidated_<domain>_foundation.md` | Deduplicated technical reference for the core domain |
| `<topic>.md` | Study guide for one missing area, one file per topic |
| `<employer>_accomplishments.md` | Accomplishments re-angled toward this JD, built from `library/career_accomplishments/` |
| `interview_strategy.md` | Pitches, audience-specific angles, gap bridges, opening/closing, questions to ask |

Descriptive names only, no numeric prefixes: which docs a job needs, and in what order, varies too
much for a numbering scheme to stay meaningful.

### 6. Calibration principles
- Don't over-explain what the candidate already knows.
- **Bridge from known to new:** explain an unfamiliar technology through a familiar analogous one.
  Named bridges make new material stick.
- Put **interview-ready phrasings** in technical docs as callout blocks.
- Audience-aware pitch content belongs in `interview_strategy.md`, not scattered across technical
  docs.
- Be technically accurate: correct terminology, real commands and code, correct mental models.

### 7. Promotion review
Decide which `output/` content moves into `library/`. Do it **at wrap-up** (offer, rejection,
withdrawal, or the job going quiet), in the same session as the catalog update, and optionally at a
milestone such as just before an interview round, for docs that have settled.

Start from the "Library Candidates" list in the job's `PROJECT_STATE.md` (add to it as reusable
docs get written). Sort each `output/` doc into a bucket and **show the candidate the list before
touching `library/`**:

| Bucket | Test | Examples |
|---|---|---|
| **Promote** | Serves any future role in the same domain; facts don't depend on this JD or company | Domain study doc → `library/<area>/`; new career story → `library/career_accomplishments/`; JD-independent behavioral answer → `library/general/` |
| **Correct** | Fixes or extends something already in `library/` | A corrected date, a newly verified fact |
| **Stays local** | Angled toward this JD, company or interviewers | Match analysis, tailoring suggestions, interview strategy, anything naming people or referral context |

Promoted content is stripped of job-specific framing (interviewer names, referral context,
company-specific pitch) and written into the right `library/<area>/`. Record what was promoted, where,
and what stayed local in the job's catalog entry.

---

## Reusable Material (`library/`)

- **Before writing an accomplishments doc, start from
  `library/career_accomplishments/<employer>_career_history.md`** and re-angle facts toward the JD.
  Don't regenerate the underlying facts.
- **Before writing a technical study doc, check `library/<area>/`.** A domain corpus built for one
  role usually covers much of the next same-domain role, even at another company or level.
- `library/general/` holds behavioral-question answers and generic questions to ask: adapt them into
  the job's `output/`, don't rewrite them.
- **A factual correction** found during a job (a date, a role detail, a verified number) goes straight
  into `library/` after the candidate confirms it, so it's right for every future job. Don't leave it
  correct in only one job's output.
- Regenerate a section from scratch only if the role needs a framing that re-angling can't produce.

---

## Rules

- **Output documents are Markdown only.** No PDF versions.
- **Ignore `ignore/` folders and any `OLD/` or `BKP/` folders.**
- **A job's `input/` is read-only.** All new and updated content goes in its `output/`, even when it
  supersedes something in `input/`.
- **Report redundancies and gaps before changing anything**, and get approval before large changes.
- Don't create documentation for its own sake: every output doc should fill a real gap or replace a
  genuinely redundant input.
- **Resume handling:** master resume versions live in the workspace's `input/resume/`. Never create
  or edit a resume file. Each job's `input/` holds a read-only copy of the exact version submitted.
  Resume feedback is always the advisory `output/resume_tailoring_suggestions.md`, which the candidate
  applies to the master themselves.
- **Keep the catalog current.** Whenever an outcome lands, an interview round happens, or content is
  promoted, update the job's entry in `jobs/PRIOR_PREP_PROJECTS.md` in the same session.
- **Never edit `jobs/new_job_skeleton/`, this file or `README.md` for one job's needs.** They're
  template files: a genuine improvement to them is a generic change (see the workspace CLAUDE.md on
  sending changes back to the template).

---

## Quality Bar

Each study doc should let the candidate:
1. Explain the topic correctly to a senior engineer in that domain
2. Answer follow-up questions without being caught flat-footed
3. Connect it naturally to their own experience

The interview strategy should give ready-to-use language for every significant gap between the
candidate's background and the JD.

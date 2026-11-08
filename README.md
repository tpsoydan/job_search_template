# Job Search Template

A Claude Code workspace for running a job search:

- **Find jobs:** scrape LinkedIn weekly by keyword and company with an Apify actor, into one
  spreadsheet per keyword group, plus the full text of every job description.
- **Rate them:** Claude rates every job against your resume (1–5, with the missing requirements
  listed), and summarizes the best matches.
- **See what to learn:** a skill-gap report ranks the skills that would raise the most ratings, and
  shows which ones you have study material for.
- **Prepare for interviews:** a folder per job, where Claude analyzes your resume against the job
  description, finds gaps, and writes study docs and an interview strategy calibrated to what you
  already know. Reusable docs go into a shared library for the next job.

Claude Code does the work; the `CLAUDE.md` files tell it how.

## Prerequisites

- [Claude Code](https://claude.com/claude-code)
- Python 3, with `openpyxl` (`pip install openpyxl`)
- An [Apify](https://apify.com) account. Put its API token in the `APIFY_TOKEN` environment variable
  (in your shell startup file). Scraping costs about $0.005 per job returned.
- git, and the [`gh` CLI](https://cli.github.com) for the GitHub steps

## Setup

Template URL: `https://github.com/tpsoydan/job_search_template.git`

1. Get your own copy, either way:
   - **Clone it:** `git clone https://github.com/tpsoydan/job_search_template.git my_job_search`
   - **Or** use GitHub's **Use this template** button to create a new **private** repo, then clone
     that.

   Keep your workspace **private**: it will hold your resume and job search details. Don't fork this
   repo: a fork of a public repo is always public.
2. Start Claude Code in the folder:
   ```
   cd my_job_search
   claude
   ```
   Say something like "help me set up my job search". Claude first sorts out the git remotes: this
   template becomes `upstream`, so you can pull later improvements, and your own private repo becomes
   `origin` (Claude offers to create it). Then it walks you through setup: your background and
   targets, your resume (put it in `input/resume/` as `resume_<yymmdd>.pdf`), your search config, and
   a dry run.

## Using it

- "Run this week's job scrape", then "rate the results"
- "Which skills should I learn to improve my scores?"
- "Start interview prep for the <Company> <Role> job"

## Layout

```
CLAUDE.md               how the workspace fits together (for Claude)
input/                  your profile and resume versions
library/                your reusable study docs
job_scraper/            scraping, rating, skill gaps
job_interview_prep/     one folder per job you prepare for
```

Your own files live only in `input/`, `library/`, `job_scraper/input/`, `job_scraper/output/` and
`job_interview_prep/jobs/`. Everything else comes from this template.

## Updates and contributions

- **Get template updates:** `git pull upstream main`
- **Contribute an improvement:** commit the generic change on its own, then:
  ```
  git fetch upstream
  git switch -c my-fix upstream/main
  git cherry-pick <commit>
  git push <your-public-fork> my-fix
  gh pr create --repo <owner>/<template-repo>
  ```
  Branching from `upstream/main` is what keeps your personal files out of the pull request.

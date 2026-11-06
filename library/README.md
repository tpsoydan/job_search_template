# library/

Your reusable study and reference material, shared by every job you prepare for and linked from the
skill-gap report. It starts empty and grows as interview prep promotes reusable docs into it (see
step 7 of `job_interview_prep/CLAUDE.md`).

Organize it by area, one folder per domain or target company, so a new job can use a whole folder:

```
library/
├── career_accomplishments/   <employer>_career_history.md: neutral facts, not angled to any job
├── general/                  behavioral answers, generic questions to ask interviewers
├── os/linux/                 e.g. kernel internals, debugging playbook
├── cloud/                    e.g. Kubernetes, AWS
└── <area>/                   add folders as domains or target companies come up
```

What belongs here: anything that would help with any future job in that area. What doesn't: material
for one job (its job description, interviewer names, company-specific pitch), which stays in that
job's folder.

To have the skill-gap report point at these docs, list them in `job_scraper/input/study_library.json`
(example in `job_scraper/input/example/`).

This README comes from the template; everything else here is yours.

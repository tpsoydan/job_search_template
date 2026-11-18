# Job Interview Prep

Interview preparation for specific jobs, driven by `CLAUDE.md` in this folder. Each job gets its own
folder under `jobs/`. Reusable material (career history, study docs, behavioral answers) lives in the
workspace's shared `library/`, so every new job starts from what earlier jobs produced.

## Starting a new job

The easiest way is to ask Claude: start Claude Code in the workspace and say something like
"start interview prep for the Acme Staff Engineer role". It follows step 0 of `CLAUDE.md`. To do it
by hand:

1. Copy the skeleton:
   ```
   cp -R jobs/new_job_skeleton jobs/<yymmdd>_<Company>_<Role>
   ```
2. Put the job's material in its `input/`:
   - the job description(s), PDF or text
   - **a copy of the resume version you submitted** (`resume_<yymmdd>.pdf`, from the workspace's
     `input/resume/`): a read-only snapshot of what the employer saw
   - related emails or assessment instructions
   - optionally `prompts.txt` with anything else Claude should know
3. Start Claude Code and ask it to begin. `CLAUDE.md` drives the rest: catalog entry → ingest →
   resume/JD match analysis → audit of existing material → calibration questions → study docs and
   interview strategy → promotion review at wrap-up.

## Notes

- Answer the calibration questions honestly. They're what keep study docs from over-explaining what
  you already know.
- If a new job is similar to an earlier one, say so up front: Claude can adapt that job's `output/`
  instead of starting over.
- `ignore/` folders are your scratch space: Claude doesn't read them and git doesn't track their
  contents.
- Don't edit `jobs/new_job_skeleton/`, `CLAUDE.md` or this README for one job. They come from the
  template; improvements to them go back to the template (see the workspace README).

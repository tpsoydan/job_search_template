# Output Directory Timeline

*This is a generic skeleton, copied from `jobs/new_job_skeleton/`.*

Source entries from `git log -- .` (exact times) where the work is committed. For anything uncommitted, reconstruct from file modification times (`stat`/`ls -la` on `output/`) and label it approximate, since same-minute ordering can't be trusted from modification times.

## [YYYY-MM-DD] — Session N ([one-line session summary])
- HH:MM `<file>` created/revised — [what changed, one line]
- ...

## Known issues / notes

- [Anything discovered while reconstructing the timeline worth flagging — e.g., a doc that hasn't been revised since creation and should be double-checked before relying on it.]
- [Upcoming interview dates worth flagging as a reason to expect a revision pass before then.]

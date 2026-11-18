# Roadmap

Planned changes to the template, so workspace users can see what's coming in future
`git pull upstream main` updates. Nothing here is personal: workspace-specific to-dos belong in that
workspace's own state files.

When an item ships, delete it here. The commit that adds the feature is its record.

## Planned

### Unemployment benefits area (`unemployment/`)

For workspaces whose owner is claiming unemployment benefits while job searching. Most agencies
require a weekly work-search record that has to match what was reported, and that must hold up in an
audit or fact-finding.

- `unemployment/CLAUDE.md` and `README.md`: how the area works, written jurisdiction-neutral. The
  agency's own rules (activities per week, accepted categories, how earnings are reported) go in a
  personal `unemployment/claim.md`, the way the search country lives in the scraper config.
- Weekly activity log: one folder per claim week, with activity folders named
  `<yymmdd>_<Verb>_<Company>_<detail>/` that hold the evidence (emails, screenshots, confirmations).
  Standard verbs (Apply, Interview, Network, FollowUp, Schedule, Prepare, Update, Register), mapped
  to the agency's activity categories.
- Tracking spreadsheet layout: one row per activity, including the category the agency logged, plus
  a claim row per week.
- Reconciliation routine: download the agency's own work-search log and benefit details, then
  cross-check them week by week against the spreadsheet and the activity folders.
- Issue folders (`issue-<description>/` with `input/` and `output/`) for fact-finding requests and
  appeals, and a `STATUS.md` with current status, next steps and a session log.
- `example/`: a sample week, a sample activity, an empty spreadsheet, and sample `claim.md` and
  `STATUS.md` files (one US state as the worked example).
- Link to job prep: when an application, interview or recruiter contact is recorded in
  `prep/` or `input/jobs/`, Claude offers to log it as that week's activity.
- Root CLAUDE.md: add `unemployment/` to the layout and to the template/personal file rules, and add
  a First-Time Setup question (claiming benefits? which state or country?).

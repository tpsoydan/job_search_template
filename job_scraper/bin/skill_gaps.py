"""
Ranks which skills a candidate could learn to raise their job match scores
most efficiently, from the Missing Requirements column of every rated
spreadsheet in output/ (current week plus OLD/ archives), and writes
output/skill_gaps.md.

Raw "most often missing" counts are misleading: they are dominated by score
4-5 jobs in domains the candidate doesn't fit, where learning one tool
changes nothing. So each skill is weighted by how close the jobs needing it
already are:

  - One-away: score-3 jobs where this skill is the ONLY missing hard
    requirement. Learning it removes every hard gap, which is what the
    rating rules require for a 1 or 2. Weighted most.
  - In score 3: score-3 jobs that list it among their gaps.
  - In score 4: score-4 jobs that list it with at most one other missing
    skill (two-away). Score-4 jobs with longer gap lists are mostly domain
    mismatches, so they're excluded.
  - Near-fit %: of all jobs listing the skill, the share already at score 3.
    High means the skill shows up in jobs close to the candidate's domain;
    low means it mostly shows up in jobs that are far off anyway.
  - Score 5 jobs are shown for context but not weighted: they are the wrong
    domain, and learning a skill won't fix that.

  leverage = 3 x one-away + 1 x in-score-3 + 0.25 x in-score-4

Missing-requirement phrases are mapped to learnable topics with the TOPICS
table below (e.g. "KVM/QEMU nested virtualization" -> Virtualization).
Phrases matching no topic are reported as-is. Jobs are deduplicated by
company + title (the same posting is often listed once per city); the most
recent rating wins. Postings with a country-subdomain LinkedIn URL (e.g. pl.linkedin.com) are
skipped: they come from searches that weren't limited to one country.

If input/study_library.json exists, a "Study doc" column shows which docs in
the workspace's library/ cover each skill (or "none yet"), so the report also
shows where study material is still missing. Format:
    {"libraryRoot": "../library",
     "topics": {"Firmware: UEFI/BIOS/BMC": ["firmware/uefi_bmc_redfish.md"]}}
libraryRoot is relative to this job_scraper/ folder; topic names must match
the TOPICS table below.

Usage:
    python3 bin/skill_gaps.py
    python3 bin/skill_gaps.py --current-only   # skip OLD/
"""

import argparse
import glob
import os
import re
from collections import defaultdict
from datetime import datetime

import json

import openpyxl

# (topic, regex) — matched case-insensitively against each missing phrase.
# A phrase can hit several topics ("Docker/Kubernetes, Terraform").
TOPICS = [
    ("Linux device drivers", r"driver"),
    ("Firmware: UEFI/BIOS/BMC", r"uefi|bios|\bbmc\b|firmware|edk2|coreboot"),
    ("Virtualization: KVM/QEMU/VMware", r"\bkvm\b|qemu|vmware|hypervisor|virtuali[sz]"),
    ("Embedded/RTOS", r"rtos|vxworks|zephyr|embedded"),
    ("ARM/RISC-V architecture", r"\barm\b(?!\s*templ)|risc-?v|grace"),
    ("RDMA/HPC interconnects", r"rdma|infiniband|kernel.bypass|dpdk|nvlink|\bcxl\b"),
    ("GPU/CUDA/ML infrastructure", r"\bgpu|cuda|ml infra|mlops|slurm"),
    ("Kubernetes & containers", r"kubernetes|\bk8s\b|\beks\b|\bgke\b|\baks\b|openshift|helm|docker|container|\boci\b|\becs\b|istio"),
    ("Public cloud (AWS/GCP/Azure)", r"\baws\b|\bgcp\b|google cloud|azure(?! devops)|\bcloud\b(?!formation|watch)|govcloud"),
    ("Infrastructure as code (Terraform etc.)", r"terraform|pulumi|cloudformation|\bcdk\b|bicep|\biac\b|infrastructure.as.code|opentofu|terragrunt"),
    ("CI/CD & GitOps", r"ci/cd|\bci\b|jenkins|github actions|gitlab|argo|gitops|azure devops"),
    ("Config management (Ansible/Salt/Chef/Puppet)", r"ansible|salt|\bchef\b|puppet"),
    ("Observability (Prometheus/Grafana/OTel)", r"prometheus|grafana|datadog|opentelemetry|\botel\b|splunk|dynatrace|new relic|\belk\b|loki|cloudwatch|observability"),
    ("Go", r"\bgo\b|golang"),
    ("Python", r"python"),
    ("Rust", r"\brust\b"),
    ("C++", r"c\+\+"),
    ("Java/JVM", r"\bjava\b|kotlin|scala|spring|\bjvm\b|hibernate"),
    ("Web/frontend (TS/JS/React/Node)", r"react|typescript|javascript|node|angular|\bvue\b|next\.js|nestjs|graphql|full.stack"),
    ("Databases/SQL", r"postgres|mysql|\bsql\b|mongo|redis|nosql|\bdb2\b|snowflake|elasticsearch|clickhouse"),
    ("Streaming/data (Kafka/Spark/Flink)", r"kafka|flink|spark|airflow|pulsar|kinesis|\bsqs\b|data pipeline"),
    (".NET/C#/Windows", r"c#|\.net|powershell|windows|\biis\b"),
    ("Ruby/Rails", r"\bruby\b|rails"),
    ("Distributed systems/microservices", r"distributed|microservice|grpc|rest api|event.driven"),
    ("Networking (BGP/load balancers)", r"\bbgp\b|ospf|lan/wan|router|tcp/ip|load.balanc|haproxy|nginx|\bcdn\b"),
    ("AI/LLM tooling", r"\bllm|\brag\b|agentic|ai coding|ai development|claude code|cursor|langgraph|ai/llm|vector database"),
    ("Security clearance", r"clearance|\bsecret\b|public trust"),
    ("Mainframe (z/OS/COBOL)", r"z/os|cobol|mvs|\bjcl\b|smp/e|rexx"),
]
TOPIC_RES = [(t, re.compile(p, re.I)) for t, p in TOPICS]

W_ONE_AWAY, W_IN3, W_IN4 = 3.0, 1.0, 0.5


def clean_url(value):
    """The LinkedIn URL column holds =HYPERLINK("url","text"); return the url."""
    m = re.search(r'HYPERLINK\("([^"]+)"', str(value or ""))
    return m.group(1) if m else (value or "")


def is_us_url(url):
    m = re.match(r"https?://([a-z]{2,3})\.linkedin\.com/", url or "")
    return not m or m.group(1) == "www"


def split_missing(text):
    """Split on commas that aren't inside parentheses."""
    return [p.strip() for p in re.split(r",\s*(?![^()]*\))", text or "") if p.strip()]


def topics_for(phrase):
    hits = [t for t, rx in TOPIC_RES if rx.search(phrase)]
    return hits or [phrase.lower()]


def archive_date(path, out_dir):
    """Sort key: OLD/<YYMMDD>/ files by date, current files newest."""
    m = re.search(r"OLD/(\d{6})/", os.path.relpath(path, out_dir))
    return m.group(1) if m else "999999"


def load_jobs(out_dir, current_only):
    pattern = "*_LinkedIn_Jobs.xlsx" if current_only else "**/*_LinkedIn_Jobs.xlsx"
    files = sorted(glob.glob(os.path.join(out_dir, pattern), recursive=True),
                   key=lambda p: archive_date(p, out_dir))
    jobs = {}  # (company, title) -> job; later (newer) files overwrite
    dates = set()
    for f in files:
        ws = openpyxl.load_workbook(f, read_only=True).active
        header = [c.value for c in next(ws.iter_rows(max_row=1))]
        if "Match Score" not in header:
            continue
        dates.add(archive_date(f, out_dir))
        for row in ws.iter_rows(min_row=2, values_only=True):
            d = dict(zip(header, row))
            score = d.get("Match Score")
            if not isinstance(score, (int, float)):
                continue
            url = clean_url(d.get("LinkedIn URL"))
            if not is_us_url(url):
                continue
            key = (str(d.get("Company") or "").strip().lower(),
                   str(d.get("Job Title") or "").strip().lower())
            jobs[key] = {
                "company": d.get("Company"), "title": d.get("Job Title"),
                "score": int(score), "url": url,
                "missing": d.get("Missing Requirements") or "",
            }
    return list(jobs.values()), dates


def analyze(jobs):
    stats = defaultdict(lambda: {"one": [], 3: [], 4: [], "far4": [], 5: []})
    for j in jobs:
        if j["score"] < 3:
            continue
        topics = set()
        for phrase in split_missing(j["missing"]):
            topics.update(topics_for(phrase))
        for t in topics:
            if j["score"] == 4 and len(topics) > 2:
                stats[t]["far4"].append(j)
            else:
                stats[t][j["score"]].append(j)
        if j["score"] == 3 and len(topics) == 1:
            stats[next(iter(topics))]["one"].append(j)
    rows = []
    for t, s in stats.items():
        lev = W_ONE_AWAY * len(s["one"]) + W_IN3 * len(s[3]) + W_IN4 * len(s[4])
        rows.append((lev, t, s))
    rows.sort(key=lambda r: (-r[0], -len(r[2][5]), r[1]))
    return rows


def load_study_library(root):
    """{topic: [(relative_path, exists), ...]} from input/study_library.json."""
    path = os.path.join(root, "input", "study_library.json")
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        cfg = json.load(fh)
    lib = os.path.normpath(os.path.join(root, cfg.get("libraryRoot", "../library")))
    return {t: [(p, os.path.exists(os.path.join(lib, p))) for p in paths]
            for t, paths in cfg.get("topics", {}).items()}


def study_cell(topic, library):
    docs = [p for p, ok in library.get(topic, []) if ok]
    return ", ".join(f"`{p}`" for p in docs) if docs else "none yet"


def write_report(out_dir, jobs, dates, rows, top_n, library=None):
    counts = defaultdict(int)
    for j in jobs:
        counts[j["score"]] += 1
    span = sorted(d for d in dates if d != "999999")
    span_txt = f"{span[0]} to now" if span else "current week only"
    lines = [
        f"# Skill Gaps - {datetime.now():%Y-%m-%d %H:%M}",
        "",
        f"{len(jobs)} distinct rated jobs ({span_txt}): "
        + ", ".join(f"{counts[s]} scored {s}" for s in range(1, 6)) + ".",
        "",
        "Skills ranked by how many near-miss jobs learning them would help. "
        "**One-away** = score-3 jobs where this is the only missing hard "
        "requirement, so learning it could lift the job to a 1 or 2. "
        f"Leverage = {W_ONE_AWAY:g} x one-away + {W_IN3:g} x score-3 + "
        f"{W_IN4:g} x score-4 (only score-4 jobs with at most one other gap). "
        "**Near-fit %** = share of all jobs listing the skill that already "
        "scored 3: high means it shows up in jobs close to the candidate's "
        "domain. Score-5 jobs are the wrong domain; they count only toward "
        "the total.",
        "",
        "| # | Skill | Leverage | One-away | Score 3 | Score 4 (two-away) | All jobs listing it | Near-fit % |"
        + (" Study doc |" if library is not None else ""),
        "|---|-------|---------:|---------:|--------:|-------------------:|--------------------:|-----------:|"
        + ("-----------|" if library is not None else ""),
    ]
    shown = [r for r in rows if r[0] > 0][:top_n]
    for i, (lev, t, s) in enumerate(shown, 1):
        total = len(s[3]) + len(s[4]) + len(s["far4"]) + len(s[5])
        pct = 100 * len(s[3]) / total if total else 0
        lines.append(f"| {i} | {t} | {lev:.1f} | {len(s['one'])} | {len(s[3])} "
                     f"| {len(s[4])} | {total} | {pct:.0f}% |"
                     + (f" {study_cell(t, library)} |" if library is not None else ""))
    lines += ["", "## Jobs behind the top skills", ""]
    for lev, t, s in shown[:10]:
        examples = s["one"] + [j for j in s[3] if j not in s["one"]]
        if not examples:
            continue
        lines.append(f"**{t}**")
        for j in examples[:6]:
            tag = "only gap" if j in s["one"] else f"also missing: {j['missing']}"
            link = f" — {j['url']}" if j.get("url") else ""
            lines.append(f"- {j['company']} — {j['title']} ({tag}){link}")
        lines.append("")
    path = os.path.join(out_dir, "skill_gaps.md")
    with open(path, "w") as fh:
        fh.write("\n".join(lines).rstrip() + "\n")
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--current-only", action="store_true",
                    help="Only this week's spreadsheets, not OLD/ archives")
    ap.add_argument("--top", type=int, default=25, help="Rows in the ranking table")
    args = ap.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(root, "output")
    jobs, dates = load_jobs(out_dir, args.current_only)
    if not jobs:
        raise SystemExit(f"No rated spreadsheets found in {out_dir}")
    path = write_report(out_dir, jobs, dates, analyze(jobs), args.top, load_study_library(root))
    print(f"Analyzed {len(jobs)} distinct rated jobs")
    print(f"Saved skill gap report: {path}")


if __name__ == "__main__":
    main()

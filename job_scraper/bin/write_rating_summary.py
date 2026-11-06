"""
Writes a rating summary to output/rating_summary.md after an
in-session sub-agent rating pass (see CLAUDE.md's "Rating Jobs Against a
Resume" section): a per-group score distribution table, a "Top Matches"
list (score 1-2 postings with zero missing hard requirements, one line
each pulling Company/Job Title from that posting's description file and
the sub-agent's one-sentence reason), and a "Why the Rest Score Low"
section listing the most frequently missing hard requirements among
score 4-5 postings. The latter two are derived purely from the ratings
data (score + missing + reason) and each posting's own description file
-- nothing person- or domain-specific is hardcoded, so the summary stays
accurate as keyword groups and candidates change over time.

Treats rating_summary.md as a single "current" file, the same way each
group's spreadsheet is current: if a previous one exists from a different
ISO week, it's archived into OLD/<old-date>/rating_summary.md first, mirroring
run_search.py's per-group archiving (same-week reruns overwrite in place).
Reuses run_search.py's .archive_state.json under a dedicated key so both
kinds of archiving share one tracked-state file.

Usage:
    python3 bin/write_rating_summary.py --ratings ratings.json

Where ratings.json is: {"<Group>": [{"file", "score", "reason", "missing"}, ...], ...}
"""

import argparse
import json
import os
import shutil
import sys
from collections import Counter
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_search import load_archive_state, save_archive_state

STATE_KEY = "__rating_summary__"


def build_table(group_ratings):
    rows = []
    for group, ratings in group_ratings.items():
        counts = Counter(r["score"] for r in ratings)
        rows.append((f"{group} ({len(ratings)})", [counts.get(s, 0) for s in range(1, 6)]))

    name_width = max([len("Group")] + [len(r[0]) for r in rows])
    col_width = 3

    def hline(left, mid, right):
        return left + mid.join([("─" * (name_width + 2))] + ["─" * (col_width + 2)] * 5) + right

    def row_line(name, cells):
        line = f"│ {name:<{name_width}} │"
        for c in cells:
            line += f" {str(c):^{col_width}} │"
        return line

    lines = [hline("┌", "┬", "┐"), row_line("Group", [1, 2, 3, 4, 5]), hline("├", "┼", "┤")]
    for i, (name, cells) in enumerate(rows):
        lines.append(row_line(name, cells))
        if i < len(rows) - 1:
            lines.append(hline("├", "┼", "┤"))
    lines.append(hline("└", "┴", "┘"))
    return "\n".join(lines)


def read_job_header(desc_path):
    """Pull Job Title / Company / URL off the top of a description file (see
    build_excel.py's file format). Missing/unreadable file -> ("", "", "")."""
    title = company = url = ""
    try:
        with open(desc_path) as f:
            for line in f:
                line = line.rstrip("\n")
                if line.startswith("Job Title:"):
                    title = line.split(":", 1)[1].strip()
                elif line.startswith("Company:"):
                    company = line.split(":", 1)[1].strip()
                elif line.startswith("URL:"):
                    url = line.split(":", 1)[1].strip()
                if title and company and url:
                    break
    except OSError:
        pass
    return title, company, url


def build_top_matches(group_ratings, output_dir):
    """Score 1-2 postings with zero missing hard requirements, across all
    groups, sorted best-first. Company/Job Title come from the posting's own
    description file, not the sanitized/truncated filename."""
    matches = []
    for group, ratings in group_ratings.items():
        desc_dir = os.path.join(output_dir, group.replace(" ", "_"))
        for r in ratings:
            if r["score"] <= 2 and not (r.get("missing") or "").strip():
                title, company, url = read_job_header(os.path.join(desc_dir, r["file"]))
                matches.append({
                    "group": group,
                    "score": r["score"],
                    "company": company or "?",
                    "title": title or r["file"],
                    "reason": r.get("reason", ""),
                    "url": url,
                })
    matches.sort(key=lambda m: (m["score"], m["group"], m["company"]))
    return matches


def format_top_matches(matches):
    lines = ["## Top Matches (score 1-2, zero missing hard requirements)", ""]
    if not matches:
        lines.append("None this run.")
        return lines
    for m in matches:
        lines.append(f"- **{m['company']} — {m['title']}** ({m['group']}, score {m['score']}) — {m['reason']}")
        if m["url"]:
            lines.append(f"  {m['url']}")
    return lines


def build_missing_requirement_counts(group_ratings, min_score=4):
    """Frequency of each missing hard requirement (comma-split) among
    postings scored at or above min_score, plus how many such postings
    there are in total."""
    counter = Counter()
    total = 0
    for ratings in group_ratings.values():
        for r in ratings:
            if r["score"] >= min_score:
                total += 1
                for req in (r.get("missing") or "").split(","):
                    req = req.strip()
                    if req:
                        counter[req] += 1
    return counter, total


def format_low_score_reasons(counter, total):
    lines = ["## Why the Rest Score Low", ""]
    if total == 0:
        lines.append("No score 4-5 postings this run.")
        return lines
    lines.append(f"{total} posting(s) scored 4-5. Most frequently missing hard requirements among them:")
    lines.append("")
    if not counter:
        lines.append("(no specific hard requirement recorded as missing — low scores came from domain/level misalignment instead)")
    else:
        for req, count in counter.most_common(10):
            lines.append(f"- {req} ({count})")
    return lines


def write_rating_summary(project_root, group_ratings):
    output_dir = os.path.join(project_root, "output")
    os.makedirs(output_dir, exist_ok=True)
    summary_path = os.path.join(output_dir, "rating_summary.md")

    if os.path.exists(summary_path):
        state = load_archive_state(output_dir)
        last = state.get(STATE_KEY)
        old_dt = datetime.strptime(last, "%y%m%d") if last else \
            datetime.fromtimestamp(os.path.getmtime(summary_path))
        now = datetime.now()
        if old_dt.isocalendar()[:2] != now.isocalendar()[:2]:
            archive_dir = os.path.join(output_dir, "OLD", old_dt.strftime("%y%m%d"))
            os.makedirs(archive_dir, exist_ok=True)
            dest = os.path.join(archive_dir, "rating_summary.md")
            shutil.move(summary_path, dest)
            print(f"Archived previous rating summary -> {dest}")

    table = build_table(group_ratings)
    total_jobs = sum(len(r) for r in group_ratings.values())
    top_matches = build_top_matches(group_ratings, output_dir)
    missing_counts, low_score_total = build_missing_requirement_counts(group_ratings)

    lines = [
        f"# Rating Summary - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"Total jobs rated: {total_jobs}",
        "",
        "```",
        table,
        "```",
        "",
    ]
    lines += format_top_matches(top_matches)
    lines.append("")
    lines += format_low_score_reasons(missing_counts, low_score_total)
    with open(summary_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    state = load_archive_state(output_dir)
    state[STATE_KEY] = datetime.now().strftime("%y%m%d")
    save_archive_state(output_dir, state)

    print(f"Saved rating summary: {summary_path}")


def main():
    parser = argparse.ArgumentParser(description="Write a rating summary table from a ratings JSON file.")
    parser.add_argument("--ratings", required=True, help="Path to JSON file: {group: [{file, score, reason, missing}, ...]}")
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(args.ratings) as f:
        group_ratings = json.load(f)

    write_rating_summary(project_root, group_ratings)


if __name__ == "__main__":
    main()

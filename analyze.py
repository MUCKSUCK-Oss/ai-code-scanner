#!/usr/bin/env python3
"""Compare AI-code scores across cohorts -- the actual result of the study.

    python3 analyze.py all-results.jsonl

Prints a markdown table, so it renders directly in a GitHub Actions summary.
The control cohort predates LLMs, so whatever fraction of it lands above the
AI threshold is the study's false-positive rate; the top/new gap only means
something if that number is small.
"""

import collections
import json
import statistics
import sys

AI_THRESHOLD = 50


def load(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("repo_score") is not None:
                rows.append(row)
    return rows


def describe(rows):
    scores = sorted(r["repo_score"] for r in rows)
    flagged = sum(1 for s in scores if s > AI_THRESHOLD)
    return {
        "n": len(scores),
        "mean": statistics.mean(scores),
        "median": statistics.median(scores),
        "p90": scores[int(len(scores) * 0.9)] if scores else 0,
        "flagged_pct": 100.0 * flagged / len(scores),
    }


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: analyze.py results.jsonl")
    rows = load(sys.argv[1])
    if not rows:
        sys.exit("no scored repos found")

    by_cohort = collections.defaultdict(list)
    for row in rows:
        by_cohort[row.get("cohort", "unknown")].append(row)

    print("## Cohort comparison\n")
    print("Repos scored: **%d**. Flagged means repo-level score above %d.\n" % (len(rows), AI_THRESHOLD))
    print("| Cohort | n | Mean | Median | P90 | % flagged |")
    print("|---|---|---|---|---|---|")
    for name in sorted(by_cohort):
        s = describe(by_cohort[name])
        print("| `%s` | %d | %.1f | %.1f | %.1f | %.1f%% |" % (
            name, s["n"], s["mean"], s["median"], s["p90"], s["flagged_pct"]))

    control = by_cohort.get("control_prellm")
    if control:
        fp = describe(control)["flagged_pct"]
        print("\n**False-positive rate: %.1f%%** " % fp, end="")
        print("(pre-LLM repos flagged as AI -- these are definitionally human-written).")

    top, new = by_cohort.get("top"), by_cohort.get("new")
    if top and new:
        gap = describe(new)["mean"] - describe(top)["mean"]
        print("\n**Top vs new gap: %+.1f points** in mean score." % gap)
        print("\n> Positive means AI-flagged code concentrates in new/unfiltered repos,")
        print("> which is the study's hypothesis. Judge it against the false-positive")
        print("> rate above, not against zero.")

    print("\n## Language breakdown\n")
    print("| Cohort | Language | n | Mean |")
    print("|---|---|---|---|")
    for name in sorted(by_cohort):
        by_lang = collections.defaultdict(list)
        for row in by_cohort[name]:
            by_lang[row.get("language") or "unknown"].append(row)
        for lang in sorted(by_lang, key=lambda k: -len(by_lang[k]))[:5]:
            group = by_lang[lang]
            print("| `%s` | %s | %d | %.1f |" % (
                name, lang, len(group), statistics.mean(r["repo_score"] for r in group)))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Step 8: measure code quality, so the AI score can be checked against it.

Runs three static analysers over a sample of a repository's Python files:

  pylint  correctness and style problems
  bandit  security weaknesses
  radon   cyclomatic complexity

Counts are normalised per 1000 lines, because a large repository would
otherwise look worse than a small one purely for being large.

Only a sample of files is analysed. Pylint on a large repository can take
many minutes, and at a few hundred repositories that exceeds any practical CI
budget. Twenty files is enough to estimate a repository-level rate, and turns
an hours-long job into a minutes-long one.

    python3 quality_audit.py /path/to/repo
    python3 quality_audit.py https://github.com/owner/repo

Needs: pip install pylint bandit radon
"""

import argparse
import json
import os
import random
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import repo_ai_detector as detector

MAX_FILES = 20
TOOL_TIMEOUT = 180

# Rates per 1000 lines are unstable when the denominator is tiny. One warning in
# a 14-line file reads as 71 per KLOC, which swamps any real signal and, because
# small repositories cluster in one cohort, can manufacture a correlation out of
# nothing. Repositories below this are measured but marked unusable.
MIN_LOC = 300

# The analysers here are Python-only. Extending to JavaScript would mean
# ESLint, which needs a Node toolchain and per-project config, so this arm of
# the study is restricted to Python and the paper should say so.
TARGET_EXT = ".py"


def sample_files(repo_path, limit=MAX_FILES):
    files = [f for f in detector.collect_files(repo_path) if f.endswith(TARGET_EXT)]
    random.shuffle(files)
    picked = files[:limit]
    loc = 0
    for path in picked:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                loc += sum(1 for line in f if line.strip())
        except OSError:
            continue
    return picked, loc


def run_json(cmd, timeout=TOOL_TIMEOUT):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (subprocess.SubprocessError, OSError):
        return None
    out = proc.stdout.strip()
    if not out:
        return None
    try:
        return json.loads(out)
    except ValueError:
        return None


def run_pylint(files):
    # Pylint exits non-zero whenever it finds anything, which is the normal
    # case, so the exit code is ignored and only the JSON is read.
    data = run_json([sys.executable, "-m", "pylint", "--output-format=json",
                     "--disable=import-error,no-name-in-module", "--persistent=n"] + files)
    if data is None:
        return None
    counts = {"error": 0, "warning": 0, "convention": 0, "refactor": 0}
    for item in data:
        kind = item.get("type", "")
        if kind in counts:
            counts[kind] += 1
    return counts


def run_bandit(files):
    data = run_json([sys.executable, "-m", "bandit", "-f", "json", "-q"] + files)
    if data is None:
        return None
    sev = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for item in data.get("results", []):
        level = item.get("issue_severity", "").upper()
        if level in sev:
            sev[level] += 1
    return sev


def run_radon(files):
    data = run_json([sys.executable, "-m", "radon", "cc", "-j"] + files)
    if data is None:
        return None
    scores = []
    for blocks in data.values():
        if isinstance(blocks, list):
            scores.extend(b.get("complexity", 0) for b in blocks if isinstance(b, dict))
    if not scores:
        return None
    return {"mean_complexity": round(sum(scores) / len(scores), 2),
            "max_complexity": max(scores),
            "blocks": len(scores)}


def audit(repo_path):
    files, loc = sample_files(repo_path)
    if not files or loc == 0:
        return {"analysed_files": 0, "loc": 0, "usable": False}

    pylint = run_pylint(files) or {}
    bandit = run_bandit(files) or {}
    radon = run_radon(files) or {}
    per_kloc = lambda n: round(1000.0 * n / loc, 2)

    errors = pylint.get("error", 0)
    warnings = pylint.get("warning", 0)
    security = bandit.get("HIGH", 0) + bandit.get("MEDIUM", 0)

    return {
        "analysed_files": len(files),
        "loc": loc,
        "usable": loc >= MIN_LOC,
        "below_min_loc": loc < MIN_LOC,
        "pylint": pylint,
        "bandit": bandit,
        "radon": radon,
        "errors_per_kloc": per_kloc(errors),
        "warnings_per_kloc": per_kloc(warnings),
        "security_per_kloc": per_kloc(security),
        "mean_complexity": radon.get("mean_complexity"),
        # A single figure so quality can be plotted against the AI score.
        # Errors are weighted above warnings, and security above both, because
        # they differ in consequence rather than in kind.
        "defect_density": round(per_kloc(errors) * 2 + per_kloc(warnings)
                                + per_kloc(security) * 3, 2),
    }


def main():
    ap = argparse.ArgumentParser(description="Static-analysis quality audit of one repository.")
    ap.add_argument("target", help="local path or GitHub URL")
    args = ap.parse_args()

    path, temp = detector.resolve_target(args.target)
    try:
        print(json.dumps(audit(path), indent=2))
    finally:
        if temp:
            import shutil
            shutil.rmtree(path, ignore_errors=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Phase 1: build the repo sample the classifier will run against.

Emits a JSON list of repos tagged by cohort, which repo_ai_detector.py then
scores. Cohorts are the whole point of the study: we compare AI-code density in
well-vetted popular repos against new unfiltered ones, with a pre-LLM cohort as
a human-written control.

    python3 github_sampler.py --per-cohort 1000 -o sample.json

Needs a token: GITHUB_TOKEN env var, or a logged-in `gh` CLI.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

API = "https://api.github.com"

# Search caps out at 1000 results per query no matter how many match, so every
# cohort gets sliced into date windows narrow enough to fit under that.
RESULT_CAP = 1000
PER_PAGE = 100

COHORTS = {
    # Well-maintained, heavily reviewed. If AI is a productivity multiplier,
    # this is where it should look harmless.
    "top": {
        "query": "stars:>=1000 pushed:>=2024-01-01",
        "window": (date(2008, 1, 1), date.today()),
    },
    # New and unvetted, created after ChatGPT's release. The "code slop"
    # hypothesis predicts the AI signal concentrates here.
    "new": {
        "query": "stars:<10 size:>100",
        "window": (date(2023, 1, 1), date.today()),
    },
    # Written before LLMs existed, so anything flagged here is by definition a
    # false positive. This is what makes the other two numbers trustworthy.
    "control_prellm": {
        "query": "stars:>=100",
        "window": (date(2012, 1, 1), date(2020, 12, 31)),
    },
}

LANGS = ["python", "javascript", "typescript", "java", "go"]


def get_token():
    for var in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(var):
            return os.environ[var]
    try:
        out = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        sys.exit("No token found. Set GITHUB_TOKEN, or run: gh auth login")


def api_get(path, token, params=None):
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "User-Agent": "ai-code-scanner-sampler",
    })
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                reset = e.headers.get("x-ratelimit-reset")
                wait = max(5, int(reset) - int(time.time())) if reset else 60
                wait = min(wait, 300)
                print("    rate limited, waiting %ds" % wait, file=sys.stderr)
                time.sleep(wait)
                continue
            if e.code >= 500:
                time.sleep(5 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("giving up on " + path)


def count_matches(query, token):
    data = api_get("/search/repositories", token, {"q": query, "per_page": 1})
    time.sleep(2)
    return data.get("total_count", 0)


def harvest(query, token, seen, out, cohort, limit):
    """Page through one query. Assumes it's already under RESULT_CAP."""
    for page in range(1, RESULT_CAP // PER_PAGE + 1):
        if len(out) >= limit:
            return
        data = api_get("/search/repositories", token,
                       {"q": query, "per_page": PER_PAGE, "page": page, "sort": "updated"})
        items = data.get("items", [])
        for repo in items:
            if repo["full_name"] in seen or repo.get("fork") or repo.get("archived"):
                continue
            seen.add(repo["full_name"])
            out.append({
                "full_name": repo["full_name"],
                "clone_url": repo["clone_url"],
                "cohort": cohort,
                "stars": repo["stargazers_count"],
                "language": repo.get("language"),
                "created_at": repo["created_at"][:10],
                "pushed_at": repo["pushed_at"][:10],
                "size_kb": repo.get("size", 0),
                "forks": repo.get("forks_count", 0),
                "open_issues": repo.get("open_issues_count", 0),
            })
            if len(out) >= limit:
                return
        if len(items) < PER_PAGE:
            return
        time.sleep(2)


def year_windows(start, end):
    """One window per calendar year across the cohort's range."""
    windows = []
    for year in range(start.year, end.year + 1):
        lo = max(start, date(year, 1, 1))
        hi = min(end, date(year, 12, 31))
        if lo <= hi:
            windows.append((lo, hi))
    return windows


def sample_cohort(name, spec, token, limit):
    """Draw an even quota from every (language, year) cell.

    Filling greedily from the first slice instead produces a sample that is
    entirely one language and one era, which would confound the whole cohort
    comparison -- older repos are both more popular and definitionally more
    human-written, so an age-skewed 'top' cohort would score low for reasons
    that have nothing to do with vetting quality.
    """
    out, seen = [], set()
    windows = year_windows(*spec["window"])
    # Year-major ordering, so a run that stops early still covers every
    # language rather than exhausting the first one alphabetically.
    cells = [(lang, lo, hi) for lo, hi in windows for lang in LANGS]
    if not cells:
        return out
    quota = max(1, limit // len(cells))

    # Two passes: take the fair share from every cell first, then top up from
    # whichever cells still have results, so a thin year can't starve the total.
    for extra in (0, 1):
        for lang, lo, hi in cells:
            if len(out) >= limit:
                return out[:limit]
            query = "%s language:%s created:%s..%s" % (spec["query"], lang, lo, hi)
            target = len(out) + (quota if not extra else limit)
            before = len(out)
            harvest(query, token, seen, out, name, min(target, limit))
            if not extra and len(out) > before:
                print("    %s %s: +%d" % (lang, lo.year, len(out) - before), file=sys.stderr)
    return out[:limit]


def main():
    ap = argparse.ArgumentParser(description="Sample GitHub repos into study cohorts.")
    ap.add_argument("-o", "--out", default="sample.json")
    ap.add_argument("--per-cohort", type=int, default=1000)
    ap.add_argument("--cohorts", default=",".join(COHORTS), help="comma separated")
    ap.add_argument("--shard", type=int, help="emit only shard N (for parallel CI jobs)")
    ap.add_argument("--shards", type=int, default=1)
    args = ap.parse_args()

    token = get_token()
    everything = []
    for name in args.cohorts.split(","):
        name = name.strip()
        if name not in COHORTS:
            sys.exit("unknown cohort: %s (have: %s)" % (name, ", ".join(COHORTS)))
        print("sampling cohort: %s" % name, file=sys.stderr)
        everything.extend(sample_cohort(name, COHORTS[name], token, args.per_cohort))

    if args.shard is not None:
        everything = [r for i, r in enumerate(everything) if i % args.shards == args.shard]

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(everything, f, indent=2)

    by_cohort = {}
    for repo in everything:
        by_cohort[repo["cohort"]] = by_cohort.get(repo["cohort"], 0) + 1
    print("\nwrote %d repos to %s" % (len(everything), args.out), file=sys.stderr)
    for cohort, count in sorted(by_cohort.items()):
        print("  %-16s %d" % (cohort, count), file=sys.stderr)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Step 11: did the repository turn out to be worth anything?

Earlier versions scored "slop" from engineering practice -- tests, CI, a
licence. Measured against real repositories, 81% of that score turned out to be
professional-practice signals, which mature projects have and weekend projects
do not. It was measuring how professionally a project is run, not whether the
project is worth having, and since maturity is also what makes a repository
popular, the resulting cohort gap was close to circular.

This measures adoption instead: whether anyone actually took the software up.
A person who cannot write code, builds something with AI, and finds users, has
made something valuable -- however it was built and whatever its CI looks like.

Adoption is scaled by age. A three-month-old project with 40 stars is doing
better than a ten-year-old with 100, and comparing the two raw would only
measure which is older.

    python3 value_audit.py owner/repo
"""

import argparse
import json
import math
import os
import subprocess
import sys
from datetime import datetime, timezone

API = "https://api.github.com"

# Star counts follow a power law: a handful of repositories have tens of
# thousands and most have nearly none. Correlating raw counts would let three
# famous projects decide the result, so rates are compared on a log scale.
LOG_ADOPTION = True

AGE_BANDS = [
    ("0-6 months", 0, 6),
    ("6-12 months", 6, 12),
    ("1-2 years", 12, 24),
    ("2-5 years", 24, 60),
    ("5+ years", 60, 10 ** 6),
]

ABANDONED_AFTER_DAYS = 180


def parse_ts(value):
    """Always returns a timezone-aware datetime.

    The API sends full timestamps but the sampler stores dates truncated to
    'YYYY-MM-DD', which parses to a naive datetime and cannot be subtracted from
    an aware one. Both shapes have to come out of here comparable.
    """
    if not value:
        return None
    parsed = None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(value[:10], "%Y-%m-%d")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def metrics(repo, now=None):
    """Adoption figures for one repository record from the GitHub API."""
    now = now or datetime.now(timezone.utc)
    created = parse_ts(repo.get("created_at"))
    pushed = parse_ts(repo.get("pushed_at"))
    if not created:
        return {"usable": False}

    age_months = max((now - created).days / 30.44, 0.5)
    stars = repo.get("stars", repo.get("stargazers_count", 0)) or 0
    forks = repo.get("forks", repo.get("forks_count", 0)) or 0

    lived_months = max((pushed - created).days / 30.44, 0.0) if pushed else 0.0
    idle_days = (now - pushed).days if pushed else None

    star_rate = stars / age_months
    fork_rate = forks / age_months

    return {
        "usable": True,
        "age_months": round(age_months, 1),
        "stars": stars,
        "forks": forks,
        "stars_per_month": round(star_rate, 3),
        "forks_per_month": round(fork_rate, 3),
        "adoption": round(math.log1p(star_rate + 2 * fork_rate), 3) if LOG_ADOPTION
                    else round(star_rate + 2 * fork_rate, 3),
        # How much of its life the project was actually being worked on. A repo
        # pushed once on the day it was created scores 0.
        "maintained_fraction": round(lived_months / age_months, 3),
        "idle_days": idle_days,
        "abandoned": bool(idle_days is not None and idle_days > ABANDONED_AFTER_DAYS),
        "age_band": next(name for name, lo, hi in AGE_BANDS if lo <= age_months < hi),
    }


def token():
    for var in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(var):
            return os.environ[var]
    try:
        out = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def fetch(full_name, tok):
    import urllib.error
    import urllib.request
    req = urllib.request.Request(
        "%s/repos/%s" % (API, full_name),
        headers={"Accept": "application/vnd.github+json",
                 "User-Agent": "value-audit",
                 **({"Authorization": "Bearer " + tok} if tok else {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return None
    return {
        "full_name": data["full_name"],
        "stars": data.get("stargazers_count", 0),
        "forks": data.get("forks_count", 0),
        "open_issues": data.get("open_issues_count", 0),
        "created_at": data.get("created_at"),
        "pushed_at": data.get("pushed_at"),
    }


def main():
    ap = argparse.ArgumentParser(description="Measure whether a repo found users.")
    ap.add_argument("repo", help="owner/name")
    args = ap.parse_args()
    data = fetch(args.repo, token())
    if not data:
        sys.exit("could not read " + args.repo)
    result = metrics(data)
    result.update({"full_name": data["full_name"]})
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

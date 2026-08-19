#!/usr/bin/env python3
"""Measure what content-based detection catches when the metadata is gone.

Every large study of AI code in the wild finds that code the same way: it looks
for commits that announced themselves, via bot logins, AI author emails, or
Co-authored-by trailers. Strip that one line and the code becomes invisible to
those methods. This script asks how much of it a content-based detector can
still recover.

Method:

  Known-AI    commits carrying an AI co-author trailer, restricted to files the
              commit ADDED, so the whole file is AI-authored rather than a human
              file with an AI patch applied.
  Known-human files from repositories whose last push predates 2021, so nothing
              in them can have been LLM-written.

Both sets are scored by the same detector, which never sees any metadata. The
rate at which it flags the known-AI set is recall; the rate on the known-human
set is the false-positive rate. The gap between them is what the metadata
approach silently misses.

    python3 provenance_experiment.py --limit 150 -o provenance.json
"""

import argparse
import json
import os
import random
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import repo_ai_detector as detector

API = "https://api.github.com"

# Commit search is throttled far more aggressively than the documented 30/min,
# so we stay well under it rather than fighting secondary limits.
SEARCH_DELAY = 6.0
API_DELAY = 1.5

AI_TRAILERS = [
    "Co-authored-by: Claude",
    "Co-authored-by: Copilot",
    "Co-authored-by: Cursor",
    "Co-authored-by: Devin",
]

FLAG_THRESHOLD = 50


def get_token():
    for var in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(var):
            return os.environ[var]
    import subprocess
    try:
        r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True)
        return r.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        sys.exit("No token. Set GITHUB_TOKEN or run: gh auth login")


def api_get(path, token, params=None, accept="application/vnd.github+json"):
    url = path if path.startswith("http") else API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + token,
        "Accept": accept,
        "User-Agent": "ai-provenance-experiment",
    })
    delay = 20.0
    for _ in range(6):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                retry = e.headers.get("retry-after")
                wait = float(retry) if retry else delay
                print("    throttled, waiting %.0fs" % wait, file=sys.stderr)
                time.sleep(min(wait, 120))
                delay = min(delay * 2, 120)
                continue
            if e.code == 422:
                return None
            if e.code >= 500:
                time.sleep(10)
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            time.sleep(10)
    return None


def fetch_raw(url):
    """raw.githubusercontent does not consume API quota."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ai-provenance-experiment"})
        with urllib.request.urlopen(req, timeout=45) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception:
        return None


def score_text(text, ext):
    """Run the detector over in-memory content by staging it as a real file."""
    fd, tmp = tempfile.mkstemp(suffix=ext)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        return detector.analyze_file(tmp)
    finally:
        os.unlink(tmp)


def collect_ai_files(token, limit):
    """Files added by commits that declare an AI co-author."""
    found, seen_repos = [], {}
    for trailer in AI_TRAILERS:
        if len(found) >= limit:
            break
        for page in range(1, 6):
            if len(found) >= limit:
                break
            print("  searching: %s (page %d)" % (trailer, page), file=sys.stderr)
            res = api_get("/search/commits", token,
                          {"q": '"%s"' % trailer, "per_page": 30, "page": page})
            time.sleep(SEARCH_DELAY)
            if not res or not res.get("items"):
                break
            for item in res["items"]:
                if len(found) >= limit:
                    break
                repo = item["repository"]["full_name"]
                # Cap per repo so one busy project cannot dominate the sample.
                if seen_repos.get(repo, 0) >= 3:
                    continue
                detail = api_get("/repos/%s/commits/%s" % (repo, item["sha"]), token)
                time.sleep(API_DELAY)
                if not detail:
                    continue
                for f in detail.get("files", []):
                    if len(found) >= limit:
                        break
                    if f.get("status") != "added":
                        continue
                    ext = os.path.splitext(f["filename"])[1].lower()
                    if ext not in detector.LANGUAGES:
                        continue
                    text = fetch_raw(f.get("raw_url", ""))
                    if not text or len(text) > detector.MAX_FILE_BYTES:
                        continue
                    result = score_text(text, ext)
                    if not result:
                        continue
                    seen_repos[repo] = seen_repos.get(repo, 0) + 1
                    found.append({
                        "source": "ai_declared",
                        "repo": repo,
                        "file": f["filename"],
                        "trailer": trailer,
                        "score": result["score"],
                        "indicators": result["indicators"],
                    })
                    print("    [%d/%d] %-52s %3d" % (
                        len(found), limit, f["filename"][:52], result["score"]), file=sys.stderr)
    return found


def collect_human_files(token, limit):
    """Files from repos untouched since before LLMs existed."""
    found = []
    res = api_get("/search/repositories", token, {
        "q": "pushed:<2021-01-01 created:<2019-01-01 stars:>=50",
        "per_page": 40, "sort": "stars",
    })
    time.sleep(SEARCH_DELAY)
    if not res:
        return found
    repos = res.get("items", [])
    random.shuffle(repos)
    for repo in repos:
        if len(found) >= limit:
            break
        tree = api_get("/repos/%s/git/trees/%s" % (repo["full_name"], repo["default_branch"]),
                       token, {"recursive": "1"})
        time.sleep(API_DELAY)
        if not tree:
            continue
        blobs = [n for n in tree.get("tree", [])
                 if n["type"] == "blob"
                 and os.path.splitext(n["path"])[1].lower() in detector.LANGUAGES]
        random.shuffle(blobs)
        for node in blobs[:3]:
            if len(found) >= limit:
                break
            raw = "https://raw.githubusercontent.com/%s/%s/%s" % (
                repo["full_name"], repo["default_branch"], node["path"])
            text = fetch_raw(raw)
            if not text or len(text) > detector.MAX_FILE_BYTES:
                continue
            ext = os.path.splitext(node["path"])[1].lower()
            result = score_text(text, ext)
            if not result:
                continue
            found.append({
                "source": "human_prellm",
                "repo": repo["full_name"],
                "file": node["path"],
                "score": result["score"],
                "indicators": result["indicators"],
            })
            print("    [%d/%d] %-52s %3d" % (
                len(found), limit, node["path"][:52], result["score"]), file=sys.stderr)
    return found


def report(ai_files, human_files):
    def rate(rows):
        if not rows:
            return 0.0, 0.0
        flagged = sum(1 for r in rows if r["score"] > FLAG_THRESHOLD)
        mean = sum(r["score"] for r in rows) / len(rows)
        return 100.0 * flagged / len(rows), mean

    recall, ai_mean = rate(ai_files)
    fpr, human_mean = rate(human_files)

    print("\n" + "=" * 68)
    print(" CONTENT DETECTION vs METADATA-DECLARED GROUND TRUTH")
    print("=" * 68)
    print("Flag threshold: score > %d\n" % FLAG_THRESHOLD)
    print("  %-34s n=%-5d mean=%5.1f  flagged=%5.1f%%" % (
        "AI (declared in metadata)", len(ai_files), ai_mean, recall))
    print("  %-34s n=%-5d mean=%5.1f  flagged=%5.1f%%" % (
        "Human (repos dormant pre-2021)", len(human_files), human_mean, fpr))

    print("\n  Recall on known-AI code : %.1f%%" % recall)
    print("  False-positive rate     : %.1f%%" % fpr)

    curve = roc(ai_files, human_files)
    print("\n  Threshold sweep (the fixed cutoff of %d is only one row):\n" % FLAG_THRESHOLD)
    print("    cutoff   recall    FPR   Youden J")
    for point in curve:
        mark = "  <-- best" if point["best"] else ""
        print("    %5d   %5.1f%%  %5.1f%%   %+.3f%s" % (
            point["cutoff"], point["recall"], point["fpr"], point["youden"], mark))

    auc = area_under_curve(curve)
    print("\n  AUC: %.3f  (0.5 = coin flip, 1.0 = perfect)" % auc)
    best = next((p for p in curve if p["best"]), None)
    if best:
        print("  Best operating point: cutoff %d -> %.1f%% recall at %.1f%% FPR"
              % (best["cutoff"], best["recall"], best["fpr"]))
    return {"recall_at_fixed": recall, "fpr_at_fixed": fpr,
            "ai_mean": ai_mean, "human_mean": human_mean,
            "n_ai": len(ai_files), "n_human": len(human_files),
            "auc": auc, "roc": curve}


def roc(ai_files, human_files):
    """Recall and false-positive rate at every candidate cutoff.

    A single hard-coded threshold hides whether a detector has any signal at
    all. Calibrating on raw model output overstates the cutoff badly, because
    AI code that survives review looks far less like raw generation.
    """
    cutoffs = [0, 5, 10, 15, 20, 25, 30, 40, 50, 60, 75]
    ai_scores = [r["score"] for r in ai_files]
    human_scores = [r["score"] for r in human_files]
    out = []
    for cutoff in cutoffs:
        rec = 100.0 * sum(1 for s in ai_scores if s > cutoff) / len(ai_scores) if ai_scores else 0.0
        fp = 100.0 * sum(1 for s in human_scores if s > cutoff) / len(human_scores) if human_scores else 0.0
        out.append({"cutoff": cutoff, "recall": rec, "fpr": fp,
                    "youden": (rec - fp) / 100.0, "best": False})
    peak = max(out, key=lambda p: p["youden"])
    peak["best"] = True
    return out


def area_under_curve(curve):
    pts = sorted(((p["fpr"] / 100.0, p["recall"] / 100.0) for p in curve))
    pts = [(0.0, 0.0)] + pts + [(1.0, 1.0)]
    total = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        total += (x2 - x1) * (y1 + y2) / 2.0
    return total


def main():
    ap = argparse.ArgumentParser(description="Measure detection recall on metadata-labeled AI code.")
    ap.add_argument("--limit", type=int, default=100, help="files per class")
    ap.add_argument("-o", "--out", default="provenance.json")
    args = ap.parse_args()

    token = get_token()
    print("collecting AI-declared files...", file=sys.stderr)
    ai_files = collect_ai_files(token, args.limit)
    print("\ncollecting pre-LLM human files...", file=sys.stderr)
    human_files = collect_human_files(token, args.limit)

    summary = report(ai_files, human_files)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "ai_files": ai_files, "human_files": human_files},
                  f, indent=2)
    print("\nwrote %s" % args.out)


if __name__ == "__main__":
    main()

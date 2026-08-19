#!/usr/bin/env python3
"""Detect AI code two ways at once, and measure where they disagree.

Neither method sees the whole picture on its own:

  Metadata  reads git history for AI markers (Co-authored-by trailers, bot
            authors, agent emails). Reliable when present, but blind to code a
            person pasted in from a chat window, which carries no marker at all.
  Content   reads the code itself. Blind to AI output that was reviewed and
            cleaned up, but it is the only thing that can catch pasted code.

They fail in opposite directions, so running both gives a Venn diagram: caught
by metadata only, content only, both, or neither. That overlap is the number
this project is actually after.

    python3 dual_detect.py https://github.com/owner/repo
    python3 dual_detect.py --batch sample.json -o dual.json
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import repo_ai_detector as detector

# Markers the major agents leave in git history. Drawn from the same signals
# published studies rely on, so our metadata arm matches theirs.
METADATA_PATTERNS = {
    "claude": r"co-authored-by:\s*claude|noreply@anthropic\.com|generated with \[?claude code",
    "copilot": r"co-authored-by:\s*copilot|copilot-swe-agent|copilot@github\.com",
    "cursor": r"co-authored-by:\s*cursor|cursor-agent",
    "devin": r"devin-ai-integration|co-authored-by:\s*devin",
    "gemini": r"co-authored-by:\s*gemini|gemini-code-assist",
    "codex": r"co-authored-by:\s*codex|chatgpt-codex",
}

# Repo-level content scores run lower than single-file scores, and real-world
# AI code scores lower still than raw model output. 40 sits above every
# pre-LLM control repo measured so far (max 23.1) with room to spare.
CONTENT_THRESHOLD = 40.0
CLONE_DEPTH = 250

# A single AI commit in 250 does not make a repository AI-built. Flagging on
# mere presence rewards size: busy projects with many contributors are more
# likely to catch one AI commit by chance, which inverts the cohort comparison
# entirely. Require AI to be a real share of recent history instead.
METADATA_MIN_SHARE = 0.10


def clone(url, depth=CLONE_DEPTH):
    tmp = tempfile.mkdtemp(prefix="dual_detect_")
    try:
        subprocess.run(["git", "clone", "--quiet", "--depth", str(depth), url, tmp],
                       check=True, capture_output=True, text=True, timeout=300)
        return tmp
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        shutil.rmtree(tmp, ignore_errors=True)
        return None


SEP = "===COMMIT==="
FILES_MARK = "===FILES==="


def metadata_signal(repo_path):
    """Scan git history for agent fingerprints, and check what they changed.

    An AI marker on a commit says a tool was involved somewhere; it does not
    say the commit wrote any code. Commits that only touch a README, a lockfile
    or CI config would otherwise count the same as one that adds 400 lines of
    Python, so we separate the two.
    """
    empty = {"ai_commits": 0, "total_commits": 0, "ai_share": 0.0, "tools": [],
             "flagged": False, "any_ai_commit": False,
             "ai_code_commits": 0, "ai_code_share": 0.0, "ai_lines_changed": 0,
             "docs_only_ai_commits": 0}
    try:
        log = subprocess.run(
            ["git", "-C", repo_path, "log", "-n", str(CLONE_DEPTH), "--numstat",
             "--format=%s%%n%%an%%n%%ae%%n%%B%%n%s" % (SEP, FILES_MARK)],
            capture_output=True, text=True, timeout=180,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return empty

    tools = set()
    total = ai_commits = ai_code_commits = docs_only = ai_lines = 0
    for chunk in log.split(SEP):
        if not chunk.strip():
            continue
        total += 1
        header, _, filepart = chunk.partition(FILES_MARK)
        hit = [n for n, pat in METADATA_PATTERNS.items() if re.search(pat, header.lower())]
        if not hit:
            continue
        ai_commits += 1
        tools.update(hit)

        touched_code, lines = False, 0
        for row in filepart.strip().splitlines():
            cols = row.split("\t")
            if len(cols) != 3:
                continue
            added, deleted, name = cols
            if os.path.splitext(name)[1].lower() not in detector.LANGUAGES:
                continue
            touched_code = True
            for value in (added, deleted):
                if value.isdigit():
                    lines += int(value)
        if touched_code:
            ai_code_commits += 1
            ai_lines += lines
        else:
            docs_only += 1

    share = ai_commits / total if total else 0.0
    code_share = ai_code_commits / total if total else 0.0
    return {
        "ai_commits": ai_commits,
        "total_commits": total,
        "ai_share": round(share, 4),
        "tools": sorted(tools),
        # Flag on commits that actually wrote code, not merely mentioned a tool.
        "flagged": code_share >= METADATA_MIN_SHARE,
        # Kept separately because it is what prior work reports, and the gap
        # between these measures is itself a result worth showing.
        "any_ai_commit": ai_commits > 0,
        "ai_code_commits": ai_code_commits,
        "ai_code_share": round(code_share, 4),
        "ai_lines_changed": ai_lines,
        "docs_only_ai_commits": docs_only,
    }


def content_signal(repo_path):
    """LOC-weighted score from the heuristic detector."""
    scored = []
    for path in detector.collect_files(repo_path):
        result = detector.analyze_file(path)
        if result:
            scored.append(result)
    if not scored:
        return {"score": None, "files": 0, "flagged": False}
    total_loc = sum(r["loc"] for r in scored) or 1
    score = sum(r["score"] * r["loc"] for r in scored) / total_loc
    return {
        "score": round(score, 1),
        "files": len(scored),
        "tier": detector.get_flag_tier(score),
        "flagged": score >= CONTENT_THRESHOLD,
    }


def ai_score(meta, content):
    """One 0-100 figure combining both arms.

    Strongest evidence leads, with a bonus when the two agree. Averaging would
    be wrong here: a repository written entirely by pasting from a chat has no
    git markers at all, so averaging halves a correct content signal against a
    zero that only means 'no tool announced itself'. Either arm firing is real
    evidence; both firing is stronger.
    """
    a = 100.0 * meta.get("ai_code_share", 0.0)
    b = content.get("score") or 0.0
    combined = max(a, b) + 0.25 * min(a, b)
    return round(min(combined, 100.0), 1)


def verdict(meta, content):
    if meta["flagged"] and content["flagged"]:
        return "both"
    if meta["flagged"]:
        return "metadata_only"
    if content["flagged"]:
        return "content_only"
    return "neither"


def examine(url, keep=None):
    path = keep or clone(url)
    if not path:
        return None
    try:
        meta = metadata_signal(path)
        content = content_signal(path)
        return {
            "repo": url,
            "metadata": meta,
            "content": content,
            "ai_score": ai_score(meta, content),
            "verdict": verdict(meta, content),
        }
    finally:
        if not keep:
            shutil.rmtree(path, ignore_errors=True)


def summarise(rows):
    counts = {"both": 0, "metadata_only": 0, "content_only": 0, "neither": 0}
    for row in rows:
        counts[row["verdict"]] += 1
    total = len(rows) or 1

    print("\n" + "=" * 62)
    print(" TWO DETECTION METHODS, SAME REPOSITORIES")
    print("=" * 62)
    print("Repos examined: %d\n" % len(rows))
    labels = {
        "both": "Both methods agree (AI)",
        "metadata_only": "Metadata only (content missed it)",
        "content_only": "Content only (unlabelled AI)",
        "neither": "Neither flagged",
    }
    for key in ("both", "metadata_only", "content_only", "neither"):
        print("  %-36s %4d  %5.1f%%" % (labels[key], counts[key], 100.0 * counts[key] / total))

    meta_total = counts["both"] + counts["metadata_only"]
    content_total = counts["both"] + counts["content_only"]
    either = meta_total + counts["content_only"]
    print("\n  Metadata alone would find : %d" % meta_total)
    print("  Content alone would find  : %d" % content_total)
    print("  Both combined find        : %d" % either)
    if meta_total:
        extra = 100.0 * counts["content_only"] / meta_total
        print("\n  Content detection adds %.0f%% more repos than metadata alone." % extra)
        print("  Those are repos where AI code carries no git marker -- the")
        print("  population every metadata-based study silently excludes.")
    return counts


def main():
    ap = argparse.ArgumentParser(description="Run metadata and content AI detection together.")
    ap.add_argument("target", nargs="?", help="a repo URL or local path")
    ap.add_argument("--batch", help="sample.json from github_sampler.py")
    ap.add_argument("-o", "--out", help="write results as JSON")
    ap.add_argument("--limit", type=int, help="cap repos processed from --batch")
    ap.add_argument("--shard", type=int, default=0, help="which slice to run (for parallel CI jobs)")
    ap.add_argument("--shards", type=int, default=1)
    args = ap.parse_args()

    if not args.target and not args.batch:
        ap.error("give a repo URL or --batch sample.json")

    rows = []
    if args.batch:
        with open(args.batch, encoding="utf-8") as f:
            repos = json.load(f)
        if args.limit:
            repos = repos[:args.limit]
        if args.shards > 1:
            repos = [r for i, r in enumerate(repos) if i % args.shards == args.shard]
        for n, repo in enumerate(repos, 1):
            result = examine(repo["clone_url"])
            if not result:
                print("[%d/%d] FAILED %s" % (n, len(repos), repo["full_name"]), file=sys.stderr)
                continue
            result["full_name"] = repo["full_name"]
            result["cohort"] = repo.get("cohort")
            result["stars"] = repo.get("stars")
            rows.append(result)
            print("[%d/%d] %-40s meta=%-3d content=%-5s -> %s" % (
                n, len(repos), repo["full_name"][:40],
                result["metadata"]["ai_commits"],
                result["content"]["score"], result["verdict"]), file=sys.stderr)
    else:
        local = args.target if os.path.isdir(args.target) else None
        result = examine(args.target, keep=local)
        if not result:
            sys.exit("could not read " + args.target)
        rows.append(result)
        print(json.dumps(result, indent=2))

    if len(rows) > 1:
        summarise(rows)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2)
        print("\nwrote %s" % args.out)


if __name__ == "__main__":
    main()

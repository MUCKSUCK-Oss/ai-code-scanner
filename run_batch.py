#!/usr/bin/env python3
"""Score every repo in a sample file, one at a time, and append results as we go.

Designed to run inside CI: each repo is cloned into a temp dir by
repo_ai_detector, scored, and deleted before the next one starts, so disk usage
stays flat no matter how many repos are in the sample.

    python3 run_batch.py sample.json -o results.jsonl --shard 0 --shards 20

Results are appended per repo, and anything already present is skipped, so a
killed job resumes where it stopped instead of starting over.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DETECTOR = os.path.join(HERE, "repo_ai_detector.py")


def already_done(path):
    done = set()
    if not os.path.exists(path):
        return done
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                done.add(json.loads(line)["full_name"])
            except (ValueError, KeyError):
                continue
    return done


def score_one(repo, timeout):
    """Run the detector against one repo, return its summary or None."""
    fd, tmp = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        proc = subprocess.run(
            [sys.executable, DETECTOR, repo["clone_url"], "--json", tmp, "--top", "5"],
            capture_output=True, text=True, timeout=timeout,
        )
        if proc.returncode != 0 or not os.path.getsize(tmp):
            return None
        with open(tmp, encoding="utf-8") as f:
            data = json.load(f)
        files = data.get("files", [])
        return {
            "full_name": repo["full_name"],
            "cohort": repo["cohort"],
            "stars": repo["stars"],
            "language": repo["language"],
            "created_at": repo["created_at"],
            "repo_score": data.get("repo_score"),
            "repo_tier": data.get("repo_tier"),
            "tier_distribution": data.get("tier_distribution"),
            "files_scanned": len(files),
            "top_files": [
                {"file": f["file"], "score": f["score"], "indicators": f["indicators"]}
                for f in files[:5]
            ],
        }
    except subprocess.TimeoutExpired:
        return None
    finally:
        os.path.exists(tmp) and os.unlink(tmp)


def main():
    ap = argparse.ArgumentParser(description="Score a sample of repos.")
    ap.add_argument("sample", help="JSON file from github_sampler.py")
    ap.add_argument("-o", "--out", default="results.jsonl")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--timeout", type=int, default=300, help="seconds per repo")
    args = ap.parse_args()

    with open(args.sample, encoding="utf-8") as f:
        repos = json.load(f)
    mine = [r for i, r in enumerate(repos) if i % args.shards == args.shard]

    done = already_done(args.out)
    if done:
        print("resuming, %d already scored" % len(done), file=sys.stderr)

    ok = failed = 0
    started = time.time()
    with open(args.out, "a", encoding="utf-8") as out:
        for n, repo in enumerate(mine, 1):
            if repo["full_name"] in done:
                continue
            result = score_one(repo, args.timeout)
            if result is None:
                failed += 1
                print("[%d/%d] FAILED %s" % (n, len(mine), repo["full_name"]), file=sys.stderr)
                continue
            out.write(json.dumps(result) + "\n")
            out.flush()
            ok += 1
            print("[%d/%d] %-45s %5.1f  %s" % (
                n, len(mine), repo["full_name"][:45],
                result["repo_score"], result["repo_tier"].split("-")[0].strip(),
            ), file=sys.stderr)

    mins = (time.time() - started) / 60
    print("\nscored %d, failed %d, %.1f min" % (ok, failed, mins), file=sys.stderr)


if __name__ == "__main__":
    main()

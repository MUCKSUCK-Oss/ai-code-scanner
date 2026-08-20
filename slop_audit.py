#!/usr/bin/env python3
"""Step 10: is this repository original work, or filler?

Defect density answers whether code is broken. It says nothing about whether
code is worth having. A generated project can pass every linter and still be
the four-thousandth copy of the same starter template, opened once and never
returned to. This module measures that instead, two ways:

  Template reuse   scaffold markers left by generators, and boilerplate the
                   author never edited. Answers "did they start from a template
                   and barely change it?"
  Hollowness       no tests, no CI, a stub README, almost no code. Answers
                   "is there a real project here, or only the shape of one?"

It also fingerprints files so duplicates can be found across a sample. Note
that on a randomly drawn sample, two repositories are very unlikely to share
files, so a near-zero duplicate count is the expected outcome and is reported
as a finding rather than treated as failure.

    python3 slop_audit.py /path/to/repo
"""

import argparse
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import repo_ai_detector as detector

# Phrases that survive only when nobody edited the generated README.
TEMPLATE_README = [
    r"getting started with create react app",
    r"bootstrapped with \[?`?create-next-app",
    r"react \+ typescript \+ vite",
    r"currently, two official plugins are available",
    r"this template provides a minimal setup to get",
    r"your app is ready to be deployed",
    r"you can learn more in the \[create react app documentation",
    r"npm run dev.*open \[http://localhost:3000",
    r"# project title\b",
    r"^\s*#+\s*(my|new|untitled)\s+(app|project)\s*$",
    r"a short description of the project",
    r"describe your project here",
    r"todo: add (a )?description",
]

# Files whose mere presence marks a generator.
TEMPLATE_FILES = [
    "cookiecutter.json", "vite.svg", "logo192.png", "logo512.png",
    "reportWebVitals.js", "setupTests.js", "next-env.d.ts",
]

# Placeholder names an author never replaced.
PLACEHOLDER_NAMES = [
    "my-app", "my-project", "vite-project", "untitled", "frontend", "test-app",
    "react-app", "nextjs-app", "new-project", "project-name", "your-project-name",
]

TEST_HINTS = ("test", "spec", "__tests__")
CI_DIRS = (".github/workflows", ".circleci", ".gitlab-ci.yml", "azure-pipelines.yml")

README_STUB_CHARS = 300
THIN_CODE_LOC = 200
HASH_FILES = 40


def read(path, limit=200000):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(limit)
    except OSError:
        return ""


def find_readme(repo_path):
    for name in os.listdir(repo_path):
        if name.lower().startswith("readme"):
            return os.path.join(repo_path, name)
    return None


def template_signals(repo_path, source_files):
    hits = []

    readme_path = find_readme(repo_path)
    readme = read(readme_path) if readme_path else ""
    for pattern in TEMPLATE_README:
        if re.search(pattern, readme, re.IGNORECASE | re.MULTILINE):
            hits.append("unedited generated README (%s)" % pattern[:34])
            break

    present = set()
    for path in source_files:
        present.add(os.path.basename(path))
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in detector.SKIP_DIRS]
        present.update(files)
    for marker in TEMPLATE_FILES:
        if marker in present:
            hits.append("generator artefact: %s" % marker)

    pkg = os.path.join(repo_path, "package.json")
    if os.path.exists(pkg):
        try:
            name = (json.loads(read(pkg)) or {}).get("name", "")
            if str(name).lower() in PLACEHOLDER_NAMES:
                hits.append("placeholder project name: %s" % name)
        except ValueError:
            pass

    return hits


def hollow_signals(repo_path, source_files, loc):
    hits = []
    rel = [os.path.relpath(p, repo_path).lower() for p in source_files]

    if not any(any(h in part for h in TEST_HINTS) for part in rel):
        hits.append("no tests")

    has_ci = any(os.path.exists(os.path.join(repo_path, c)) for c in CI_DIRS)
    if not has_ci:
        hits.append("no CI")

    readme_path = find_readme(repo_path)
    body = read(readme_path) if readme_path else ""
    if len(body.strip()) < README_STUB_CHARS:
        hits.append("README missing or a stub (%d chars)" % len(body.strip()))

    if loc < THIN_CODE_LOC:
        hits.append("almost no code (%d lines)" % loc)

    if not os.path.exists(os.path.join(repo_path, "LICENSE")) and \
       not os.path.exists(os.path.join(repo_path, "LICENSE.md")):
        hits.append("no licence")

    return hits


def file_hashes(source_files, repo_path, limit=HASH_FILES):
    """Content hashes with comments and whitespace removed.

    Normalising first means a copied file still matches after reformatting or
    after its comments were stripped, which is exactly what a repository does
    when it adapts a template.
    """
    out = {}
    for path in sorted(source_files)[:limit]:
        text = read(path)
        if not text:
            continue
        stripped = re.sub(r"(#|//).*?$", "", text, flags=re.MULTILINE)
        stripped = re.sub(r"/\*.*?\*/", "", stripped, flags=re.DOTALL)
        stripped = re.sub(r"\s+", "", stripped)
        if len(stripped) < 200:
            continue
        digest = hashlib.sha1(stripped.encode("utf-8")).hexdigest()
        out[digest] = os.path.relpath(path, repo_path)
    return out


def audit(repo_path):
    source_files = detector.collect_files(repo_path)
    loc = 0
    for path in source_files:
        text = read(path)
        loc += sum(1 for line in text.splitlines() if line.strip())

    template = template_signals(repo_path, source_files)
    hollow = hollow_signals(repo_path, source_files, loc)

    # Template reuse is the stronger signal of unoriginality, so it is weighted
    # above hollowness; a thorough project built on a scaffold is less like
    # filler than an empty repository with no scaffold at all.
    score = min(100, len(template) * 25 + len(hollow) * 12)

    return {
        "slop_score": score,
        "template_hits": template,
        "hollow_hits": hollow,
        "loc": loc,
        "files": len(source_files),
        "hashes": file_hashes(source_files, repo_path),
    }


def find_duplicates(rows):
    """Repos sharing normalised file content, across a whole sample."""
    owners = {}
    for row in rows:
        for digest in (row.get("slop") or {}).get("hashes", {}):
            owners.setdefault(digest, set()).add(row.get("full_name") or row.get("repo"))
    shared = {d: sorted(names) for d, names in owners.items() if len(names) > 1}
    per_repo = {}
    for names in shared.values():
        for name in names:
            per_repo[name] = per_repo.get(name, 0) + 1
    return {"duplicate_file_groups": len(shared), "repos_sharing_files": per_repo}


def main():
    ap = argparse.ArgumentParser(description="Measure template reuse and hollowness.")
    ap.add_argument("target", help="local path or GitHub URL")
    args = ap.parse_args()
    path, temp = detector.resolve_target(args.target)
    try:
        result = audit(path)
        result.pop("hashes", None)
        print(json.dumps(result, indent=2))
    finally:
        if temp:
            import shutil
            shutil.rmtree(path, ignore_errors=True)


if __name__ == "__main__":
    main()

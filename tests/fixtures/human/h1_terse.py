import os, sys, json
from collections import defaultdict

CACHE = {}

def slugify(s):
    return "".join(c if c.isalnum() else "-" for c in s.lower()).strip("-")

def group_by_owner(repos):
    out = defaultdict(list)
    for r in repos:
        out[r["owner"]].append(r)
    return dict(out)

def main():
    if len(sys.argv) < 2:
        print("usage: prog <file>"); sys.exit(1)
    with open(sys.argv[1]) as fh:
        repos = json.load(fh)
    for owner, rs in sorted(group_by_owner(repos).items()):
        print(owner, len(rs))

if __name__ == "__main__":
    main()

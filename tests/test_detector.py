#!/usr/bin/env python3
"""
test_detector.py — labeled regression suite for the Phase 2 classifier.

Runs repo_ai_detector.analyze_file() over hand-labeled fixtures in
tests/fixtures/{human,ai}/ and reports per-file scores plus a confusion
matrix, so heuristic changes can be checked against known ground truth
instead of a single example.

Decision rule under test: score > 50 (Tier 3/4) => predicted AI-generated.

Usage:
    python3 tests/test_detector.py [-v]
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from repo_ai_detector import analyze_file  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')
THRESHOLD = 50  # > THRESHOLD => predicted AI

# Fixtures that document a KNOWN limitation rather than a target behaviour.
# They still run and report, but don't count as regressions.
KNOWN_LIMITATIONS = {
    'a2_stripped.py': "AI code with comments stripped — detector is comment-dependent",
}


def evaluate(verbose=False):
    rows = []
    for label in ('human', 'ai'):
        folder = os.path.join(FIXTURES, label)
        for fn in sorted(os.listdir(folder)):
            path = os.path.join(folder, fn)
            if not os.path.isfile(path):
                continue
            res = analyze_file(path)
            if res is None:
                print(f"[!] {fn}: unscoreable (skipped by analyze_file)")
                continue
            predicted = 'ai' if res['score'] > THRESHOLD else 'human'
            rows.append({
                'file': fn,
                'actual': label,
                'predicted': predicted,
                'score': res['score'],
                'indicators': res['indicators'],
                'known_limitation': fn in KNOWN_LIMITATIONS,
            })

    tp = sum(1 for r in rows if r['actual'] == 'ai' and r['predicted'] == 'ai')
    tn = sum(1 for r in rows if r['actual'] == 'human' and r['predicted'] == 'human')
    fp = [r for r in rows if r['actual'] == 'human' and r['predicted'] == 'ai']
    fn_ = [r for r in rows if r['actual'] == 'ai' and r['predicted'] == 'human']

    print("=" * 78)
    print(" PHASE 2 CLASSIFIER — LABELED FIXTURE RESULTS")
    print("=" * 78)
    print(f"{'file':<24}{'actual':<9}{'pred':<9}{'score':<8}result")
    print("-" * 78)
    for r in rows:
        ok = r['actual'] == r['predicted']
        if not ok and r['known_limitation']:
            mark = 'KNOWN GAP'
        else:
            mark = 'ok' if ok else '** MISS **'
        print(f"{r['file']:<24}{r['actual']:<9}{r['predicted']:<9}{r['score']:<8}{mark}")
        if verbose:
            for ind in r['indicators']:
                print(f"      - {ind}")

    print("-" * 78)
    print(f"Confusion matrix (threshold: score > {THRESHOLD} => AI)")
    print(f"  True AI  detected as AI    : {tp}")
    print(f"  True human detected as human: {tn}")
    print(f"  False positives (human->AI) : {len(fp)}  {[r['file'] for r in fp]}")
    print(f"  False negatives (AI->human) : {len(fn_)} {[r['file'] for r in fn_]}")

    real_failures = [r for r in (fp + fn_) if not r['known_limitation']]
    if KNOWN_LIMITATIONS:
        print("\nKnown limitations (reported, not counted as regressions):")
        for name, why in KNOWN_LIMITATIONS.items():
            print(f"  - {name}: {why}")

    print()
    if real_failures:
        print(f"FAIL — {len(real_failures)} unexpected misclassification(s): "
              f"{[r['file'] for r in real_failures]}")
        return 1
    print("PASS — all fixtures classified as expected.")
    return 0


if __name__ == "__main__":
    sys.exit(evaluate(verbose='-v' in sys.argv))

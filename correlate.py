#!/usr/bin/env python3
"""Step 9: does more AI mean worse code?

Prior work compares AI-authored commits against human ones -- two boxes. With a
continuous AI score per repository we can ask the sharper question: whether the
*amount* of AI predicts the *amount* of damage.

    python3 correlate.py results.json

Reports the relationship three ways, because each answers a different
objection:

  overall        the headline correlation
  binned         whether the relationship is a slope or a cliff
  within-cohort  the same test inside each cohort separately

The third matters most. New hobby repositories have messier code than mature
projects regardless of AI, so an overall correlation could be entirely explained
by which cohort a repository belongs to. If the relationship survives inside a
single cohort, that explanation is ruled out.
"""

import argparse
import collections
import json
import math
import sys

QUALITY_KEY = "defect_density"

# The 2/sqrt(n) significance rule is far too permissive at very small n: five
# points can reach r=0.96 by chance. Below this many repositories a band is
# reported but never interpreted, whatever r comes out.
MIN_BAND_N = 8


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def usable(rows):
    out = []
    for r in rows:
        q = r.get("quality") or {}
        if not q.get("usable"):
            continue
        if q.get(QUALITY_KEY) is None or r.get("ai_score") is None:
            continue
        out.append(r)
    return out


def describe(rows, label):
    xs = [r["ai_score"] for r in rows]
    ys = [r["quality"][QUALITY_KEY] for r in rows]
    r = pearson(xs, ys)
    if r is None:
        print("  %-16s n=%-4d (too few, or no variation)" % (label, len(rows)))
        return
    # Rough two-tailed p<0.05 threshold. Below this, r is indistinguishable
    # from zero at this sample size and must not be reported as a finding.
    critical = 2.0 / math.sqrt(len(rows))
    if abs(r) < critical:
        print("  %-16s n=%-4d r=%+.3f  NOT SIGNIFICANT (need |r|>%.2f at this n)"
              % (label, len(rows), r, critical))
        return
    direction = "more AI -> worse" if r > 0 else "more AI -> better"
    strength = "weak" if abs(r) < 0.3 else "moderate" if abs(r) < 0.5 else "strong"
    print("  %-16s n=%-4d r=%+.3f  (%s, %s)" % (label, len(rows), r, strength, direction))


def binned(rows):
    bins = collections.OrderedDict([
        ("0-10  (little/none)", lambda s: s < 10),
        ("10-30 (some)", lambda s: 10 <= s < 30),
        ("30-60 (a lot)", lambda s: 30 <= s < 60),
        ("60+   (mostly AI)", lambda s: s >= 60),
    ])
    print("\n  %-22s %5s %14s %12s" % ("AI score band", "n", "defect density", "complexity"))
    for label, test in bins.items():
        group = [r for r in rows if test(r["ai_score"])]
        if not group:
            print("  %-22s %5d %14s %12s" % (label, 0, "-", "-"))
            continue
        dd = sum(r["quality"][QUALITY_KEY] for r in group) / len(group)
        cx = [r["quality"].get("mean_complexity") for r in group]
        cx = [c for c in cx if c is not None]
        cxs = "%.2f" % (sum(cx) / len(cx)) if cx else "-"
        print("  %-22s %5d %14.2f %12s" % (label, len(group), dd, cxs))


def by_age_band(rows):
    """AI score against adoption, inside each age band.

    Age is the confound that has to be removed here. Older repositories have
    had longer to collect stars and are also more likely to predate AI tooling,
    so comparing them directly would measure age twice over. Within a band, both
    sides started with the same amount of time to find users.
    """
    bands = collections.OrderedDict()
    for row in rows:
        v = row.get("value") or {}
        if not v.get("usable") or row.get("ai_score") is None:
            continue
        bands.setdefault(v["age_band"], []).append(row)

    order = [b[0] for b in __import__("value_audit").AGE_BANDS]
    print("\n  Does AI use predict adoption, holding age constant?\n")
    print("  %-14s %5s %11s %10s   %s" % ("age band", "n", "mean adopt", "r", "reading"))
    for name in order:
        group = bands.get(name)
        if not group:
            continue
        xs = [g["ai_score"] for g in group]
        ys = [(g["value"] or {})["adoption"] for g in group]
        mean_adopt = sum(ys) / len(ys)
        r = pearson(xs, ys)
        if r is None:
            print("  %-14s %5d %11.2f %10s   too few" % (name, len(group), mean_adopt, "-"))
            continue
        critical = 2.0 / math.sqrt(len(group))
        if len(group) < MIN_BAND_N:
            reading = "n too small to interpret (need %d+)" % MIN_BAND_N
        elif abs(r) < critical:
            reading = "not significant (need |r|>%.2f)" % critical
        else:
            reading = "more AI -> more adoption" if r > 0 else "more AI -> less adoption"
        print("  %-14s %5d %11.2f %+10.3f   %s" % (name, len(group), mean_adopt, r, reading))

    alive = [r for r in rows if (r.get("value") or {}).get("usable")]
    if alive:
        aband = [r for r in alive if r["value"]["abandoned"]]
        print("\n  Abandoned (no push in 180 days): %d/%d (%.0f%%)"
              % (len(aband), len(alive), 100.0 * len(aband) / len(alive)))
        if aband:
            hi = [r for r in aband if (r.get("ai_score") or 0) >= 20]
            print("  Of those, %d had an AI score of 20 or more." % len(hi))


def main():
    ap = argparse.ArgumentParser(description="Relate AI score to code quality and adoption.")
    ap.add_argument("results", help="JSON from dual_detect.py --quality")
    args = ap.parse_args()

    with open(args.results, encoding="utf-8") as f:
        rows = json.load(f)
    rows = usable(rows)
    if len(rows) < 3:
        sys.exit("need at least 3 repos with quality data; got %d.\n"
                 "Run: python3 dual_detect.py --batch sample.json --quality" % len(rows))

    print("\n" + "=" * 62)
    print(" DOES MORE AI MEAN WORSE CODE?")
    print("=" * 62)
    print("Repos with usable quality data: %d\n" % len(rows))

    describe(rows, "overall")
    by_cohort = collections.defaultdict(list)
    for r in rows:
        by_cohort[r.get("cohort") or "unknown"].append(r)
    for name in sorted(by_cohort):
        describe(by_cohort[name], "within " + name)

    binned(rows)
    by_age_band(rows)

    print("\n  Reading this: a positive r means higher AI score goes with more")
    print("  defects. If 'overall' is positive but every 'within' row is flat,")
    print("  the effect is cohort membership, not AI. Only a relationship that")
    print("  holds inside a cohort supports a claim about AI itself.")
    print("\n  Correlation is not causation either way. This is observational.")


if __name__ == "__main__":
    main()

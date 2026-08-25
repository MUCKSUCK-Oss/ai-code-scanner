# 🕵️‍♂️ Who Can See the AI Code?

An empirical study of **9,982 GitHub repositories**, testing what AI-code detection methods miss — and whether AI use predicts whether a project finds users.

📄 **Paper:** [10.5281/zenodo.22040134](https://doi.org/10.5281/zenodo.22040134)
📊 **Data:** `paper/data/final_n10000.json` — 9,982 records, every number below reproduces from it

---

## The question

Every large study of AI-generated code finds it the same way: by looking for a **label** in git history — a `Co-authored-by` trailer, a bot account, a tool-specific email.

Labels only exist when a tool adds one. Paste code from a chat window and nothing gets recorded.

So this study ran **two** detectors over the same repositories: one reading git metadata, one reading the code itself.

## What we found

**The two methods barely overlap.**

| Outcome | Repos | Share |
|---|---|---|
| Git metadata only | 792 | 7.9% |
| Code reading only | **106** | 1.1% |
| Both agreed | **10** | 0.1% |
| Neither | 9,074 | 90.9% |

Out of 908 repositories flagged by either method, they agreed on **ten**. The 106 caught only by code reading carry AI code with no git marker at all — invisible to every published prevalence estimate.

**The detector is validated.** Against 3,333 repositories dormant since before 2021 — so definitionally human-written:

| Method | False positives |
|---|---|
| Git metadata | **0 / 3,333** (0.00%) |
| Code reading | 33 / 3,333 (0.99%) |

**AI use does not predict adoption.**

| Within | n | r | Verdict |
|---|---|---|---|
| Popular repos | 3,326 | +0.131 | significant, under 2% of variance |
| New repos | 3,323 | +0.016 | **no effect** |

At this sample size the significance bar is r = 0.035. A real effect in either direction would have shown up. Neither "AI slop is killing open source" nor its opposite survives the data.

## Three measurement traps

The study documents three measures that produced confident, wrong answers before being caught. The first is built into the standard method used by published work.

1. **Presence is not prevalence.** Counting repos with *any* AI commit says popular projects use more AI (55.6% vs 26.2%). Counting the *share* of commits reverses it (3.90% vs 5.93%). A repo with 250 commits and 40 contributors catches an AI commit if any one person uses a tool once — so the criterion partly measures project activity. Three repos were once flagged on a single commit out of 250, including a professional IDE at 0.4%.

2. **An AI commit is not AI code.** A commit tagged "Claude" may have edited only a README. Parsing the actual diffs removed 15% as documentation-only.

3. **Engineering practice is not value.** An early "slop" score counted missing tests, CI and licences. The pre-LLM control scored 24.9 — *worse* than new AI-heavy repos at 23.8. Old abandoned human code looked sloppier than anything AI wrote. 81% of that score turned out to be professional-practice signals, not substance.

---

## Reproduce it

Stdlib only for detection; static analysis needs three packages.

```bash
pip install pylint bandit radon        # only for --quality
```

Scan any repository, local path or public GitHub URL:

```bash
python3 dual_detect.py https://github.com/owner/repo
```

Run the full study pipeline:

```bash
python3 github_sampler.py --per-cohort 3333 -o sample.json
python3 dual_detect.py --batch sample.json --quality --slop -o results.json
python3 correlate.py results.json
```

Reproduce the headline table from the published data:

```bash
python3 -c "import json,dual_detect; dual_detect.summarise(json.load(open('paper/data/final_n10000.json')))"
```

Check the classifier against labelled fixtures:

```bash
python3 tests/test_detector.py -v
```

Expect 8/8 fixtures as labelled, 0 false positives.

## What each script does

| Script | Role |
|---|---|
| `github_sampler.py` | Draws the three cohorts, even quotas per language and year |
| `dual_detect.py` | Runs both detectors on one clone; produces the 0–100 AI score |
| `repo_ai_detector.py` | The content classifier — structural fingerprints, weak/strong split |
| `quality_audit.py` | Pylint, Bandit, radon on sampled files → defect density |
| `slop_audit.py` | Template reuse, hollowness, cross-repo duplicate hashing |
| `value_audit.py` | Adoption per month since creation, age-banded |
| `correlate.py` | Ties AI score to quality and adoption, with significance gates |

## How the content classifier scores

Files score 0–100 on structural fingerprints, split by how specific they are.

**Weak signals** — also just good engineering: comment-to-code ratio, docstring coverage, type-hint saturation, generic identifiers.

**Strong signals** — structural artifacts of generation: conversational boilerplate, uniformly padded box-drawing banners, sequentially numbered step comments, self-narrating commentary about the editing process, `<file> — description` headers, rigid doc templates on every function.

**If no strong signal fires, the score caps at 40.** Documentation density alone can never produce a high-confidence verdict. That rule exists because `psf/requests` — released years before LLMs — produced a maximum-score false positive on docstring coverage alone.

## Known limitations

Stated plainly, because a detector that hides its failure modes is not useful.

- **The content classifier is weak.** AUC 0.604 against metadata-labelled ground truth, barely above chance. It catches raw model output, not AI code that has been reviewed and edited. Its 106 unique finds are real; it is not a general-purpose detector.
- **Comment-dependent.** AI code with comments stripped scores ~20 and is missed — see `tests/fixtures/ai/a2_stripped.py`.
- **Quality analysis is Python-only.** Pylint and Bandit do not cover JavaScript, so that arm reflects 2,760 repositories.
- **History depth is capped at 250 commits**, so older AI use in long-lived projects is invisible.
- **Stars are an imperfect proxy for worth.** They reward visibility and timing too.
- **Observational.** No causal claim is made or supported. The association in established projects is at least as easily explained by active teams adopting more tooling of every kind.

## Citing

```bibtex
@misc{kaushik2026aicode,
  author       = {Kaushik, Maulik},
  title        = {Who Can See the AI Code? Detection Blind Spots and the
                  Limits of Prevalence Estimates on GitHub},
  year         = {2026},
  publisher    = {Zenodo},
  doi          = {10.5281/zenodo.22040134},
  url          = {https://doi.org/10.5281/zenodo.22040134}
}
```

## License

MIT for the code. Paper and data are CC BY 4.0.

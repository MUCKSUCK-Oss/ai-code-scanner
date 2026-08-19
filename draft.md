# Who Can See the AI Code? Measurement Bias in Detecting AI-Generated Code on GitHub

**Author:** Maulik
**Status:** DRAFT — results below are from a 60-repository pilot. Numbers marked `[PILOT]` must be regenerated at n≥300 before submission.

---

## Abstract

*(Write this last. Draft placeholder:)*

Large-scale studies of AI-generated code on GitHub identify AI authorship through git metadata: `Co-authored-by` trailers, agent bot accounts, and tool-specific author emails. A repository is then typically treated as AI-involved if any such marker is present. We show this binary criterion is confounded by repository size, and that correcting it reverses the apparent result. Running two detection methods — metadata inspection and a content-based heuristic classifier — over 60 repositories split between popular projects (≥1000 stars) and new, low-visibility projects (<10 stars, created after 2023), the presence-based criterion suggests AI use is three times more common in popular repositories (57% vs 20%). But three of those repositories were flagged on a single commit out of 250, and one was a large professional IDE with 0.4% AI commits. Measuring the *share* of history that is AI-authored instead, the direction inverts: at a 25% threshold, 10% of new repositories qualify versus 3% of popular ones, with mean AI share of 6.2% versus 4.5%. Separately, content-based detection identified no repositories that metadata had not already flagged, and scored AUC 0.604 against metadata-labelled ground truth. We conclude that binary AI-presence flags measure project activity as much as AI adoption, and that the pasted-code population remains unobservable by either method.

---

## 1. Introduction

GitHub is absorbing AI-generated code faster than anyone can measure it. GitHub's Octoverse 2025 reported 230 new repositories created every minute and 36 million new developers in a single year. Maintainers report the consequences directly: in January 2026 the curl project shut down its bug bounty programme, reporting that roughly 20% of submissions were AI-generated noise while only about 5% were genuine, creating what its maintainers described as a denial-of-service on their review capacity.

A body of research has grown to measure this. These studies consistently find that AI-generated code accumulates technical debt. But they share a methodological assumption that has not been examined: they locate AI code by looking for code that *announced itself*.

This paper asks what that assumption costs.

**Contribution.** We compare two detection methods on the same repositories and show that (1) the binary "any AI marker" criterion used in prior work is confounded by repository size, and correcting it to a share-based measure reverses the apparent cohort difference; (2) content-based heuristic detection adds nothing beyond metadata at any usable threshold; and (3) the pasted-code population is therefore observable by neither method. We report negative results for our own detector and for our own first measurement, and treat both as evidence rather than failure.

---

## 2. Related Work

**Quality and technical debt.** *Debt Behind the AI Boom* analysed 304,362 AI-authored commits across 6,275 repositories, finding 484,606 distinct issues introduced, with 24.2% still unresolved at repository HEAD and security issues surviving at 41.1%. GitClear's analysis of 211 million lines of code found block duplication rising sharply and code churn roughly doubling relative to the pre-AI baseline. A Carnegie Mellon study of 807 repositories adopting Cursor found static analysis warnings up ~30% and complexity up ~41%.

> **TODO before submission:** open each of these papers and confirm the inclusion criteria yourself. Do not cite second-hand summaries.

**Detection method.** *Debt Behind the AI Boom* identified AI commits through actor logins, author emails, author names, and `Co-authored-by` trailers, covering 29 tools that leave identifiable traces. A separate large-scale study located AI code by searching for files mentioning LLM tools, then filtering with an LLM classifier, reporting precision of 88/100 on positives.

**The gap.** A validated multi-method census of 180 million repositories concludes that no single detection approach captures all AI-generated code, and explicitly names *developing more sophisticated heuristics for code-based identification* as future work.

**Population coverage.** Critically for this paper: *Debt Behind the AI Boom* included only repositories with ≥100 stars, and a task-stratified study of PR acceptance applied the same ≥100 star threshold. The low-visibility population — new, unreviewed, single-author projects — is excluded from these analyses by construction, despite being the population most associated in practitioner discussion with low-quality AI output.

---

## 3. Method

### 3.1 Two detection arms

The two methods fail in opposite directions, which is why we run both.

**Metadata detection** reads git history for markers left by AI coding agents. We match case-insensitively against `Co-authored-by` trailers, agent author emails, and bot account names for six tools: Claude, GitHub Copilot, Cursor, Devin, Gemini, and Codex. This mirrors the approach used in prior work, so our metadata arm is directly comparable to published studies. It is reliable when a marker exists and blind when one does not.

We record two quantities per repository: whether *any* AI marker appears (the criterion used in prior work), and the *share* of scanned commits carrying one. A repository is flagged when that share reaches `METADATA_MIN_SHARE` = 10%. §4.2 and §4.3 show why this distinction matters: the two criteria disagree about which cohort uses more AI.

**Content detection** scores the source code itself, ignoring all repository metadata. It is blind to AI output that has been reviewed and cleaned, but it is the only method that can detect code pasted from a chat interface.

Implementation: `dual_detect.py`, which clones each repository once (depth 250) and runs both arms against the same working copy.

### 3.2 Content classifier design

Files are scored 0–100. Signals are divided by specificity, which addresses this approach's main confound: **mature, well-documented human code resembles AI-generated code under naive documentation-density heuristics.**

*Weak signals* (also markers of good engineering practice): high comment-to-code ratio, near-complete docstring or JSDoc coverage, type-hint saturation, generic variable naming.

*Strong signals* (structural fingerprints of AI scaffolding): conversational boilerplate, uniformly padded Unicode box-drawing section banners, sequentially numbered step-comments, self-narrating commentary about the editing process, `<filename> — description` header comments, and rigid documentation templates repeated across every function.

**If no strong signal fires, the score is capped at 40.** Documentation density alone cannot produce a high-confidence verdict. This rule was added after `psf/requests` — released years before LLMs existed and therefore human-written by definition — produced a maximum-score false positive on docstring coverage and comment ratio alone.

Repository-level scores are the LOC-weighted mean of file scores. A repository is flagged when this exceeds 40.

### 3.3 Cohorts

| Cohort | Definition | Rationale |
|---|---|---|
| Popular | ≥1000 stars, pushed since 2024 | Reviewed, vetted; where prior work looks |
| New | <10 stars, created after 2023 | Unreviewed; where prior work does not look |
| Control | ≥100 stars, created 2012–2020 | Predates LLMs; any flag is a false positive |

Sampling draws an even quota from every (language, year) cell across Python, JavaScript, TypeScript, Java, and Go, rather than filling greedily. An earlier version filled greedily and produced a cohort that was 100% Python and entirely 2009–2012 — an artifact that would have confounded the comparison, since older repositories are both more popular and definitionally more human-written. Implementation: `github_sampler.py`.

### 3.4 Validating the content classifier

Ground-truth labels come free from metadata: commits carrying an AI co-author trailer identify AI-authored code without manual labelling. GitHub commit search returns approximately 12 million commits carrying a Claude trailer and 1.75 million carrying Copilot's.

We restrict to files a commit **added**, so the entire file is AI-authored rather than a human file with an AI patch applied. Human controls are files from repositories whose last push predates 2021. Both sets are scored by the classifier, which never sees metadata. Implementation: `provenance_experiment.py`.

---

## 4. Results

### 4.1 Two methods, same repositories `[PILOT n=60]`

| Outcome | Count | % |
|---|---|---|
| Metadata only | 23 | 38.3% |
| Content only | 0 | 0.0% |
| Both | 0 | 0.0% |
| Neither | 37 | 61.7% |

Content detection identified **zero** repositories that metadata had not already flagged.

### 4.2 The presence criterion is size-confounded `[PILOT n=30 per cohort]`

Treating any AI marker as evidence of AI involvement — the criterion used in prior work — produces a large cohort gap:

| Cohort | Any AI commit |
|---|---|
| Popular | 17/30 (57%) |
| New | 6/30 (20%) |

This result does not survive inspection. Of the 23 flagged repositories, **three were flagged on a single commit out of 250**, and seven on five or fewer. The weakest case is `rstudio/rstudio` — a large professional IDE — flagged on 1 of 250 commits (0.4%).

Because busy projects accumulate more commits and more contributors, they are mechanically more likely to contain at least one AI-authored commit. The criterion partly measures activity, not adoption.

### 4.3 Measuring AI *share* reverses the direction

Requiring AI commits to constitute a meaningful fraction of recent history:

| Threshold | Popular | New |
|---|---|---|
| Any AI commit | 17/30 (57%) | 6/30 (20%) |
| ≥5% of commits | 8/30 (27%) | 6/30 (20%) |
| ≥10% of commits | 5/30 (17%) | 6/30 (20%) |
| ≥25% of commits | 1/30 (3%) | **3/30 (10%)** |
| ≥50% of commits | 0/30 (0%) | **1/30 (3%)** |

| Cohort | Mean AI share | Median | Max |
|---|---|---|---|
| Popular | 4.5% | 0.4% | 32.8% |
| New | 6.2% | 0.0% | **77.2%** |

The gap closes by the 10% threshold and inverts above it. Popular repositories touch AI more often; new repositories, when they use it, are built on it far more heavily. We adopt a 10% share threshold (`METADATA_MIN_SHARE`) for the remainder of this paper.

Tools observed: Claude, Copilot, Codex, Cursor (popular); Claude, Copilot, Codex (new).

Content scores trend slightly higher in the new cohort (mean 11.0 vs 9.1; 4/30 above 25 vs 0/30), but no repository in either cohort reached the content flagging threshold.

> **Caution:** at n=30 per cohort, the inverted result rests on 3 repositories versus 1. It indicates a direction to test, not an established effect. This is the single most important reason to rerun at n≥300.

### 4.4 Classifier performance against ground truth `[PILOT n=12 per class]`

| Cutoff | Recall | False-positive rate |
|---|---|---|
| 15–30 | 16.7% | 0.0% |
| 40 | 8.3% | 0.0% |
| 50 (default) | 0.0% | 0.0% |

**AUC = 0.604** (0.5 = chance). The classifier is precise but has very low recall: when it flags code it is correct, but it detects roughly one in six known-AI files.

> **TODO:** regenerate at n≥150 per class. AUC from 12 samples per class carries very wide error bars and should not be reported as a finding at this size.

### 4.5 Classifier validation

Labelled fixtures: 8/8 classified as expected, 0 false positives. Pre-LLM repositories: `psf/requests` 23.1, `pallets/flask` 13.9, `expressjs/express` 9.8 — all Tier 1 (human), confirming no systematic false-positive problem on human code.

---

## 5. Discussion

### 5.1 The worked example

Two repositories illustrate the entire problem.

**`rodaddy/open-brain`** — 173 of its 250 most recent commits carry a Claude co-author trailer. It is, by any reasonable definition, an AI-built project. Our content classifier scores it **13.7**, well inside the human range. The AI code was reviewed, edited, and integrated; the stylistic tells did not survive.

**`debate-arena`** — written entirely with AI assistance by pasting from a chat interface. It carries **zero** AI markers in git history. Our content classifier scores it **70.9**, comfortably flagged. The output was never cleaned, so the fingerprints remain.

Each repository is invisible to exactly one method. Neither method sees both.

### 5.2 Presence is not prevalence

Our first analysis used the criterion prior work uses: a repository counts as AI-involved if any AI marker appears in its history. It produced a clean, publishable-looking result — 57% versus 20% — that was an artifact of our own measure.

The mechanism is simple. A repository with 250 commits from 40 contributors will contain an AI-authored commit if *any one* of those contributors used an agent once. A three-month-old solo project has far fewer opportunities to accumulate such a marker. The criterion therefore rewards size and contributor count, both of which correlate with popularity by construction.

Once AI is required to constitute a real share of history, the difference disappears by the 10% threshold and inverts above it (§4.3). Popular repositories *touch* AI more often; new repositories, when they use it, are built on it far more heavily — one new repository in our sample is 77.2% AI-authored, well beyond anything in the popular cohort.

The practical recommendation is narrow but concrete: **studies of AI prevalence should report the share of commits that are AI-authored, not the proportion of repositories containing any AI commit.** The two measures can point in opposite directions on the same data, as they do here.

### 5.3 Two kinds of invisibility

Even with the corrected measure, a second bias remains untouched. Professional teams adopt agent tooling — Copilot, Claude Code, Cursor — which attaches attribution automatically. An individual building a weekend project is more likely to paste from a chat window, which attaches nothing. Metadata therefore records agent-tool adoption more faithfully than it records AI use.

This is a claim about measurement, not about quality. This study does not measure code quality at all.

### 5.4 Why content detection cannot close the gap

Our own results rule out the obvious fix. Content-based detection added zero repositories (§4.1) and achieved AUC 0.604 against ground truth (§4.4). At thresholds low enough to catch anything, it disagrees with metadata more often than it agrees.

The reason is visible in §5.1: the classifier detects *raw* model output. Code that has passed through human review no longer carries the signal. Since the detectable form is also the form most likely to appear in unreviewed hobby projects, a content classifier is biased toward exactly the opposite population from metadata — but too weakly to be useful.

**The invisible population remains unmeasured, and neither available method can reach it.**

---

## 6. Limitations

- **Inverted result rests on few repositories.** The share-based cohort difference (§4.3) is 3 repositories versus 1 at the 25% threshold. It is a direction to test, not an effect we have established.
- **Share threshold is a judgement call.** `METADATA_MIN_SHARE` = 10% is defensible but arbitrary; §4.3 reports the full sweep so readers can apply their own.
- **Pilot scale.** n=60 repositories, n=12 per class for the ROC analysis. The 57%/20% gap requires n≥300 before it should be trusted.
- **Comment dependence.** The classifier relies on comments. AI code with comments stripped scores ~20 and is not detected (`tests/fixtures/ai/a2_stripped.py`).
- **Noisy positive labels.** Files "added" in an AI-co-authored commit may include human-written files added in the same commit, which would depress measured recall.
- **History depth.** Metadata scanning covers the most recent 250 commits, so older AI use in long-lived repositories is missed.
- **Heuristic, not learned.** The classifier is hand-written pattern matching, not a trained model, and was calibrated on a small number of known-provenance repositories.
- **Single detector generation.** Different models leave different fingerprints; results may not transfer to tools we did not sample.
- **Observational.** No causal claim is made or supported.

---

## 7. Conclusion

Two detection methods, run over the same repositories, disagree completely: metadata flagged repositories that content scored as human, and the one repository we know to be entirely AI-written carried no metadata at all.

More importantly, our own first measurement was wrong in an instructive way. Counting repositories that contain *any* AI commit showed popular projects using AI three times more than new ones. Counting the *share* of history that is AI-authored reversed it. The first measure was tracking repository size; three repositories were flagged on one commit in 250, including a large professional IDE at 0.4%. Prevalence work should report shares, not presence.

The consequence is that current estimates of how much AI code exists on GitHub are estimates of how much AI code *identifies itself*, measured with a criterion that also rewards project activity. For well-resourced projects using agent tooling, those estimates may be close. For the fast-growing population of new, unreviewed, single-author repositories — the population the code-quality discussion is mostly about — neither available method can see clearly, and we found no way to fix that.

---

## Appendix: Reproduction

All numbers are reproducible from the repository at `github.com/MUCKSUCK-Oss/ai-code-scanner`.

```bash
python3 dual_detect.py --batch sample.json      # §4.1, §4.2
python3 provenance_experiment.py --limit 150    # §4.3
python3 tests/test_detector.py -v               # §4.4
python3 dual_detect.py https://github.com/rodaddy/open-brain   # §5.1
python3 dual_detect.py ./debate-arena-main                     # §5.1
```

Raw pilot data: `paper/data/`.

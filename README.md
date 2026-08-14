# 🕵️‍♂️ API-Free Heuristic AI Code Scanner

A lightweight, fully local Python tool that scans codebases to detect the probability of AI-generated code. Instead of relying on paid APIs or external machine learning models, this scanner uses a **heuristic approach**—looking for the common behavioral "tells" and structural patterns left behind by LLMs like ChatGPT and Claude.

Built as **Phase 2** of a research study on the proliferation and quality of AI-generated code in open-source repositories, as AI-assisted commits are projected to grow from ~1 billion to 14+ billion per year.

## 🚀 Features
* **100% Local & API-Free:** No API keys required, no rate limits, and your code never leaves your machine.
* **Whole-Repo Scanning:** Point it at a local folder *or* a public GitHub URL — public repos are shallow-cloned, so still no API key needed.
* **Multi-Language:** Python, JavaScript/TypeScript, Java, C/C++/C#, Go, Rust, Ruby, PHP, Swift, Kotlin.
* **Heuristic Scoring System:** Grades files from 0 to 100 based on specific AI coding habits.
* **4-Tier Flagging:** Visually categorizes files from "Human-Written" (Green) to "Likely AI Slop" (Red).
* **Detailed Readouts:** Explains *why* a file received its score by listing the specific flags triggered.
* **Validated Against Ground Truth:** Ships with a labeled regression suite and a confusion matrix — not just vibes.

## 🛠️ Usage

Scan a whole repository — local path or public GitHub URL:

```bash
python3 repo_ai_detector.py <local-path-or-github-url> [--top N] [--json out.json]
```

```bash
python3 repo_ai_detector.py https://github.com/psf/requests --top 10
```

Stdlib only — nothing to `pip install`.

## 🧠 How It Works (The Heuristics)

Files are scored 0–100 and bucketed into four tiers. Signals are split by **specificity**, which is the main defence against this approach's biggest confound: *mature, well-documented human code looks AI-like under naive documentation-density heuristics.*

### Weak signals — ambiguous, also just good practice
1. **Over-Commenting:** Unusually high comment-to-code ratios or excessive generic explanatory comments (`# initialize variable`).
2. **Perfect Saturation:** Textbook 100% docstring/JSDoc and type-hint coverage across all functions.
3. **Generic Variables:** Heavy reliance on placeholder names (`data`, `temp`, `result`, `val`).

### Strong signals — structural fingerprints specific to AI scaffolding
4. **Conversational Boilerplate:** Artifacts like *"Here is the script"* or *"Step 1:"* left in by mistake.
5. **Section Banners:** Uniformly padded Unicode box-drawing dividers (`// ── Label ─────────`) that humans rarely type by hand.
6. **Numbered Step-Comments:** Tutorial-style `1.`, `2.`, `3.` structuring across a file.
7. **Reasoning Trails:** Self-narrating commentary about the *editing process* left inline (*"Actually the original... nothing more to do"*).
8. **Scaffolding Headers:** A `<file>.ext — Description of the file` header comment on the first line.
9. **Rigid Doc Templates:** An identical `@param`/`Returns:` skeleton repeated across *every* function.

**If no strong signal fires, the score is capped at 40 (Tier 2).** Documentation density alone can never produce a high-confidence AI verdict. This rule was added after `psf/requests` — written years before LLMs existed — produced a **Tier 4 false positive** on docstring coverage and comment ratio alone.

## 📊 Validation

```bash
python3 tests/test_detector.py -v
```

Scores hand-labeled fixtures in `tests/fixtures/{human,ai}/` (decision rule: score > 50 ⇒ AI) and prints a confusion matrix. The fixtures deliberately include the *hard* cases — professionally documented human code, human code using ASCII section dividers — since easy fixtures would prove nothing.

Current results — fixtures **8/8 as expected, 0 false positives**. Against real repositories:

| Repo | Provenance | Score | Tier |
|---|---|---|---|
| internal calibration repo | known AI-generated | 70.9 | 🟧 Tier 3 Orange |
| `psf/requests` | pre-LLM, human | 23.1 | 🟩 Tier 1 Green |
| `pallets/flask` | pre-LLM, human | 13.9 | 🟩 Tier 1 Green |
| `expressjs/express` | pre-LLM, human | 9.8 | 🟩 Tier 1 Green |

Repositories whose code predates ~2021 are *definitionally* human-written, which makes them the cheapest available control cohort for false-positive testing.

## ⚠️ Known Limitations

Stated plainly, because a detector that hides its failure modes isn't useful:

* **Comment-dependent.** AI code with comments stripped scores ~20/Tier 1 (see `tests/fixtures/ai/a2_stripped.py`, tracked as a known gap). Closing it needs non-comment signals — AST shape, identifier distributions, commit metadata.
* **Heuristic, not a validated classifier.** This is regex pattern matching, not a statistically validated model. Treat tiers as a **triage signal, not a verdict**.
* **Calibrated on a limited ground-truth set.** Different models leave different fingerprints; the structural tells here come from a small number of known-provenance repositories.

## 🔬 Research Context

This tool is Phase 2 of a four-phase pipeline:

| Phase | Purpose | Status |
|---|---|---|
| 1. Data Collection | GitHub API scrape of ~10,000 repos, skewed toward active projects | not started |
| 2. AI Classification | Detect AI fingerprints, rank files Tier 1 → Tier 4 | ✅ **implemented** |
| 3. Quality Auditing | Static analysis (Pylint, Bandit) for logic errors, security, redundancy | not started |
| 4. Utility Score (U) | Composite metric weighting syntax, security, and duplication | not started |

The end goal is a **Comparative Cohort Analysis** testing whether AI acts as a productivity multiplier in high-vetted top repositories, or mostly deposits "code slop" into new and unfiltered ones.

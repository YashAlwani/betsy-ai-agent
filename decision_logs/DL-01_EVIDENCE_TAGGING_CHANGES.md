# DL-01 — Evidence Tagging Changes (Before / After)

**File changed:** `decision_logs/[DL-01] How do I build a realistic test environment before writing any agent code.txt`
**Date:** 2026-06-12
**Reason:** DL-01 was the only decision log still using the old `[path/file.ext]` bracket
style for inline references. DL-02 through DL-08 already use the bare `@name`
convention. These edits bring DL-01 in line. **No prose was rewritten** — only the
reference tokens were changed, plus one missing footer line was added.

---

## Part A — Straight retags (path + extension stripped to bare `@name`)

| # | Section | Before | After |
|---|---------|--------|-------|
| 1 | 5. Why this decision | `The inventory data [mock_data/inventory.json] holds the 12 SKUs` | `The inventory data @inventory holds the 12 SKUs` |
| 2 | 5. Why this decision | `The supplier data [mock_data/suppliers.json] gives each supplier` | `The supplier data @suppliers gives each supplier` |
| 3 | 5. Why this decision | `The scenario files [scenarios/] each describe one problem` | `The scenario files @scenarios each describe one problem` |
| 4 | 5. Why this decision | `The scenario injection [server/state.py] applies a scenario` | `The scenario injection @state applies a scenario` |
| 5 | 6. Does this hold up | `the base state is copied on every injection [server/state.py].` | `the base state is copied on every injection (@state).` |

---

## Part B — Structural fixes (design-doc references)

These three were **not** simple strips. The other logs never put a `.md` or a diagram
`.png` inline as a token — design docs live in the footer `Source:` line (which the
upload platform maps to their PDF versions) and the GAP source is cited inline as
`@bpm_analysis`. The reference is **kept**, not removed: an inline `@token` now points
to it, and the footer `Source:` line carries the source path.

| # | Section | Before | After |
|---|---------|--------|-------|
| 6 | 5. Why this decision | `According to the case summary [analysis/case_summary.md], preventing stockouts` | `According to the case summary (@case_summary), preventing stockouts` |
| 7 | 5. Why this decision | `According to the stakeholder analysis [analysis/stakeholder_analysis.md], production needs speed` | `According to the stakeholder analysis (@stakeholder_analysis), production needs speed` |
| 8 | 5. Why this decision | `According to the before-and-after picture in the GAP analysis [diagrams/gap-as-is.png, bpm_analysis.html], the four situations` | `According to the before-and-after picture in the GAP analysis (@bpm_analysis), the four situations` |

**Footer — added a `Source:` line** (DL-01 was the only log missing one):

```
Before:
  Diagrams: diagrams/gap-as-is.png, decision_logs/images/gap-dashboard-empty-log.png, decision_logs/images/gap-supplier-scoreboard.png
  LO stages: Analyzing, Advising, Designing, Realizing, Managing

After:
  Diagrams: diagrams/gap-as-is.png, decision_logs/images/gap-dashboard-empty-log.png, decision_logs/images/gap-supplier-scoreboard.png
  Source: bpm_analysis.html, analysis/case_summary.md, analysis/stakeholder_analysis.md
  LO stages: Analyzing, Advising, Designing, Realizing, Managing
```

> Note on #8: the inline `diagrams/gap-as-is.png` reference was dropped from the
> sentence because that diagram is already carried by the `Diagrams:` footer line **and**
> by an `[IMAGE: gap-as-is.png — …]` callout further down the log. Nothing is lost.

---

## Evidence-name mapping (for the upload platform)

The inline `@token` → the evidence file it should be tagged to:

| Inline token | Source file | Upload evidence (PDF/HTML) |
|--------------|-------------|----------------------------|
| `@inventory` | `mock_data/inventory.json` | (data file) |
| `@suppliers` | `mock_data/suppliers.json` | (data file) — **see collision below** |
| `@scenarios` | `scenarios/` | (data dir) |
| `@state` | `server/state.py` | (code) — **see collision below** |
| `@case_summary` | `analysis/case_summary.md` | `pdf_exports/analysis/case_summary.pdf` |
| `@stakeholder_analysis` | `analysis/stakeholder_analysis.md` | `pdf_exports/analysis/stakeholder_analysis.pdf` |
| `@bpm_analysis` | `bpm_analysis.html` | `upload/bpm_analysis.html` |

---

## Collisions — evidences that need a CUSTOM name on the upload platform

These bare tokens resolve to **different files** in different logs. Inline prose
disambiguates by context, but on the upload platform each must be given a distinct
custom evidence name so they don't merge:

| Bare token | File A | File B | Appears in | Suggested custom names |
|------------|--------|--------|-----------|------------------------|
| `@state` | `server/state.py` | `pipeline/state.py` **and** `orchestra/state.py` | DL-01 / DL-05 / DL-06 vs DL-02 | `server-state` / `pipeline-state` / `orchestra-state` |
| `@graph` | `pipeline/graph.py` | `orchestra/graph.py` | both in DL-02 | `pipeline-graph` / `orchestra-graph` |
| `@suppliers` | `mock_data/suppliers.json` | `server/routers/suppliers.py` | DL-01 vs DL-07 | `suppliers-data` / `suppliers-router` |

---

## Logs NOT changed

DL-02 through DL-08 and `DL-SUMMARY.txt` already use the `@name` convention
consistently — no evidence-tagging changes were needed in them.

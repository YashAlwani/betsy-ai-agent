# Evidence Manifest — `@token` → evidence name → file to upload

**Purpose:** On the upload platform, every `@token` in the decision-log text links to an
uploaded evidence of the **same name**. This table is the upload checklist: for each
`@token`, upload the listed file and name the evidence exactly the token (without the `@`).

**Rule:** every distinct file = one evidence = one unique `@name`. Collisions (one `@name`
pointing at two different files) are resolved below.

**Footers are tokenized.** The `Files:` / `Diagrams:` / `Source:` footer lines use bare
`@tokens` now (no paths). Only `[IMAGE: ...]` callouts in the body keep a path. This
manifest is the single place that maps each `@token` back to a real file.

**Footnote bridge (`¹`).** When the body points straight at a design doc but the
underlying code lives in the footer, a superscript number bridges them: e.g. DL-04 body
`¹@api-control-layer` ↔ footer `¹@main` (= server/main.py). Design is foregrounded in the
prose; the code stays one hop away in the footer.

---

## Collisions resolved (Step 1)

| Old token | Was ambiguous between | Now |
|-----------|----------------------|-----|
| `@state` | server/state.py · pipeline/state.py · orchestra/state.py | `@state` = server/state.py only; agent ones renamed below |
| `@graph` | pipeline/graph.py · orchestra/graph.py | split into `@pipeline-graph` / `@orchestra-graph` |

Edited in DL-02: `@graph`→`@pipeline-graph` (pipeline context) and `@orchestra-graph`
(orchestra context, ×2); `@state`→`@pipeline-state, @orchestra-state` (the "each pattern
keeps its own state file" line). DL-01/05/06 `@state` (server/state.py) left unchanged.

---

## Body tokens — code & data (upload the source file, name = token)

| `@token` | Evidence name | File to upload | Used in |
|----------|---------------|----------------|---------|
| `@inventory` | inventory | mock_data/inventory.json | DL-01 |
| `@suppliers` | suppliers | mock_data/suppliers.json | DL-01 |
| `@scenarios` | scenarios | scenarios/ (folder) | DL-01 |
| `@state` | state | server/state.py | DL-01, DL-05, DL-06 |
| `@pipeline-graph` | pipeline-graph | pipeline/graph.py | DL-02 |
| `@orchestra-graph` | orchestra-graph | orchestra/graph.py | DL-02 |
| `@pipeline-state` | pipeline-state | pipeline/state.py | DL-02 |
| `@orchestra-state` | orchestra-state | orchestra/state.py | DL-02 |
| `@decide` | decide | pipeline/nodes/decide.py | DL-02, DL-04 |
| `@act` | act | pipeline/nodes/act.py | DL-05 |
| `@evaluate` | evaluate | pipeline/nodes/evaluate.py | DL-07 |
| `@llm` | llm | shared/llm.py | DL-02, DL-04 |
| `@api_client` | api_client | shared/api_client.py | DL-02, DL-05 |
| `@inventory_monitor` | inventory_monitor | orchestra/agents/inventory_monitor.py | DL-02 |
| `@supplier_scout` | supplier_scout | orchestra/agents/supplier_scout.py | DL-02 |
| `@invoice_auditor` | invoice_auditor | orchestra/agents/invoice_auditor.py | DL-02 |
| `@betsy` | betsy | dashboard/betsy.html | DL-03/04/05/06/08 |
| `@index` | index | dashboard/index.html | DL-03, DL-04 |
| `@wireframe` | wireframe | dashboard/wireframe.html | DL-03 |
| `@main` | main | server/main.py | DL-04, DL-06 |
| `@approvals` | approvals | server/routers/approvals.py | DL-05 |
| `@orders` | orders | server/routers/orders.py | DL-06 |
| `@stats` | stats | server/routers/stats.py | DL-06 |
| `@db` | db | server/db.py | DL-06 |
| `@scheduler_instance` | scheduler_instance | server/scheduler_instance.py | DL-06 |
| `@config` | config | server/config.py | DL-08 |
| `@notifier` | notifier | server/notifier.py | DL-08 |
| `@suppliers-router` | suppliers-router | server/routers/suppliers.py | DL-07 footer |
| `@notifications-router` | notifications-router | server/routers/notifications.py | DL-08 footer |
| `@requirements` | requirements | requirements.txt | DL-08 footer |
| `@test_ema_learning` | test_ema_learning | tests/test_ema_learning.py | DL-06 |
| `@test_long_term_learning` | test_long_term_learning | tests/test_long_term_learning.py | DL-07 |
| `@test_notifier` | test_notifier | tests/test_notifier.py | DL-08 |

## Body tokens — analysis / GAP source (upload the PDF/HTML)

| `@token` | Evidence name | File to upload | Used in |
|----------|---------------|----------------|---------|
| `@bpm_analysis` | bpm_analysis | bpm_analysis.html | all DLs |
| `@case_summary` | case_summary | pdf_exports/analysis/case_summary.pdf | DL-01 |
| `@stakeholder_analysis` | stakeholder_analysis | pdf_exports/analysis/stakeholder_analysis.pdf | DL-01 |

## Summary tokens — diagrams (upload the PNG)

| `@token` | File to upload |
|----------|----------------|
| `@decision-lifecycle` | diagrams/decision-lifecycle.png |
| `@gap-as-is` | diagrams/gap-as-is.png |
| `@gap-to-be` | diagrams/gap-to-be.png |
| `@gap-scenario-stockout` | diagrams/gap-scenario-stockout.png |
| `@gap-scenario-price-spike` | diagrams/gap-scenario-price-spike.png |
| `@gap-scenario-duplicate-invoice` | diagrams/gap-scenario-duplicate-invoice.png |
| `@pipeline-overview` | diagrams/pipeline-overview.png |
| `@orchestra-overview` | diagrams/orchestra-overview.png |
| `@orchestra-conflict` | diagrams/orchestra-conflict.png |
| `@system-c4-container` | diagrams/system-c4-container.png |
| `@pipeline-approval` | diagrams/pipeline-approval.png |
| `@persistence-scheduler` | diagrams/persistence-scheduler.png |
| `@learning-crossover` | diagrams/learning-crossover.png |
| `@notifications` | diagrams/notifications.png |
| `@wireframe-betsy-standalone` | diagrams/wireframe-betsy-standalone.png |
| `@wireframe-betsy-layer` | diagrams/wireframe-betsy-layer.png |
| `@gap-dashboard-empty-log` | decision_logs/images/gap-dashboard-empty-log.png |
| `@gap-supplier-scoreboard` | decision_logs/images/gap-supplier-scoreboard.png |

## Summary tokens — design docs / reports (upload the PDF)

| `@token` | File to upload |
|----------|----------------|
| `@gap-analysis` | pdf_exports/design/gap-analysis.pdf |
| `@pipeline-architecture` | pdf_exports/design/pipeline-architecture.pdf |
| `@orchestra-architecture` | pdf_exports/design/orchestra-architecture.pdf |
| `@api-control-layer` | pdf_exports/design/api-control-layer.pdf |
| `@user_requirements` | pdf_exports/docs/user_requirements.pdf |
| `@wireframes` | pdf_exports/docs/wireframes.pdf |
| `@test-report-dl05` | pdf_exports/docs/test-report-dl05.pdf |
| `@test-report-dl06` | pdf_exports/docs/test-report-dl06.pdf |

---

## Decision-log files (upload each as `[DL-0N]`)

`@[DL-01]` … `@[DL-08]` → the eight `decision_logs/[DL-0N] *.txt` files, plus
`DL-SUMMARY.txt`.

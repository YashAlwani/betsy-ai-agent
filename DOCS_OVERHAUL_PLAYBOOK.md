# Documentation Overhaul — Direction / Playbook

This is a **transferable direction**, not a literal changelog. It captures *how*
this project's design docs and decision logs were made accurate, readable, and
upload-friendly, so the same approach can be applied to a **different project
with a different structure**. Treat each item as a direction to adapt — file
names, folders, and components will differ; the principles and conventions do
not.

---

## The goal

Make a project's design documentation:
- **Accurate** — every doc matches what the code actually does (no drift,
  no invented files/classes).
- **Readable** — plain, simple, direct language; steady coherent paragraphs,
  not clever one-liners.
- **Portable** — deliverable on platforms that **cannot preview Markdown**.
- **Justified** — every capability traced back to a business "before vs after"
  (GAP) need.

---

## Core decisions (apply these anywhere)

1. **Ship `.txt` + PDF, keep `.md` as source.**
   Some upload/submission platforms can't render Markdown. So the *deliverable*
   is a plain-text `.txt` (readable raw) plus a **PDF with the diagrams embedded**.
   Keep an accurate `.md` version too as the GitHub/IDE-viewable source.

2. **Diagrams are separate files, not inline.**
   Author each diagram as its own **Mermaid `.mmd`** file in a `diagrams/` folder.
   Render each to a **`.png`**. Embed the PNGs in the PDFs; reference them by path
   in the `.txt`. Plain text can't embed, so it points instead.

3. **Add a "point document".**
   One plain-text index in `diagrams/` (e.g. `00-INDEX.txt`) lists every diagram:
   what it shows, which document it belongs to, and the matching code file.

4. **Docs must match the code.**
   Before writing, read the real source. Fix drift: name the files/functions that
   actually exist, delete descriptions of things that don't. Doc/code mismatch is
   the worst transferability failure.

5. **Lead with the GAP (before vs after).**
   The business-process "as-is vs to-be" analysis is the *forefront* — the reason
   every feature exists. Decompose it into diagrams and reference the relevant one
   wherever a change is justified.

6. **Plain, direct language everywhere.**
   Short sentences, everyday words, explain a term once. No witty fragments —
   steady, coherent blocks. This applies to analysis/planning docs too.

---

## Target shape (rename folders to suit the project)

```
diagrams/
  00-INDEX.txt            plain-text "point document" describing every diagram
  <name>.mmd              one Mermaid source per diagram
  <name>.png              rendered image (built, embedded, referenced)
docs/
  <component>.txt         plain-English deliverable (references diagrams + code)
  <COMPONENT>.md          accurate technical source (inline mermaid ok for GitHub)
pdf_exports/design/
  <component>.pdf         built from the .txt with diagrams embedded
build_design_docs.py      renders .mmd -> .png and builds the .txt -> PDF
```

---

## Toolchain (direction)

- **Render Mermaid -> PNG, high-res:** `npx -y @mermaid-js/mermaid-cli -i x.mmd
  -o x.png -b white -s 3 -w 1600` (needs Node; first run fetches the CLI + a
  headless browser). The `-s 3` (3x scale) is what makes diagrams stay sharp when
  a reader zooms a PDF — default scale looks blurry. Use a wider `-w` for wide
  diagrams (e.g. a C4 container view: `-w 2000`).
  - **Stale-render gotcha:** a build that "renders if PNG missing or older than
    the .mmd" will *skip* unchanged diagrams. After changing render settings,
    delete the stale `.png`s to force a re-render.
- **Wireframes -> PNG (proper wireframes, not ASCII):** author in **wiremd**
  (`npm install -g wiremd`), render with `--style wireframe`. wiremd only emits
  HTML, so screenshot it to PNG with headless Edge/Chrome
  (`msedge --headless=new --screenshot=out.png --window-size=W,H
  --force-device-scale-factor=2 in.html`) and **auto-crop** the fixed-window
  whitespace with Pillow. Wrap the three steps in a small `build_wireframes.py`.
  wiremd syntax cheat: input `[____]{type:search}`, primary button `[Label]*`,
  grid `## Title {.grid-N}` with `###` items, GFM tables, blockquote = AI
  summary. (WireScript is a *different* tool with native PNG but its own syntax.)
- **Build PDFs:** a small script (reportlab works well) that:
  1. renders any `.mmd` whose `.png` is missing/stale, then
  2. turns each `.txt` into a PDF, embedding `diagrams/<name>.png` wherever the
     text contains a marker line like `See the picture: diagrams/<name>.mmd`.
- Note: generic Markdown->PDF converters usually **can't** render Mermaid, embed
  images, or lay out tables well. Pre-render PNGs and embed them instead.

---

## `.txt` design-doc shape (reusable template)

```
==== TITLE ====
WHAT THIS IS            plain one-paragraph framing
THE PARTS/STEPS         each part in plain words
HOW <X> WORKS           the tricky bits, restated simply
IF SOMETHING BREAKS     failure behaviour in plain words
WHY IT'S BUILT THIS WAY link the GAP (before/after) justification
WHERE THIS LIVES IN THE CODE   bullet list of real files + one-line roles
DIAGRAMS FOR THIS DOCUMENT     list the diagrams/*.mmd used
```
Put a `See the picture: diagrams/<name>.mmd` line where each diagram belongs;
the build script embeds the PNG there.

---

## Diagram conventions

- **Flows / swimlanes:** Mermaid `flowchart`. Use **top-to-bottom (`TB`)** for
  swimlanes so they stay legible in a portrait PDF (left-to-right gets too wide).
  Use `subgraph` per actor/lane; dotted arrows for cross-lane hand-offs.
- **C4:** Mermaid's native `C4Container` layout is messy. Instead draw a
  **flowchart styled with C4 colours** (person = dark blue, container = mid blue,
  external = grey) inside a `subgraph` system boundary. You keep the C4 *model*
  with clean layout.
- **Sequences:** use `sequenceDiagram` for request/response round-trips (e.g. an
  approval flow).
- **Lifecycles / state machines:** use `stateDiagram-v2` for one entity moving through
  its states (e.g. a decision/order: detected → evaluated → decided → auto-approved or
  held → created → in-transit → delivered → score-updated). Pull the real state strings
  from the code (status fields, branch conditions) so the diagram matches behaviour;
  mark the key business gate (e.g. the `$5,000` auto-approve limit) as the branch.

---

## Decision-log direction

- **Keep the existing structure/scaffold** (section headings, required fields).
  Do not restructure a graded/required format — only rewrite the prose.
- **Rewrite prose plain and direct**, in coherent steady blocks. No witty
  fragments, no symbol soup. Replace status emoji (✅ 🟡 ✦) with plain words.
- **Use this pattern** for justification paragraphs:
  *"[File] does this. According to [analysis/design doc] this is why. This led to
  [outcome / the next gap]."*
- **Drop advisory tangents** ("if I were advising…") unless explicitly required.
- **Tie each log back to the GAP.** Weave one sentence into each log linking the
  decision to the before/after (e.g. "this is the escalation gateway in the
  TO-BE process"), referencing the GAP source by name.
- **Give each log a diagram.** If a log has none, author one (`.mmd`) for it and
  reference it; render it high-res like the rest.

### Reference conventions (these decide whether a log survives upload)

The upload platform **links uploaded evidences by an `@name` typed in free text.** So
the one hard requirement is that every `@token` matches the name its evidence is uploaded
under. Everything below follows from that.

- **Everything is a bare `@token` — body AND footer.** Strip path and extension:
  `server/state.py` → `@state`, `pipeline/nodes/decide.py` → `@decide`,
  `diagrams/learning-crossover.png` → `@learning-crossover`,
  `analysis/case_summary.md` → `@case_summary` (it uploads as a PDF; the token is what
  links it). The `Files:` / `Diagrams:` / `Source:` footer lines are token lists too —
  **no path survives anywhere a `@` appears**, and `.md`/`.html` design docs may be inline
  tokens now (they link to their uploaded PDF/HTML, not to raw markdown).
- **Resolve every collision 1:1.** A `@name` links to exactly one evidence, so two
  different files cannot share a token — do NOT rely on context to disambiguate, the
  platform can't. Keep the most-referenced file on the bare name and qualify the rest:
  `@state` (server) vs `@pipeline-state` / `@orchestra-state`; `@pipeline-graph` /
  `@orchestra-graph`; `@suppliers` (data) vs `@suppliers-router`; `@notifications`
  (diagram) vs `@notifications-router`.
- **Foreground design, keep code in the footer, bridge with a footnote.** Where the prose
  should point at a design doc but the code still matters, point straight at the design
  with a superscript number (`¹@api-control-layer`) and put the code file in the footer
  under the same number (`¹@main`). Design leads the sentence; code is one hop away. Don't
  write "described in the X design" prose — the token *is* the pointer.
- **Keep an evidence manifest.** One file (`EVIDENCE-MANIFEST.md`) maps every `@token` →
  the real file to upload and the name to give it. Because the logs no longer carry paths,
  this manifest is the only token↔file lookup and doubles as the upload checklist.
- **Images: bracket callouts keep their path** — `[IMAGE: diagrams/name.png — caption]`.
  This is the one place a path survives, because the callout points a human at the actual
  picture. Point only at files that exist — audit for dead refs.
- **Filename format:** name each log `[DL-0N] <research question>.txt` so the summary can
  reference it as `[DL-0N]`. Rename with `git mv`.

### Collection summary direction

- Ship the summary as a **`.txt`** (same upload reasoning as the logs), with a
  short intro — **What is this? / Why / What was accomplished** — then a
  **sprint-story** built from `git log`: one section per sprint.
- Each sprint = **explanation first** in clean plain prose, with the design-doc/diagram
  `@token` **woven in beside any sentence that mentions that design** (in parentheses
  right before or after the sentence — minimal text change, the token *is* the link);
  then the pointer lines, then a **What it unlocked** line:
  - `Designs & reports:` — `@`-pointers to the **transferable evidence**: design
    docs, diagrams, and test/PDF reports by stripped name (`@gap-analysis`,
    `@learning-crossover`, `@test-report-dl05`). **Never point at code** — let the
    design docs/diagrams/reports surround it; name a code file only briefly if
    unavoidable.
  - `Decision logs:` — `@[DL-0N]` (matches the renamed log files).
- **Do not embed images** and **do not list commit hashes** in the summary — the
  `@`-pointers to docs/diagrams/reports are the references. Verify every one
  resolves to a real file.

---

## Packaging & delivery

Once the docs are accurate and plain, separate the repo into three buckets —
**never delete anything**, just sort.

- **`deletable/` — flat, git-ignored, local-only.** Move (don't copy) the unused
  and superseded files here: stray screenshots, scratch notes, build artifacts,
  duplicate "evidence" copies, planning docs, and any orphaned PDFs of the above.
  Add `deletable/` to `.gitignore`. Drop the moved docs from the PDF builder's
  file list so it doesn't try to rebuild them. Nothing is lost — the files just
  leave the tracked repo and sit locally.
- **`upload/` — committed deliverable bundle.** *Copy* (don't move) the
  submission set into a clean structure: `decision-logs/` (`.txt` + summary),
  `design-docs/` (`.txt` + their PDFs), `diagrams/` (the referenced `.png` +
  `00-INDEX.txt`), `reports/` (test-report PDFs), plus the GAP artifact and the
  README/plan PDFs. Regenerate all PDFs *before* copying so the bundle is current.
- **Everything else stays** — the actual code, the accurate `.md` sources, the
  diagram sources, the build scripts.

Then deliver with git: branch (`git checkout -b <name>` — **no spaces in branch
names**), `git add -A` (the `deletable/` ignore keeps it out, `upload/` goes in),
commit, push, and merge to the main branch. If the remote has diverged, **fetch
and merge — never force-push** a shared branch.

---

## Step-by-step, to apply to a new project

1. Read the real code; list the actual components and files. Record any doc/code
   drift to fix.
2. Find or create the GAP (before/after) artifact. Decompose it into diagrams.
3. For each architecture component: accurate source doc + plain `.txt` + diagrams
   + PDF.
4. Add a C4 container diagram and a system-overview diagram (put one in the
   README).
5. Stand up the `diagrams/` folder, the `00-INDEX.txt` point document, and the
   build script. Render diagrams high-res (`-s 3`).
6. Rebuild the wireframes as proper wiremd wireframes (not ASCII).
7. Rewrite the decision logs with the conventions above (bare `@` refs, GAP ties,
   per-log diagram, `[DL-0N]` filenames), then the collection summary as a `.txt`.
8. Rewrite test reports plain (keep the evidence tables/formulas).
9. Simplify the language across analysis/planning docs only where they are
   genuinely old-style — leave already-plain and intentionally-technical `.md`
   sources alone.
10. Regenerate all PDFs, then package into `deletable/` + `upload/`.
11. Branch, commit, push, merge.

---

## Pitfalls learned here

- Upload platform couldn't preview Markdown -> the move to `.txt` + PDF.
- The repo's existing `md -> pdf` script ignored Mermaid, images, and tables ->
  built a dedicated diagram-aware PDF builder.
- Native Mermaid C4 rendered as an unreadable single column -> flowchart-as-C4.
- A wide left-to-right swimlane shrank to nothing in a portrait PDF -> reoriented
  top-to-bottom.
- The architecture docs described an older design (files/classes that no longer
  existed) -> always re-derive docs from the current code.
- The generic `md -> pdf` converter rendered `✅`/`✦` as a `?` glyph (outside its
  font) and laid tables out as monospace blocks -> for **test reports**, keep the
  results table and any formula as evidence but rewrite the prose plain, swap
  `✅ -> pass`, and trim raw JSON to a short plain note. Plain prose, evidence kept.
- A locked PDF (open in a viewer) blocks overwrite on Windows -> build to a
  `*.new.pdf`, verify, then swap once the viewer is closed.
```

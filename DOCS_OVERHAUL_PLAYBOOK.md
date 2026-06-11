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

- **Inline file references: strip the extension and the path — bare name only.**
  `@server/state.py` → `@state`, `@pipeline/nodes/decide.py` → `@decide`. Upload
  platforms linkify `@file.ext` in free text; a bare `@name` does not trip that.
  Let surrounding context disambiguate collisions (e.g. two `@graph` files).
- **No `.md` files in the body text.** Architecture/test-report markdown belongs
  only in the footer `Source:` line, never as an inline `@` token in prose.
- **Footer is plain lines, not `@` tokens:** `Files:` (real paths + extensions,
  comma-separated) · `Diagrams:` (diagrams/<name>.png) · `Source:` (GAP html +
  any .md) · `LO stages:`. Footer lists keep extensions — they are safe there.
- **Images: bracket callouts `[IMAGE: path/name.png — caption]`** (brackets are
  upload-safe). Point only at files that actually exist — audit for dead refs
  (old logs often cite screenshots that were never committed).
- **Filename format:** name each log `[DL-0N] <research question>.txt` so the
  collection summary can reference it as `[DL-0N]`. Rename with `git mv`.

### Collection summary direction

- Make the summary a **sprint-story narrative artifact** built from `git log`:
  one section per sprint, each with a plain-language story, **Key commits**
  (verified hashes), the **Decision logs** it produced (referenced by stripped
  filename, e.g. `[DL-02] Should I use a pipeline…`), the **Diagrams** (stripped
  names), and a **What it unlocked** line.
- In the summary, **do not embed images** — just refer to the stripped filename
  (`gap-as-is`, `learning-crossover`). Verify every reference resolves.

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
   build script.
6. Rewrite the decision logs with the pattern above, keeping their structure.
7. Simplify the language across analysis/planning docs.
8. Checkpoint (commit) at logical milestones.

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

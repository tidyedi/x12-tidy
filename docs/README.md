# x12-tidy docs

| Document | What it is |
| --- | --- |
| **[Finding the Elusive ISA Line](https://ubeast.github.io/x12-tidy/finding-the-isa-line.html)** | Engineering note on Step 1 — why fixed offsets and a regex both fail, and the techniques that replace them. Rendered by GitHub Pages; [Markdown source](finding-the-isa-line.md) renders here on GitHub too. |
| [design.md](design.md) | The *why* behind the architecture and the diagnostic-code scheme — decisions that span modules. |
| [diagnostics.md](diagnostics.md) | Every diagnostic code the linter can emit. **Generated** from `src/x12_tidy/diagnostics/codes.py` — do not edit by hand. |

`figures/` holds the SVG figures for the ISA-line note. `finding-the-isa-line.html`
is the page GitHub Pages serves — opening it from the repo file tree only shows
its source, because GitHub does not render HTML there; use the Pages link above.

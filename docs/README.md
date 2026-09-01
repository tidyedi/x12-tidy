# x12-tidy docs

| Document | What it is |
| --- | --- |
| **[The x12-tidy Method](the-x12-tidy-method.md)** | The one idea the step notes hang off — earn the four delimiters from structure first, then everything downstream is ordinary parsing plus repair. Read this first. |
| **[Finding the Elusive ISA Line](https://docs.tidyedi.com/finding-the-elusive-isa-line.html)** | Engineering note on Step 1 — why fixed offsets and a regex both fail at *locating* the ISA line, and the techniques that replace them. [Markdown source](finding-the-elusive-isa-line.md) · [PDF](https://docs.tidyedi.com/finding-the-elusive-isa-line.pdf). |
| **[Those Pesky Delimiters](https://docs.tidyedi.com/those-pesky-delimiters.html)** | Engineering note on Step 2, slice 1 — reading the four X12 delimiters out of that run when the byte offsets the standard uses have all moved. [Markdown source](those-pesky-delimiters.md) · [PDF](https://docs.tidyedi.com/those-pesky-delimiters.pdf). |
| **[Reconstructing the ISA Line](reconstructing-the-isa-line.md)** | Engineering note on Step 2, slice 2 — once the delimiters are trusted, rebuilding the canonical 105-byte line, and why that is a total function. |
| [design.md](design.md) | The *why* behind the architecture and the diagnostic-code scheme — decisions that span modules. |
| [diagnostics.md](diagnostics.md) | Every diagnostic code x12-tidy can emit. **Generated** from `src/x12_tidy/diagnostics/codes.py` — do not edit by hand. |

This folder is served at **[docs.tidyedi.com](https://docs.tidyedi.com)** by
GitHub Pages; [`index.html`](index.html) is the landing page. `figures/` holds
the SVG figures for the engineering notes. Opening a `.html` from the repo file
tree only shows its source — GitHub does not render HTML there; use the links
above.

# x12-tidy docs

| Document | What it is |
| --- | --- |
| **[The x12-tidy Method](https://docs.tidyedi.com/the-x12-tidy-method.html)** | The one idea the notes hang off — earn the four delimiters from structure first, then everything downstream is ordinary parsing plus repair. Read this first. [Markdown source](the-x12-tidy-method.md) · [PDF](https://docs.tidyedi.com/the-x12-tidy-method.pdf). |
| **[Finding the Elusive ISA Line](https://docs.tidyedi.com/finding-the-elusive-isa-line.html)** | Why fixed offsets and a regex both fail at *locating* the ISA line, and the techniques that replace them. [Markdown source](finding-the-elusive-isa-line.md) · [PDF](https://docs.tidyedi.com/finding-the-elusive-isa-line.pdf). |
| **[Those Pesky Delimiters](https://docs.tidyedi.com/those-pesky-delimiters.html)** | Reading the four X12 delimiters out of that run when the byte offsets the standard uses have all moved. [Markdown source](those-pesky-delimiters.md) · [PDF](https://docs.tidyedi.com/those-pesky-delimiters.pdf). |
| **[Reconstructing the ISA Line](https://docs.tidyedi.com/reconstructing-the-isa-line.html)** | Once the delimiters are trusted, rebuilding the canonical 105-byte line — and why that is a total function. [Markdown source](reconstructing-the-isa-line.md) · [PDF](https://docs.tidyedi.com/reconstructing-the-isa-line.pdf). |
| [design.md](design.md) | The *why* behind the architecture and the diagnostic-code scheme — decisions that span modules. |
| [diagnostics.md](diagnostics.md) | Every diagnostic code x12-tidy can emit. **Generated** from `src/x12_tidy/diagnostics/codes.py` — do not edit by hand. |
| [links.md](links.md) | External EDI references — the X12 standard, code-list lookups, community resource lists. |

This folder is served at **[docs.tidyedi.com](https://docs.tidyedi.com)** by
GitHub Pages; [`index.html`](index.html) is the landing page. `images/figures/` holds
the SVG figures for the engineering notes. Opening a `.html` from the repo file
tree only shows its source — GitHub does not render HTML there; use the links
above.

# x12-tidy docs

| Document | What it is |
| --- | --- |
| **[Finding the Elusive ISA Line](https://docs.tidyedi.com/finding-the-elusive-isa-line.html)** | Engineering note on Step 1 — why fixed offsets and a regex both fail at *locating* the ISA line, and the techniques that replace them. [Markdown source](finding-the-elusive-isa-line.md) · [PDF](https://docs.tidyedi.com/finding-the-elusive-isa-line.pdf). |
| **[Those Pesky Delimiters](https://docs.tidyedi.com/those-pesky-delimiters.html)** | Engineering note on Step 2 — reading the four X12 delimiters out of that run when the byte offsets the standard uses have all moved. [Markdown source](those-pesky-delimiters.md) · [PDF](https://docs.tidyedi.com/those-pesky-delimiters.pdf). |
| [design.md](design.md) | The *why* behind the architecture and the diagnostic-code scheme — decisions that span modules. |
| [diagnostics.md](diagnostics.md) | Every diagnostic code x12-tidy can emit. **Generated** from `src/x12_tidy/diagnostics/codes.py` — do not edit by hand. |

`figures/` holds the SVG figures for both engineering notes. The `.html` files
are the pages GitHub Pages serves — opening one from the repo file tree only
shows its source, because GitHub does not render HTML there; use the Pages links
above.

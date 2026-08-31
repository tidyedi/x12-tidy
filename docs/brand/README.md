# TidyEDI brand assets

The mark is **"Tidied rows"**: a Pine tile with four Cream bars. The top bar
overhangs a clean left edge and sits faint — the non-conformant segment the
parser found; the three below are flush and solid — the same data, tidied.

| File | Use |
| --- | --- |
| `tidyedi-mark.svg` | Primary mark. Source of truth. Self-contained, does not theme. |
| `tidyedi-mark.png` | 512×512 raster of the primary mark (transparent corners). GitHub org avatar, README, anywhere PNG is required. |
| `tidyedi-mark-mono.svg` | Single-ink outline build for embroidery / engraving / one-colour print. Set `color` to ink it. |
| `../favicon.svg` | Favicon build — 3 heavier bars so the idea survives at 16px. Served at the site root. |
| `../favicon-96.png` `../favicon-32.png` `../favicon-16.png` | PNG favicon fallbacks. |
| `../apple-touch-icon.png` | 180×180 for iOS home-screen. |
| `social-card-1280x640.png` | Repo social preview and page `og:image`. |
| `tidyedi-avatar-512.png` | Same bytes as `tidyedi-mark.png`, named for the GitHub org-avatar upload. |

## Colour

| Token | Hex | Where |
| --- | --- | --- |
| Pine | `#1F6B4D` | tile; `EDI` in the wordmark |
| Cream | `#F3F8F5` | bars |
| Rust | `#B3612C` | **not in the logo** — reserved for deviation findings |

The logo uses only Pine and Cream and never themes — one artwork on every
background.

## Wordmark

"Tidy" + "EDI" set in **IBM Plex Serif SemiBold**, `EDI` in Pine. Mark height =
cap height of the wordmark; gap between them = one bar-pitch of the mark. The
`x12-tidy` CLI keeps a plain IBM Plex Mono wordmark with no mark.

## Geometry (64×64 grid)

Tile radius 14. Bars: height 5.4, radius 2.7, vertical pitch 11, first bar
centred at y ≈ 17.7. The three solid bars run x 18→46 (width 28). The top bar
runs x 11→46 (width 35 — a 7-unit overhang) at opacity 0.34.

**Never** re-space the bars, add a fifth, tint them, or straighten the top one.
The asymmetry is the mark.

Full spec with lockups, clear space, and misuse: see the identity artifact
linked from the project notes.

## Regenerating the PNGs

No rasteriser is committed. To rebuild from the SVGs (headless Chrome):

```bash
chrome --headless=new --disable-gpu --hide-scrollbars \
  --default-background-color=00000000 --window-size=512,512 \
  --screenshot=tidyedi-mark.png \
  'data:text/html,<img src="tidyedi-mark.svg" style="width:512px;height:512px">'
```

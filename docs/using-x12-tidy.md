# Using x12-tidy

A developer guide to the command-line tool and the Python library. For *how it
works*, see the [engineering notes](https://docs.tidyedi.com) and
[`design.md`](design.md); for *every diagnostic code*, see
[`diagnostics.md`](diagnostics.md).

x12-tidy takes a byte-for-byte X12 interchange — however malformed — and gives
you back two things:

1. a **cleansed, conformant copy** of the interchange (when one can be
   recovered at all), and
2. a **complete list of every deviation** it found from the X12 standard, each
   as a `Diagnostic` (a code, a plain-English message, and a byte offset).

It parses permissively and reports strictly: it will not bail on the first
problem, and it never silently repairs anything without emitting a diagnostic
for it.

---

## Install

There is no PyPI release yet. Work from the repository:

```bash
git clone https://github.com/tidyedi/x12-tidy && cd x12-tidy
uv sync                       # library + the `x12-tidy` CLI, no runtime deps
uv run x12-tidy --help
```

`uv pip install .` puts `x12-tidy` on your `PATH`. Python ≥ 3.11.

---

## The command line

Three subcommands: `check`, `codes`, `explain`.

### `x12-tidy check <file>`

Runs the whole pipeline against a file and prints a report.

```
$ x12-tidy check clean.edi
delimiters: element=b'*' repetition=None component=b':' terminator=b'~'
payload (224 bytes): b'ISA*00*          *00* ... IEA*1*000000042~'
envelope: sender=b'ZZ'/b'ACME           ' receiver=b'ZZ'/b'WIDGETCO       ' usage=b'P' groups=1 transaction_sets=1 segments=6
was_clean: yes
```

```
$ x12-tidy check broken.edi
[ERROR isa.element-width] ISA02 is 2 byte(s); padded with spaces to its fixed width of 10.
[ERROR isa.element-width] ISA06 is 4 byte(s); padded with spaces to its fixed width of 15.
[FATAL structure.functional-group-count-mismatch] IEA01 is b'9' but 1 functional group(s) were found.
[WARNING isa.leading-bytes] 23 byte(s) precede the ISA segment (b'Subject: your order\r\n\r\n'); stripped before parsing.
delimiters: element=b'*' repetition=None component=b':' terminator=b'~'
payload (224 bytes): b'ISA*00*          *00* ... IEA*9*000000042~'
envelope: sender=b'ZZ'/b'ACME           ' receiver=b'ZZ'/b'WIDGETCO       ' usage=b'P' groups=1 transaction_sets=1 segments=6
```

The output, in order:

| line | when it appears |
| --- | --- |
| one `[SEVERITY code] message` line per finding | for every finding; **warnings go to stdout, errors and fatals to stderr** |
| `delimiters:` — the four recovered delimiters | whenever the ISA line could be decomposed |
| `payload (N bytes):` — the cleansed interchange as a `bytes` repr | only when a payload was produced |
| `envelope:` — sender, receiver, usage, counts | only when QA/QC produced facts |
| `was_clean: yes` | only when there were zero findings |

Splitting the streams lets you keep just the problems:

```bash
x12-tidy check file.edi 2> problems.txt   # errors + fatals to the file, warnings to the terminal
```

**Exit codes:** `0` clean (or warnings only) · `1` at least one error or fatal
· `2` usage or I/O problem (file unreadable, bad arguments).

This is the only built-in format. It is deliberately terse and
developer-facing — `bytes` reprs, no colour, no summary counts. For anything
else, use the library and format the results yourself
([below](#formatting-your-own-report)).

### `x12-tidy codes [--area <area>]`

Lists every diagnostic code with its default severity and one-line title — the
full severity matrix.

```
$ x12-tidy codes --area isa
isa.component-separator-invalid error    The component separator is not a usable delimiter
isa.delimiter-collision      fatal    Two delimiters are the same byte
isa.element-width            error    An ISA element is not its fixed width
isa.leading-bytes            warning  Bytes precede the ISA segment
...
```

Areas with codes today: `isa`, `gs`, `st`, `structure`. Same content as
[`diagnostics.md`](diagnostics.md), which is generated from the registry and
kept in sync by CI.

### `x12-tidy explain <code>`

The full write-up for one code.

```
$ x12-tidy explain isa.element-width
isa.element-width  (error)
  An ISA element is not its fixed width

  Every ISA element has a fixed width -- ISA06 is 15 bytes, ISA13 is 9 ...
  This is an error, not a warning: the ISA line is no longer 105 bytes, and
  conventional VAN services and fixed-offset parsers cannot read the
  interchange at all until it is repaired.
```

---

## The library — one call

```python
from x12_tidy.envelope.tidy import tidy

result = tidy(dirty)          # dirty: bytes  ->  TidyResult
```

> The import stutters (`x12_tidy.envelope.tidy` the module, `tidy` the function) because
> `x12_tidy/__init__.py` does not re-export yet. `from x12_tidy import tidy`
> currently gives you the *module*; call `tidy.tidy(dirty)` in that case.

`tidy` runs `clean_payload` then `check_payload` and merges the findings
(cleanse findings first).

### `TidyResult`

| attribute | type | meaning |
| --- | --- | --- |
| `payload` | `bytes \| None` | the cleansed, conformant interchange. `None` **only** when the file could not be cleansed at all (no recoverable ISA line). |
| `facts` | `EnvelopeFacts \| None` | plain facts about the interchange. `None` exactly when `payload` is `None`. |
| `diagnostics` | `list[Diagnostic]` | every finding from both phases, cleanse first. |
| `was_clean` | `bool` (property) | `True` iff `diagnostics` is empty. |

### `EnvelopeFacts`

Plain values pulled from the envelope — **not** diagnostics. All the `bytes`
fields are the raw element values (space-padded as they appear in the ISA/GS).

```
sender_qualifier      bytes        ISA05
sender_id             bytes        ISA06   (15 bytes, space-padded)
receiver_qualifier    bytes        ISA07
receiver_id           bytes        ISA08
interchange_date      bytes        ISA09
interchange_time      bytes        ISA10
interchange_version   bytes        ISA12
usage_indicator       bytes        ISA15   (b'P' production, b'T' test)
group_versions        tuple[bytes] one GS08 per functional group
functional_group_count int         GS/GE pairs actually seen
transaction_set_count  int         ST/SE pairs actually seen
segment_count          int         segments in the payload
```

### `Diagnostic`

```python
@dataclass(frozen=True)
class Diagnostic:
    code: Code            # the stable identity of this kind of finding
    message: str          # plain English, specific to this occurrence
    offset: int | None    # byte position into the ORIGINAL dirty input, or None
```

`Diagnostic` carries **no severity**. Severity is resolved when you report,
from the code:

```python
from x12_tidy.diagnostics import resolved_severity, meta

resolved_severity(diag.code)     # 'fatal' | 'error' | 'warning'
diag.code.value                  # 'isa.element-width'   (the stable string)
diag.code.area                   # 'isa'
meta(diag.code).title            # short one-liner
meta(diag.code).explanation      # the full paragraph `explain` prints
meta(diag.code).default_severity # same as resolved_severity today
meta(diag.code).deprecated       # bool
```

### A full example

```python
from pathlib import Path
from x12_tidy.envelope.tidy import tidy
from x12_tidy.diagnostics import resolved_severity

result = tidy(Path("broken.edi").read_bytes())

print("clean :", result.was_clean)                       # False
print("sender:", result.facts.sender_id.strip().decode())  # ACME
print("counts:", result.facts.functional_group_count,
      result.facts.transaction_set_count,
      result.facts.segment_count)                          # 1 1 6

for d in result.diagnostics:
    sev = resolved_severity(d.code)
    where = "" if d.offset is None else f" @byte {d.offset}"
    print(f"[{sev}] {d.code.value}{where}: {d.message}")

if result.payload is not None:
    hand_off_to_parser(result.payload)
```

### The refusal contract

A terminal input is a clean "no", not an exception:

```python
bad = tidy(b"this is not an EDI file at all")
bad.payload         # None
bad.facts           # None
[d.code.value for d in bad.diagnostics]   # ['isa.no-identifier']
```

`tidy` never raises on malformed content. It only raises on genuine misuse
(e.g. passing `str` instead of `bytes`).

---

## The library — building blocks

Use these when you want one phase, not the whole pipeline. Each returns a
result object that accumulates the diagnostics of every prior stage.

```
dirty bytes
    │
    ├─ extract_isa_line ──────► IsaLineResult      locate ISA … just before GS
    │       │
    │       ▼
    ├─ split_isa_line ────────► IsaDecomposition   recover the 4 delimiters, split into 16 elements
    │       │
    │       ▼
    ├─ reconstruct_isa_line ──► ReconstructedIsaLine  pad/trim to the canonical 105 bytes
    │
    │   clean_isa_line(dirty)  = the three above, chained
    │
    ├─ clean_payload ─────────► ReconstructedPayload  clean ISA line + clean body, rejoined
    │       │
    │       ▼
    └─ check_payload ─────────► QaQcResult           envelope / control-number / count audit
```

### ISA line only

```python
from x12_tidy.envelope.isa import (
    extract_isa_line,      # -> IsaLineResult
    split_isa_line,        # -> IsaDecomposition
    reconstruct_isa_line,  # -> ReconstructedIsaLine
    clean_isa_line,        # -> ReconstructedIsaLine  (the three, chained; usual entry point)
)

r = clean_isa_line(b"garbage\r\nISA*00* ... ~GS*PO* ... ~")
r.isa_line              # bytes, exactly 105 long, or None
r.elements              # tuple[bytes, ...] — the 16 ISA elements
r.decomposition         # IsaDecomposition | None
r.segment_terminator    # the sender's terminator byte (preserved, not normalised)
r.diagnostics           # list[Diagnostic]
r.was_clean             # bool (property)
```

`IsaLineResult`: `isa_line: bytes | None`, `isa_start: int`, `diagnostics`,
`found` (property).

`IsaDecomposition`: `element_separator`, `repetition_separator: bytes | None`,
`component_separator`, `segment_terminator`, `trailing`, `elements`,
`diagnostics`, `usable` (property — `True` when no fatal).

### Whole payload

```python
from x12_tidy.envelope.structure import clean_payload    # -> ReconstructedPayload

p = clean_payload(dirty)
p.payload        # bytes | None  (None on refusal, same condition as clean_isa_line)
p.isa_result     # the ReconstructedIsaLine it was built from
p.segments       # tuple[bytes, ...] — cleaned body, empty pieces dropped, in order
p.diagnostics    # ISA-phase diagnostics (the split/drop steps emit none)
p.was_clean      # bool (property)
```

`clean_payload` is **assembly only** — it does not repair a body segment, check
that a identifier is real, or validate envelope consistency. That is QA/QC.

There are also two purely mechanical helpers in `x12_tidy.envelope.structure`,
`split_segments` and `drop_empty_segments` — no diagnostics, no validation, no
refusal — plus `split_elements`.

### Envelope QA/QC

```python
from x12_tidy.envelope.qaqc import check_payload     # -> QaQcResult

q = check_payload(p)          # p: ReconstructedPayload
q.facts          # EnvelopeFacts | None
q.diagnostics    # every QA/QC finding — always the complete list
q.was_clean      # bool (property)
```

One pass over the payload's segments covers: `ISA`/`IEA`, `GS`/`GE`, `ST`/`SE`
pairing and nesting; control-number agreement and uniqueness;
segment / transaction-set / group counts; the identifier-shape gate; `ISA12`/`GS08`
version agreement; `ISA15` and `GS07` validity; and foreign content (a segment
with no structurally valid place to be).

Deliberately **not** checked anywhere yet: multiple interchanges in one file,
`ISA05`/`ISA07` qualifiers, `ISA14`, `GS01`, `ST01` shape, date/time formats,
`TA1`, `BIN`/`BDS`. See [`design.md`](design.md).

---

## The severity model

Every code resolves to one of three severities:

| severity | meaning |
| --- | --- |
| **fatal** | In the **ISA-reconstruction phase**: parsing stopped; there is no payload. In **QA/QC**: the payload exists and every check still ran, but its own bookkeeping is not trustworthy — *don't feed it downstream*. |
| **error** | The interchange is non-conformant (its bytes are wrong), but it was recovered and is usable after repair. Advisory — does not stop anything. |
| **warning** | A deviation was tolerated and repaired; nothing about the data changed. Advisory. |

Two things follow from this:

- **`fatal` means different things in the two phases.** ISA-phase `fatal` is a
  stop signal. QA/QC `fatal` is a trust signal — nothing in QA/QC ever aborts
  the walk.
- **Severity is never stored on a `Diagnostic`.** It is resolved at report time
  by `resolved_severity(code)`, from the registry default (and, in a future
  version, a user-config override). A config loaded *after* parsing still
  applies.

To see the whole matrix: `x12-tidy codes`, or [`diagnostics.md`](diagnostics.md),
or in code:

```python
from x12_tidy.diagnostics import all_codes, resolved_severity, meta

for code in all_codes():
    print(resolved_severity(code), code.value, "-", meta(code).title)
```

Today: 31 fatal, 10 error, 6 warning.

---

## Formatting your own report

The library returns **data, not text**. The CLI's `check` output is just one
consumer of that data — you are not bound to it. From a `TidyResult` you have,
per finding: severity, code string, area, short title, full explanation, the
human message, and a byte offset; plus every `EnvelopeFacts` field and the
payload. Render whatever subset you want, in whatever format.

### Markdown, grouped by severity, payload omitted

```python
from x12_tidy.diagnostics import resolved_severity, meta

def to_markdown(result, *, show_payload=False):
    out = ["# EDI validation report", ""]
    out.append(f"**{result.facts.sender_id.strip().decode()} → "
               f"{result.facts.receiver_id.strip().decode()}** — "
               f"{'clean' if result.was_clean else 'needed repair'}")
    for sev in ("fatal", "error", "warning"):
        ds = [d for d in result.diagnostics if resolved_severity(d.code) == sev]
        if not ds:
            continue
        out += ["", f"## {sev.title()} ({len(ds)})", ""]
        for d in ds:
            loc = "" if d.offset is None else f" _(byte {d.offset})_"
            out.append(f"- **`{d.code.value}`**{loc} — {meta(d.code).title}  ")
            out.append(f"  {d.message}")
    if show_payload and result.payload is not None:
        out += ["", "## Cleansed payload", "```", result.payload.decode("latin-1"), "```"]
    return "\n".join(out)
```

### HTML table, findings only

```python
def to_html(result):
    rows = "".join(
        f'<tr class="{resolved_severity(d.code)}">'
        f'<td>{resolved_severity(d.code).upper()}</td>'
        f'<td><code>{d.code.value}</code></td><td>{d.message}</td></tr>'
        for d in result.diagnostics
    )
    return f"<h1>EDI validation report</h1>\n<table>{rows}</table>"
```

### JSON

There is **no built-in serializer** (`to_json` / `as_dict`) yet — build the
dict yourself:

```python
import json

payload = {
    "clean": result.was_clean,
    "sender": result.facts.sender_id.strip().decode(),
    "findings": [
        {
            "severity": resolved_severity(d.code),
            "code": d.code.value,
            "area": d.code.area,
            "message": d.message,
            "offset": d.offset,
        }
        for d in result.diagnostics
    ],
}
print(json.dumps(payload, indent=2))
```

### Leaving things out

Every field is optional to render. Skip `result.payload`, skip the facts block,
drop the warnings, hide the byte offsets — you are iterating a list and reading
attributes, so omit whatever you don't want. The HTML example above shows no
payload and no facts; the Markdown one hides the payload unless asked.

---

## Conventions and gotchas

- **Everything is `bytes`, never `str`.** Inputs, outputs, element values,
  delimiters. Decode at your edges (`.decode("latin-1")` is safe for a
  reconstructed payload).
- **Every function is pure.** No global state, no I/O, no logging. `tidy` reads
  nothing and writes nothing; you hand it bytes.
- **`offset` is into the original input** you passed, before any junk was
  stripped — so it points at the real byte in the file the user gave you.
- **The delimiters are the sender's choice.** Reconstruction preserves them,
  including a non-`~` segment terminator; it only fixes bytes that cannot be a
  legal delimiter.
- **A clean refusal is a success.** A terminal input handled with `payload =
  None` plus a `fatal` diagnostic saying why is the correct outcome, not a gap.

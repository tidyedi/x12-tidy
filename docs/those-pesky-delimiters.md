<a href="https://tidyedi.com"><img src="brand/tidyedi-mark.png" alt="TidyEDI" width="52" height="52" align="left" hspace="12"></a>

# Those Pesky Delimiters

*An engineering note on Step 2 of x12-tidy: reading the four X12 delimiters out
of an ISA line that no longer sits where the standard says it should.*

> **Read this as a web page:** <https://docs.tidyedi.com/those-pesky-delimiters.html>
> (served by GitHub Pages from [`docs/those-pesky-delimiters.html`](those-pesky-delimiters.html);
> clicking the `.html` file in the repo tree only shows its source — GitHub never
> renders HTML there). This Markdown file is the version of record — keep it, the
> HTML, and the figures under `docs/figures/` in sync with
> `src/x12_tidy/isa/delimiters.py`.

The companion note, [Finding the Elusive ISA Line](finding-the-elusive-isa-line.md),
ends with a run of bytes: `ISA` up to just before `GS`, holding exactly sixteen
element separators. That run has the *shape* of an ISA line. This note is about
the first thing you do with it — pull out the delimiters — and why that is
harder than reading three bytes at three fixed offsets.

> This is act two of [the x12-tidy method](the-x12-tidy-method.md). The four
> delimiters are the one thing the tool must be certain of; everything before
> this step exists to make this parse clean, and everything after treats its
> result as ground truth.

---

## 1. The ISA line is a delimiter declaration

An X12 interchange is a stack of envelopes — `ISA` wraps `GS` wraps `ST` — and
every segment, element, and sub-element inside them is separated by a punctuation
byte the sender chose. Those bytes are not fixed by the standard. They are
*declared*, once, by the ISA segment:

- the **element separator** sits at byte 3 — the fourth byte of `ISA…`;
- the **component separator** (between the parts of a composite element) is the
  value of `ISA16`, at byte 104;
- the **segment terminator** is at byte 105;
- and — for interchange version `00403` and later — the **repetition separator**
  (between repeated occurrences of one element) is the value of `ISA11`.

Four delimiters, not three. And the ISA segment is a bootstrapping trick: the
segment that tells you how to split every other segment is itself split by those
same bytes, so it has to be readable *positionally*, at fixed widths, before you
know anything.

![The four X12 delimiters. The standard places the element separator at byte 3,
ISA11 the repetition separator, the component separator at byte 104, and the
segment terminator at byte 105. In a file whose earlier elements were stripped,
every one of those byte positions has moved except byte 3.](figures/delimiters-four.svg)

That is exactly the problem [the first note](finding-the-elusive-isa-line.md)
describes, one layer down. The senders who strip empty ISA elements — turning the
fixed 105-byte segment into something shorter — move byte 104 and byte 105 along
with everything else. `data[104]` is no longer the component separator. `data[105]`
is no longer the terminator. You cannot read a delimiter at an offset the sender
slid out from under you.

---

## 2. The one you can still trust: the element separator

Byte 3 does not move. The tag `ISA` is exactly three bytes — it can't be
stripped, padded, or shifted, and it is the anchor Step 1 already used to find
the line. Whatever byte sits at index 3 of the run is the element separator, full
stop. It is the one fixed offset that survives, because it sits *before* the
first variable-width field.

From there, everything is a `split`:

```python
element_separator = run[3:4]
parts = run.split(element_separator)
```

Step 1 guarantees the run holds *exactly* sixteen element separators — that is
[its minimum bar](finding-the-elusive-isa-line.md) for calling a run an ISA line
at all — so the split always yields seventeen pieces:

![run.split(element_separator) produces seventeen pieces: the literal ISA, then
ISA01 through ISA15, and a seventeenth piece that is ISA16 followed by the
segment terminator and any trailing bytes before GS.](figures/delimiters-split.svg)

Everything after this is read from those pieces — never from byte 104, never from
byte 105. A sender who stripped `ISA02` and `ISA04` down to nothing pulled the
component separator eleven bytes to the left of where the standard puts it, but
it is still the first byte of the last piece, because the *count* of separators
and the position of `GS` did not move. This is the same move as Step 1:
**anchor on a structural invariant, never on a byte position the sender can
shift.**

There is one thing the element separator is checked for, and it is fatal: if it
is a letter or a digit, it cannot be told apart from the data inside elements, so
no segment in the whole interchange splits cleanly. Step 1 will have *located*
such a line — its job is permissive — but Step 2 refuses it.

---

## 3. The last piece: component separator and terminator

The last of the seventeen pieces is `ISA16`, then the segment terminator, then
whatever sits between the terminator and `GS` — the split runs straight past
ISA16 because nothing stops it.

`ISA16` is a strange field: **its value is a delimiter.** The component separator
is whatever single byte the sender put there. So this piece *begins* with `ISA16`
(the component separator); its next byte is the segment terminator.

That second byte — one byte, by rule, not by convenience. This is the rule that
earns its keep. Real files end segments with `~`, or `~\r\n`, or a bare `\r\n`,
or `~` then a stray space, or `\n` alone. If you treat "the terminator" as
*everything between ISA16 and GS*, you cannot tell a two-byte terminator from a
one-byte terminator followed by a newline the sender appended — and that
ambiguity then propagates to every segment in the file. The one-byte rule cuts
it:

![How the one-byte rule resolves each real-world terminator. The colon is ISA16.
For a tilde, the terminator is the tilde and there is no trailing. For tilde-CR-LF
the terminator is the tilde and CR-LF is trailing. For a bare CR-LF the terminator
is the CR and the LF is trailing. For tilde-space the terminator is the tilde and
the space is trailing.](figures/delimiters-terminator.svg)

The terminator is that one byte. Anything after it and before `GS` is *trailing*
— classified on its own: carriage returns and line feeds are a newline the
sender appended (a warning), anything else is junk (an error). Both are stripped
when the line is reconstructed.

Two things this last piece tells you are seriously wrong:

**The terminator was stripped.** The last piece is one byte long — just the
component separator, then `GS`. The sender dropped the terminator entirely. Its
position is known, so it is reconstructed as `~` and flagged; this is not fatal.

**The split landed on data.** The last piece's first byte — where `ISA16` should
be — is a letter or a digit. The component
separator is never alphanumeric, so the decomposition is wrong — almost always
because an element separator byte occurs *inside* `ISA06` or `ISA08` data, which
pulled every field after it out of alignment. The line has the right *number* of
separators — Step 1 counted them — but the wrong *boundaries*. That is terminal:
the diagnostic is emitted and parsing stops, because any repair from here is a
guess.

---

## 4. The fourth delimiter, and a version number three fields away

`ISA11` is the awkward one. Through interchange version `00402` it is the
"Interchange Control Standards Identifier," and its value is the single letter
`U`. From version `00403` (004030) onward the field was repurposed to hold the
**repetition separator**.

So whether the ISA line even *has* a fourth delimiter depends on `ISA12` — the
version code, two fields further along. You read `ISA11`'s role from `ISA12`:

| `ISA12` | what `ISA11` is |
| --- | --- |
| `00200` – `00402` | the standards identifier `U`; there is **no** repetition separator |
| `00403` and later (incl. `00501`, HIPAA `005010` where it is `^`) | the repetition separator |

Version `00402` does not have a repetition separator — a common misconception,
worth stating plainly.

And `ISA11` is never guessed at. If `ISA12` is an older version and `ISA11` holds
something other than `U`, that is a wrong value in an informational field — an
error, not a delimiter. x12-tidy does not decide the sender "meant" it as a
repetition separator, because on that version the field is not one. If `ISA12` is
not a recognizable five-digit version code at all, `ISA11` is left opaque.

---

## 5. When is a bad delimiter fatal?

Not "when it is non-conformant." A delimiter finding is fatal *at this step* only
if it blocks parsing the interchange outright.

| delimiter | needed by | an unusable value is |
| --- | --- | --- |
| element separator | every segment | **fatal** |
| segment terminator | every segment | **fatal** |
| component separator | composite elements only | an **error** — fatal at the first composite |
| repetition separator | repeated elements only | an **error** — fatal at the first repeat |

An alphanumeric element separator is fatal: nothing splits. An alphanumeric
*component* separator is only a problem if some segment carries a composite
element — and many interchanges carry none. So `split_isa_line` records it as an
error and hands the delimiters back. If the body parser later reaches a composite
it cannot split, *it* raises the fatal — at that segment, where the evidence is.
The repetition separator works the same way.

This is why `split_isa_line` returns a populated result with a severity-free
diagnostic list rather than a bare pass/fail: the finding's weight is settled
later, at report time, against what the rest of the file turns out to need.

---

## 6. Proving it: the delimiters don't move

The claim the whole approach rests on is that stripped and re-padded elements do
not change the delimiters. That is a property you can test, not a hope:

> For any ISA line — conformant, elements stripped to nothing, elements padded
> wide — `split_isa_line` returns the same four delimiters.

The test builds all three and asserts equality.

Then an adversarial sweep: roughly 180,000 inputs — every byte of a valid
interchange mutated at random, delimiters drawn from arbitrary bytes, the file
truncated at every possible length — each checked against the invariants: no
crash; a returned run starts with `ISA`, is a prefix of the input, is followed by
`GS`, holds exactly sixteen separators; and any delimiter that comes back as
usable is exactly one byte, with the element, component, and terminator mutually
distinct.

The sweep found a real bug. When an element separator had been dropped and
`ISA11` swallowed the following field, `split_isa_line` returned a two-byte
"repetition separator" with no complaint. A two-byte delimiter is not a
delimiter. `ISA11` is a fixed one-byte field; the fix makes anything else in it —
too long, alphanumeric, colliding with another delimiter — a reported finding
with the repetition separator coming back as *none*. The invariant now holds:
**a returned delimiter is either absent or exactly one usable byte.**

The split also keeps its sixteen pieces, in the result it returns. The next
step, [Reconstructing the ISA Line](reconstructing-the-isa-line.md), takes those
elements and the four delimiters and rebuilds the canonical 105-byte line — with
width no longer a fact it has to trust.

---

## The pattern

Read the element separator at the one offset that cannot move — the byte before
the first variable-width field. Recover everything else from the split, anchored
on the guaranteed separator count and the `GS` boundary, never a byte number.
Make the segment terminator one byte by rule, so that a two-byte terminator and a
trailing newline stop being the same thing. Let the version number decide whether
the fourth delimiter exists; do not infer intent. And hold the fatal for the
delimiters the interchange genuinely cannot be read without — report the rest,
and let the segment that needs a broken delimiter be the one that fails.

<a href="https://tidyedi.com"><img src="brand/tidyedi-mark.png" alt="TidyEDI" width="52" height="52" align="left" hspace="12"></a>

# Reassembling the Interchange

*An engineering note on x12-tidy: turning a reconstructed ISA line and a pile of
raw segments into one cleansed payload — and why doing the location work twice
is free.*

> **Read this as a web page:** <https://docs.tidyedi.com/reassembling-the-interchange.html>
> (served by GitHub Pages from [`docs/reassembling-the-interchange.html`](reassembling-the-interchange.html);
> clicking the `.html` file in the repo tree only shows its source — GitHub never
> renders HTML there). This Markdown file is the version of record — keep it, the
> HTML, and the figures under `docs/figures/` in sync with
> `src/x12_tidy/envelope/structure/`.

This is the fourth act of [the x12-tidy method](the-x12-tidy-method.md). The
first three notes stop at one clean 105-byte line. This one is about everything
after it: the `GS`/`ST`/`SE`/`GE`/`IEA` segments that make up the rest of the
interchange, and the one payload they and the ISA line become.

---

## 1. The claim: refuse exactly when the ISA line does

`clean_payload(dirty)` is a total function over the same input space as
`clean_isa_line`, because it is built on top of it:

- if the ISA line cannot be recovered, `clean_payload` refuses — same
  diagnostics, no payload, nothing to split;
- otherwise it hands back one `ReconstructedPayload`: the reconstructed ISA
  line, the body split into segments with the empty ones dropped, and
  everything rejoined on the sender's own terminator.

Nothing new can go fatal here. Whether the *body* is well-formed — real identifiers,
matched openers and closers, counts that add up — is not this step's question.
This step's only job is mechanical: **assemble one payload out of what the
earlier steps already trust.**

---

## 2. Two purely mechanical transforms

`split_segments` and `drop_empty_segments` share one property, and the code
says so directly: **no diagnostics, no validation, no refusal.**

```python
def split_segments(dirty: bytes) -> list[bytes]:
    located = extract_isa_line(dirty)
    if located.isa_line is None:
        return []
    decomposition = split_isa_line(located.isa_line, base_offset=located.isa_start)
    terminator = decomposition.segment_terminator
    if not terminator:
        return []
    contents = dirty[located.isa_start + len(located.isa_line):]
    contents = contents.strip(_WHITESPACE + terminator)
    return [piece.lstrip(_WHITESPACE) for piece in contents.split(terminator)]
```

Take everything after the ISA line — which, by [the locating
step](finding-the-elusive-isa-line.md)'s own contract, ends immediately before
`GS`. Strip whitespace *and the terminator* from both ends, so a trailing blank
line or a doubled closing terminator does not leave a spurious empty piece at
the end. Split on the segment terminator. Left-trim each piece — a segment identifier
is alphabetic and first, so leading whitespace is never segment content.

That produces the *raw* segments, empties included: two terminators in a row
(`~~`) split into an empty string between them, and an empty string is not a
segment.

```python
def drop_empty_segments(segments: list[bytes]) -> list[bytes]:
    return [segment for segment in segments if segment]
```

Neither function asks *why* the terminators were doubled, or whether a identifier is
real, or whether `GS` opens and `GE` closes in the right order. **Judging
requires context this step deliberately does not have.** That is [the next
note](auditing-the-envelope.md)'s job, once there is a whole payload to judge.

---

## 3. The redundant parse, and why it costs nothing

Look again at `split_segments`: it calls `extract_isa_line` and
`split_isa_line` itself. But `clean_payload` already called the full pipeline
— `clean_isa_line`, which runs those same two functions internally, plus
reconstruction — to get the repaired ISA line in the first place.

```python
def clean_payload(dirty: bytes) -> ReconstructedPayload:
    isa_result = clean_isa_line(dirty)
    if isa_result.isa_line is None:
        return ReconstructedPayload(None, isa_result, (), list(isa_result.diagnostics))

    segments = tuple(drop_empty_segments(split_segments(dirty)))
    terminator = isa_result.segment_terminator
    body = b"".join(segment + terminator for segment in segments)
    payload = isa_result.isa_line + terminator + body

    return ReconstructedPayload(payload, isa_result, segments, list(isa_result.diagnostics))
```

So the ISA line gets located and its delimiters decomposed **twice** — once by
`clean_isa_line`, once again by `split_segments`. That looks like waste. It
isn't, for two reasons.

**It's pure and cheap.** Locating and decomposing do no I/O, allocate nothing
large, and run once per call regardless of file size beyond the initial scan.
Paying for it twice on a single interchange is not a cost anyone will notice.

**It's the price of keeping `split_segments` honest.** If `split_segments`
instead took the already-computed decomposition as an argument, it would stop
being a pure function of `dirty` alone — every caller would have to thread the
right upstream result through, and a mismatched pair (segments split with one
decomposition, an ISA line reconstructed from another) becomes a class of bug
that can exist. Recomputing from `dirty` each time makes that bug
*impossible*, not just unlikely.

The two computations are also guaranteed to agree. Reconstruction never
rewrites the sender's segment terminator byte — [the previous
note](reconstructing-the-isa-line.md) establishes that a `\n` terminator stays
`\n` — so `isa_result.segment_terminator`, computed via the reconstructed line,
and the `terminator` `split_segments` recovers independently from the same
bytes, are always the same byte. The body is split on it and rejoined on it
without the two calls ever having to be reconciled.

---

## 4. Reassembly always ends in exactly one terminator

Whatever the sender put after the last real segment — nothing, one
terminator, a terminator plus a stray newline, two terminators in a row — the
strip in `split_segments` removes all of it from the end, and the join in
`clean_payload` puts back exactly one terminator after every segment,
including the last. The output always ends the same way, regardless of how
the input did.

This is not a *repair* in the sense the ISA-line phase uses the word — there
is no diagnostic for it, because nothing about it was wrong. A trailing
terminator is not preserved information; it is punctuation the join
regenerates. There is nothing to flag, so nothing is flagged.

![Two terminators in a row produce an empty piece between them; dropping empty
segments removes it, and rejoining puts exactly one terminator after every
remaining segment.](figures/reassembly-collapse.svg)

---

## 5. The closed set of outcomes

| input | outcome |
| --- | --- |
| ISA line cannot be recovered | refused — no payload, no segments, the ISA-phase diagnostics say why |
| clean input | `payload == dirty`, byte-identical, `was_clean` |
| a right-trimmed ISA element | the *reconstructed* line anchors the payload, not the dirty one — the repair is reflected all the way through |
| two terminators in a row (`~~`) | the empty piece is dropped; not present in `.segments` |
| non-`~` terminator (`\n`, bare `\r`) | preserved through the whole payload, not just the ISA line |
| trailing junk after the last segment | stripped; the reassembled payload ends in exactly one terminator |

Every row that isn't a refusal produces exactly one payload. There is still no
third outcome.

---

## 6. Where validation takes over

`ReconstructedPayload.segments` is the *raw* body: whatever identifiers and elements
the sender sent, empties dropped, nothing else touched. It has not been asked
whether `beg` is a real identifier, whether `GS`/`GE` and `ST`/`SE` nest correctly,
whether `SE01` counts the segments it claims to, or whether `ISA13` matches
`IEA02`. [Auditing the Envelope](auditing-the-envelope.md) is where all of
that lives — the first place x12-tidy checks not just the *shape* of a
segment, but whether the interchange's own bookkeeping is honest.

---

## 7. Proving it

The corpus for this step is the payload built from every case the ISA-line
notes already prove, plus a family of body-only deviations layered on top of a
known-good ISA line: a doubled terminator mid-body, a non-`~` terminator
carried all the way through, and a dirty ISA element whose repair has to
survive the join. Each is checked against the same shape of invariant the
earlier notes use:

```python
result = clean_payload(dirty)
if result.payload is None:
    assert result.diagnostics        # a refusal must say why
else:
    assert b"" not in result.segments                    # no empty pieces
    assert result.payload.startswith(result.isa_result.isa_line)
    assert result.payload == (
        result.isa_result.isa_line + terminator
        + terminator.join(result.segments) + terminator
    )
```

That last assertion is the whole claim in one line: the payload is *exactly*
the reconstructed ISA line, the terminator, the cleaned segments joined on
that same terminator, and one final terminator — never the dirty bytes, never
a stray empty piece, never a different terminator than the one the sender
chose.

---

## The pattern

Once a step downstream depends on something upstream already computed, don't
thread the dependency through — recompute it from the same raw input, if
recomputing is cheap and pure. It costs a little CPU and buys back a whole
class of "these two callers used different versions of the same fact" bugs.
Keep mechanical transforms free of judgment even when a judgment would be easy
to bolt on; a step that only assembles is a step you can trust regardless of
what validation looks like once it exists. And when a repair regenerates
something rather than preserving it — a trailing terminator, not a sender's
identifier — there is nothing to name, because nothing was wrong.

# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

"""Command-line entry point.

::

    x12-tidy check <file.edi>      run the checks built so far on a file
    x12-tidy codes [--area isa]     list every diagnostic code
    x12-tidy explain <code>         show the detail for one code

Exit codes for ``check``: 0 = clean, 1 = a fatal/error finding, 2 = usage / IO.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from x12_tidy.diagnostics import Code, Diagnostic, all_codes, meta, resolved_severity
from x12_tidy.qaqc import EnvelopeFacts, check_payload
from x12_tidy.structure import clean_payload


def _report(diags: list[Diagnostic]) -> bool:
    """Print each diagnostic to the right stream. Return True if any was a
    fatal or error after severity resolution."""
    saw_problem = False
    for diag in diags:
        severity = resolved_severity(diag.code)
        stream = sys.stdout if severity == "warning" else sys.stderr
        print(f"[{severity.upper()} {diag.code.value}] {diag.message}", file=stream)
        saw_problem |= severity in ("fatal", "error")
    return saw_problem


def _print_facts(facts: EnvelopeFacts) -> None:
    print(
        "envelope: "
        f"sender={facts.sender_qualifier!r}/{facts.sender_id!r} "
        f"receiver={facts.receiver_qualifier!r}/{facts.receiver_id!r} "
        f"usage={facts.usage_indicator!r} "
        f"groups={facts.functional_group_count} "
        f"transaction_sets={facts.transaction_set_count} "
        f"segments={facts.segment_count}"
    )


def _cmd_check(path: Path) -> int:
    try:
        data = path.read_bytes()
    except OSError as exc:
        print(f"cannot read {path}: {exc}", file=sys.stderr)
        return 2

    cleaned = clean_payload(data)
    qaqc = check_payload(cleaned) if cleaned.payload is not None else None

    diagnostics = list(cleaned.diagnostics)
    if qaqc is not None:
        diagnostics.extend(qaqc.diagnostics)
    worst_problem = _report(diagnostics)

    decomposition = cleaned.isa_result.decomposition
    if decomposition is not None:
        print(
            "delimiters: "
            f"element={decomposition.element_separator!r} "
            f"repetition={decomposition.repetition_separator!r} "
            f"component={decomposition.component_separator!r} "
            f"terminator={decomposition.segment_terminator!r}"
        )

    if cleaned.payload is None:
        return 1 if worst_problem else 0

    print(f"payload ({len(cleaned.payload)} bytes): {cleaned.payload!r}")
    if qaqc is not None and qaqc.facts is not None:
        _print_facts(qaqc.facts)
    if not diagnostics:
        print("was_clean: yes")
    return 1 if worst_problem else 0


def _cmd_codes(area: str | None) -> int:
    for code in all_codes():
        if area and code.area != area:
            continue
        m = meta(code)
        flag = " (deprecated)" if m.deprecated else ""
        print(f"{code.value:<28} {m.default_severity:<8} {m.title}{flag}")
    return 0


def _cmd_explain(code_str: str) -> int:
    try:
        code = Code(code_str)
    except ValueError:
        print(f"unknown code: {code_str}", file=sys.stderr)
        return 2
    m = meta(code)
    print(f"{code.value}  ({m.default_severity})")
    print(f"  {m.title}")
    print()
    print(m.explanation)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="x12-tidy", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="run the checks on a file")
    p_check.add_argument("file", type=Path)

    p_codes = sub.add_parser("codes", help="list diagnostic codes")
    p_codes.add_argument("--area", help="limit to one area (e.g. isa)")

    p_explain = sub.add_parser("explain", help="detail for one code")
    p_explain.add_argument("code")

    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if args.command == "check":
        return _cmd_check(args.file)
    if args.command == "codes":
        return _cmd_codes(args.area)
    if args.command == "explain":
        return _cmd_explain(args.code)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

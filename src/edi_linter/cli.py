"""Command-line entry point.

::

    edi-linter check <file.edi>      run the checks built so far on a file
    edi-linter codes [--area isa]     list every diagnostic code
    edi-linter explain <code>         show the detail for one code

Exit codes for ``check``: 0 = clean, 1 = a fatal/error finding, 2 = usage / IO.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from edi_linter.diagnostics import Code, all_codes, meta, resolved_severity
from edi_linter.isa import extract_isa_line


def _cmd_check(path: Path) -> int:
    try:
        data = path.read_bytes()
    except OSError as exc:
        print(f"cannot read {path}: {exc}", file=sys.stderr)
        return 2

    result = extract_isa_line(data)
    worst = "warning"
    for diag in result.diagnostics:
        severity = resolved_severity(diag.code)
        stream = sys.stdout if severity == "warning" else sys.stderr
        print(f"[{severity.upper()} {diag.code.value}] {diag.message}", file=stream)
        if severity in ("fatal", "error"):
            worst = "error"

    if result.isa_line is not None:
        print(f"isa_line: {len(result.isa_line)} bytes  {result.isa_line!r}")
    return 1 if worst == "error" else 0


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
    parser = argparse.ArgumentParser(prog="edi-linter", description=__doc__)
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

# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

"""Generate ``docs/diagnostics.md`` from the code registry.

The registry in :mod:`x12_tidy.diagnostics.codes` is the single source of
truth.  This script renders it to Markdown so the list is browsable in the repo
and on GitHub with full history.  Never edit ``docs/diagnostics.md`` by hand --
a pre-commit hook regenerates it when ``codes.py`` changes, and CI fails the
build if the committed file is stale.

Usage::

    python scripts/gen_diagnostics_docs.py            # write the file
    python scripts/gen_diagnostics_docs.py --check     # exit 1 if stale
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Runnable from a plain checkout, without the package installed.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from x12_tidy.diagnostics import AREAS, all_codes, meta  # noqa: E402

BANNER = "<!-- GENERATED from src/x12_tidy/diagnostics/codes.py -- do not edit -- run scripts/gen_diagnostics_docs.py -->"
DOC_PATH = Path(__file__).resolve().parents[1] / "docs" / "diagnostics.md"


def render() -> str:
    lines: list[str] = [
        BANNER,
        "",
        "# Diagnostic codes",
        "",
        "Every finding the linter can emit. Codes are `area.specific`; the "
        "`area` is the subject of the finding. `default severity` is a starting "
        "point that user config can override per-code (including to `ignore`).",
        "",
    ]
    by_area = {area: [c for c in all_codes() if c.area == area] for area in AREAS}
    for area, codes in by_area.items():
        if not codes:
            continue
        lines.append(f"## `{area}`")
        lines.append("")
        lines.append("| code | severity | title |")
        lines.append("| --- | --- | --- |")
        for code in codes:
            m = meta(code)
            flag = " _(deprecated)_" if m.deprecated else ""
            lines.append(
                f"| `{code.value}`{flag} | {m.default_severity} | {m.title} |"
            )
        lines.append("")
        for code in codes:
            m = meta(code)
            lines.append(f"### `{code.value}`")
            lines.append("")
            lines.append(f"*{m.default_severity}* — {m.title}")
            lines.append("")
            lines.append(m.explanation)
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if docs/diagnostics.md is out of date (do not write)",
    )
    args = parser.parse_args(argv)

    generated = render()
    if args.check:
        current = DOC_PATH.read_text() if DOC_PATH.exists() else ""
        if current != generated:
            print(
                f"{DOC_PATH} is stale; run: python scripts/gen_diagnostics_docs.py",
                file=sys.stderr,
            )
            return 1
        return 0

    DOC_PATH.write_text(generated)
    print(f"wrote {DOC_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

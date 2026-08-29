"""The code registry stays internally consistent and matched to what modules emit.

This is the check that actually prevents drift -- not discipline, a failing
build.  See ``docs/design.md``.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from x12_tidy.diagnostics import AREAS, Code, all_codes, meta

SRC = Path(__file__).resolve().parents[1] / "src" / "x12_tidy"

_CODE_STRING = re.compile(r"^[a-z]+\.[a-z0-9]+(?:-[a-z0-9]+)*$")


def test_every_code_is_registered() -> None:
    for code in Code:
        assert code in list(all_codes()), f"{code} missing from META"


def test_code_strings_are_well_formed() -> None:
    for code in Code:
        assert _CODE_STRING.match(code.value), f"malformed code string: {code.value}"
        assert code.area in AREAS, f"{code.value}: area {code.area!r} not in AREAS"


def test_member_name_matches_code_string() -> None:
    for code in Code:
        expected = code.value.replace(".", "_").replace("-", "_").upper()
        assert code.name == expected, f"{code.name} should be {expected}"


def test_no_duplicate_code_strings() -> None:
    values = [c.value for c in Code]
    assert len(values) == len(set(values))


def test_metadata_is_complete() -> None:
    for code in Code:
        m = meta(code)
        assert m.title and not m.title.endswith("."), code
        assert len(m.explanation) > 40, f"{code}: explanation too thin"
        assert m.default_severity in ("fatal", "error", "warning"), code


def _emitted_codes() -> set[str]:
    """Every ``Code.MEMBER`` referenced anywhere under src/x12_tidy."""
    emitted: set[str] = set()
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "Code"
            ):
                emitted.add(node.attr)
    return emitted


def test_registry_matches_what_modules_emit() -> None:
    emitted = _emitted_codes()
    registered = {c.name for c in Code}

    unknown = emitted - registered
    assert not unknown, f"code(s) referenced but not defined: {unknown}"

    unused = registered - emitted
    # Every code must be emitted by some module (or explicitly deprecated).
    unused = {n for n in unused if not meta(Code[n]).deprecated}
    assert not unused, f"code(s) defined but never emitted: {unused}"


def test_generated_docs_are_current() -> None:
    from scripts.gen_diagnostics_docs import DOC_PATH, render

    assert DOC_PATH.exists(), "docs/diagnostics.md missing; run the generator"
    assert DOC_PATH.read_text() == render(), (
        "docs/diagnostics.md is stale; run: python scripts/gen_diagnostics_docs.py"
    )

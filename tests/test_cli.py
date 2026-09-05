# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

"""``x12-tidy check`` -- runs the full pipeline (cleanse + envelope QA/QC) on
a file and reports every diagnostic from both phases.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _isa_helpers import build_isa

from x12_tidy.cli import main

_CLEAN_TRAILER = (
    b"GS*PO*SENDERGS*RECEIVERID*20240101*1200*1*X*004010~"
    b"ST*850*0001~BEG*00*NE*PO0001**20240101~SE*3*0001~"
    b"GE*1*1~IEA*1*000000001~"
)


def _write(tmp_path: Path, data: bytes) -> Path:
    path = tmp_path / "sample.edi"
    path.write_bytes(data)
    return path


def test_check_exits_clean_and_reports_envelope_facts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write(tmp_path, build_isa(trailer=_CLEAN_TRAILER))
    assert main(["check", str(path)]) == 0
    out = capsys.readouterr().out
    assert "was_clean: yes" in out
    assert "envelope: " in out
    assert "groups=1" in out


def test_check_reports_qaqc_findings_and_exits_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    trailer = _CLEAN_TRAILER.replace(b"IEA*1*000000001~", b"IEA*2*000000001~")
    path = _write(tmp_path, build_isa(trailer=trailer))
    assert main(["check", str(path)]) == 1
    err = capsys.readouterr().err
    assert "structure.functional-group-count-mismatch" in err


def test_check_reports_isa_phase_refusal_and_exits_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write(tmp_path, b"not an edi file at all")
    assert main(["check", str(path)]) == 1
    err = capsys.readouterr().err
    assert "isa.no-identifier" in err


def test_check_missing_file_is_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["check", str(tmp_path / "missing.edi")]) == 2

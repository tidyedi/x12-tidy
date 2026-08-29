"""Diagnostics: the finding record and the code registry.

* :class:`Diagnostic` -- one finding (code + message + offset), severity-free.
* :class:`Code` -- the stable identity of every kind of finding.
* :func:`meta`, :func:`all_codes` -- read the registry.

The registry in :mod:`edi_linter.diagnostics.codes` is the single source of
truth; ``docs/diagnostics.md`` and the ``edi-linter codes`` command are
generated from it.
"""

from __future__ import annotations

from edi_linter.diagnostics.codes import (
    AREAS,
    Code,
    CodeMeta,
    Severity,
    all_codes,
    meta,
    resolved_severity,
)
from edi_linter.diagnostics.diagnostic import Diagnostic

__all__ = [
    "AREAS",
    "Code",
    "CodeMeta",
    "Severity",
    "Diagnostic",
    "all_codes",
    "meta",
    "resolved_severity",
]

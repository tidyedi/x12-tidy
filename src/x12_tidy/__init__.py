# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Michael Schertz

"""x12-tidy: validate and repair malformed ANSI X12 EDI documents.

The free command-line tool and Python library behind TidyEDI
(https://tidyedi.com). See ``docs/design.md`` for the design.

* :mod:`x12_tidy.envelope.isa` -- ISA interchange-envelope checks
* :mod:`x12_tidy.envelope.structure` -- whole-interchange structure (segment splitting,
  ``clean_payload``)
* :mod:`x12_tidy.envelope.qaqc` -- envelope QA/QC, once a payload exists
* :mod:`x12_tidy.envelope.tidy` -- the whole-package entry point: cleanse, then QA/QC
* :mod:`x12_tidy.diagnostics` -- the finding record and the code registry
"""

__version__ = "0.1.0"

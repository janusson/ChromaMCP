"""Ingestion: read chromatographic data into typed objects.

W1 covers **mzML chromatogram ingestion**, TIC and XIC.  The reader is
standard-library only and takes ``numpy`` as its single runtime dependency
(``AGENTS.md`` §5); every vendor binary format is refused with an explicit
conversion instruction rather than read approximately (``AGENTS.md`` §4).
"""

from __future__ import annotations

from chromamcp.io.mzml import (
    Chromatogram,
    ChromatogramKind,
    SourceSnapshot,
    read_chromatograms,
    read_chromatograms_with_source,
    read_source_bytes,
    read_tic,
    read_xic,
)

__all__ = [
    "Chromatogram",
    "ChromatogramKind",
    "SourceSnapshot",
    "read_chromatograms",
    "read_chromatograms_with_source",
    "read_source_bytes",
    "read_tic",
    "read_xic",
]

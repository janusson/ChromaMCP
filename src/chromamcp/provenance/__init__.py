"""Provenance: the record emitted with every panel result (W5).

The block ``M1-BRIEF.md`` §4 requires, serialised deterministically so that the
same input, parameters and versions produce byte-identical output.
"""

from __future__ import annotations

from chromamcp.provenance.record import (
    TOLERANCE_BASIS,
    VERDICTS,
    Criteria,
    InputFile,
    LibraryVersions,
    MetricRecord,
    ProvenanceRecord,
    Reader,
    build_record,
    file_sha256,
    library_versions,
    serialise,
    utc_now,
)

__all__ = [
    "TOLERANCE_BASIS",
    "VERDICTS",
    "Criteria",
    "InputFile",
    "LibraryVersions",
    "MetricRecord",
    "ProvenanceRecord",
    "Reader",
    "build_record",
    "file_sha256",
    "library_versions",
    "serialise",
    "utc_now",
]

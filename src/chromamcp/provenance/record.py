"""The provenance record (W5).

Every panel result is emitted with the record block ``M1-BRIEF.md`` §4 requires:
the input file and its content hash, the reader, the parameters, the library
versions, the criteria applied (or ``none``), a per-metric block, and a UTC
timestamp **labelled as the run time, not the acquisition time**.

**Determinism is a gate** (``AGENTS.md`` §1.7): the same input file, parameters
and versions must serialise **byte-identically**.  Two things make that hold:

- the serialiser sorts keys and walks the record in a fixed way, and
- the timestamp is **injected**, not read from the clock inside the serialiser —
  so a caller that passes the same instant twice gets the same bytes.  The
  helper :func:`utc_now` is for real runs and is deliberately kept out of the
  serialiser.

Float formatting is pinned: a finite ``float`` is written by Python's shortest
round-trip ``repr`` (stable across CPython), and the non-finite values JSON
cannot carry are written as the strings ``"NaN"``, ``"Infinity"`` and
``"-Infinity"`` — never as invalid JSON, and never as ``0``, which would make a
missing value indistinguishable from a measured zero (``AGENTS.md`` §1.6).

Vocabulary discipline (``AGENTS.md`` §2) applies to every field name and string
here: the record is evidence a qualified person can review, and it asserts
nothing more.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path

from chromamcp.metrics import MetricResult

__all__ = [
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

#: The verdicts a per-metric block may carry.  ``M1-BRIEF.md`` §4 names
#: ``pass`` / ``flag`` / ``not-evaluated``; M1 does not evaluate a sequence, so
#: every record it emits carries ``not-evaluated``.
VERDICTS = frozenset({"pass", "flag", "not-evaluated"})

_TIMESTAMP_NOTE = "run time, not acquisition time"
_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


@dataclass(frozen=True, slots=True)
class InputFile:
    """The input file: its path as given, and the SHA-256 of its bytes."""

    path: str
    sha256: str


@dataclass(frozen=True, slots=True)
class Reader:
    """The reader that produced the trace: a name and a version."""

    name: str
    version: str


@dataclass(frozen=True, slots=True)
class LibraryVersions:
    """The versions the result depends on (``M1-BRIEF.md`` §4)."""

    chromamcp: str
    numpy: str
    mzml_reader: str
    python: str


@dataclass(frozen=True, slots=True)
class Criteria:
    """A criteria file that was applied: its id and the SHA-256 of its bytes."""

    id: str
    sha256: str


@dataclass(frozen=True, slots=True)
class MetricRecord:
    """One metric's value, its identifiers, and the verdict against criteria."""

    metric_id: str
    value: float
    unit: str
    formula_id: str
    tolerance: float | None
    verdict: str

    def __post_init__(self) -> None:
        if self.verdict not in VERDICTS:
            raise ValueError(
                f"verdict {self.verdict!r} is not one of {sorted(VERDICTS)}."
            )

    @classmethod
    def from_result(
        cls, result: MetricResult, *, verdict: str = "not-evaluated"
    ) -> MetricRecord:
        """Build a record block from a panel :class:`MetricResult`."""
        return cls(
            metric_id=result.metric_id,
            value=result.value,
            unit=result.unit,
            formula_id=result.formula_id,
            tolerance=result.tolerance,
            verdict=verdict,
        )


@dataclass(frozen=True, slots=True)
class ProvenanceRecord:
    """The full record emitted with a panel result."""

    input_file: InputFile
    reader: Reader
    parameters: Mapping[str, object]
    library_versions: LibraryVersions
    criteria: Criteria | None
    metrics: tuple[MetricRecord, ...]
    timestamp_utc: str
    timestamp_note: str = _TIMESTAMP_NOTE


def utc_now() -> datetime:
    """The current time, timezone-aware in UTC.  For real runs, not for tests."""
    return datetime.now(UTC)


def file_sha256(path: str | Path) -> str:
    """The SHA-256 of a file's bytes, as lowercase hex."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def library_versions() -> LibraryVersions:
    """The versions of this package, numpy, the reader and the interpreter."""
    package = metadata.version("chromamcp")
    import numpy

    return LibraryVersions(
        chromamcp=package,
        numpy=numpy.__version__,
        mzml_reader=package,
        python=platform.python_version(),
    )


def build_record(
    *,
    input_path: str | Path,
    parameters: Mapping[str, object],
    metrics: Sequence[MetricRecord],
    timestamp: datetime,
    criteria: Criteria | None = None,
) -> ProvenanceRecord:
    """Assemble a :class:`ProvenanceRecord`, hashing the input file.

    *timestamp* is the **run time**; a naive datetime is read as UTC.  Passing
    the same instant twice yields byte-identical output.
    """
    resolved = Path(input_path)
    return ProvenanceRecord(
        input_file=InputFile(path=str(resolved), sha256=file_sha256(resolved)),
        reader=Reader(name="chromamcp.io.mzml", version=metadata.version("chromamcp")),
        parameters=dict(parameters),
        library_versions=library_versions(),
        criteria=criteria,
        metrics=tuple(metrics),
        timestamp_utc=_format_utc(timestamp),
    )


def serialise(record: ProvenanceRecord) -> str:
    """Serialise *record* to deterministic JSON text.

    Keys are sorted, floats are pinned (see the module docstring), and the only
    input that varies between runs — the timestamp — is part of *record*, so two
    records carrying the same timestamp serialise to identical bytes.
    """
    return json.dumps(
        _to_jsonable(record),
        sort_keys=True,
        ensure_ascii=True,
        indent=2,
        allow_nan=False,
    )


def _format_utc(timestamp: datetime) -> str:
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC).strftime(_TIMESTAMP_FORMAT)


def _to_jsonable(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _to_jsonable(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, Mapping):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0.0 else "-Infinity"
    return value

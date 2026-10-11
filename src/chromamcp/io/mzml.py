"""mzML chromatogram reader (W1).

Reads the chromatogram channels of an mzML file — TIC and XIC — into typed
:class:`Chromatogram` objects, using only the standard library and ``numpy``.

**Why a hand-written reader.**  The sibling project MSMCP parses mzML with the
standard library rather than a third-party reader, and ChromaMCP inherits that
choice: the chromatogram subset is small and well specified (a
``<chromatogramList>`` of base64-encoded, optionally zlib-compressed float
arrays), and parsing it here keeps the runtime surface to ``numpy`` alone
(``AGENTS.md`` §5) and the licence surface to a single BSD-3 package
(``AGENTS.md`` §6).

**Conventions this module implements, and the alternatives it rejects.**  Where
the format admits more than one reading, this reader follows these and refuses
rather than guessing:

- *Time unit.*  A chromatogram time array (``MS:1000595``) is defined **in
  minutes**; retention time is read in minutes and never silently converted.
  An array that names a different unit is refused.
- *Missing values.*  A missing intensity is carried as ``NaN``, never ``0`` — a
  zero-filled gap is indistinguishable from a measured zero (``AGENTS.md`` §1.6).
- *Binary precision.*  Taken from the array's ``MS:1000521`` (32-bit) or
  ``MS:1000523`` (64-bit) term.  With neither term the element size cannot be
  inferred from the file, so the reader refuses it rather than assuming one.
- *Compression.*  ``MS:1000574`` is zlib; ``MS:1000576`` **or the absence of a
  compression term** is uncompressed (absence has a single safe reading).
  MS-Numpress arrays are refused with an instruction to re-export.
- *Kind.*  A chromatogram is classified as TIC (``MS:1000235``), XIC
  (``MS:1000627``) or BPC (``MS:1000628``); anything else is
  :attr:`ChromatogramKind.OTHER`.

Only mzML is accepted.  Every vendor binary format, and every other extension,
is refused with an explicit conversion instruction (``AGENTS.md`` §4).
"""

from __future__ import annotations

import base64
import binascii
import gzip
import xml.etree.ElementTree as ET
import zlib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from chromamcp.errors import (
    ChannelResolutionError,
    InaccessiblePathError,
    MalformedFileError,
    UnsupportedFormatError,
)

__all__ = [
    "Chromatogram",
    "ChromatogramKind",
    "read_chromatograms",
    "read_tic",
    "read_xic",
]

# --- mzML controlled-vocabulary accessions ---------------------------------
# These are the term identifiers of the PSI-MS controlled vocabulary used by
# mzML; the trailing comment on each line is the term's own name.  They are
# format constants, not scientific formulas, so they carry no row in
# SOURCES.md.
_ACC_TIC = "MS:1000235"  # total ion current chromatogram
_ACC_XIC = "MS:1000627"  # selected ion current chromatogram
_ACC_BPC = "MS:1000628"  # base peak chromatogram
_ACC_TIME_ARRAY = "MS:1000595"  # time array (minutes)
_ACC_INTENSITY_ARRAY = "MS:1000515"  # intensity array
_ACC_MZ_ARRAY = "MS:1000514"  # m/z array
_ACC_32BIT_FLOAT = "MS:1000521"  # 32-bit float
_ACC_64BIT_FLOAT = "MS:1000523"  # 64-bit float
_ACC_ZLIB = "MS:1000574"  # zlib compression
_ACC_SELECTED_ION_MZ = "MS:1000744"  # selected ion m/z
_ACC_UNIT_MINUTE = "UO:0000031"  # minute (time-array unit)
_NUMPRESS = frozenset({"MS:1002312", "MS:1002313", "MS:1002314"})

#: Formats the reader recognises and refuses, with a human label for each, so
#: the refusal message can name what it saw.  The first four are vendor binary
#: formats; the remainder are other non-mzML MS formats.
_REFUSED_FORMATS: dict[str, str] = {
    ".raw": "Thermo Fisher raw",
    ".d": "Agilent / Bruker directory",
    ".lcd": "Shimadzu LabSolutions",
    ".wiff": "SCIEX",
    ".mzxml": "mzXML",
    ".mgf": "Mascot Generic Format",
    ".cdf": "ANDI/AIA netCDF",
}


class ChromatogramKind(Enum):
    """The chromatogram channel types this reader distinguishes."""

    TIC = "tic"
    XIC = "xic"
    BPC = "bpc"
    OTHER = "other"


@dataclass(frozen=True, slots=True, eq=False)
class Chromatogram:
    """A single chromatogram channel read from an mzML file.

    Immutable, and the ``time`` / ``intensity`` buffers are read-only, so a
    parsed chromatogram can be handed to several consumers without any of them
    being able to alter what the others see.

    ``time`` is in **minutes** (the mzML time-array convention, ``MS:1000595``)
    and ``intensity`` is in the file's own intensity unit (typically detector
    counts).  The two arrays are the same length and index-aligned.
    """

    id: str
    kind: ChromatogramKind
    time: NDArray[np.float64]
    intensity: NDArray[np.float64]
    target_mz: float | None = None

    @property
    def n_points(self) -> int:
        """Number of (time, intensity) points in the chromatogram."""
        return int(self.time.size)


# ---------------------------------------------------------------------------
# Public reader API
# ---------------------------------------------------------------------------
def read_chromatograms(path: str | Path) -> tuple[Chromatogram, ...]:
    """Read every chromatogram channel in the mzML file at *path*.

    Returns them in file order.  A valid mzML file with no ``<chromatogramList>``
    yields an empty tuple; a file whose root element is not ``mzML``, or whose
    chromatograms are incomplete, raises
    :class:`~chromamcp.errors.MalformedFileError`.
    """
    resolved = _resolve_readable(path)
    root = _parse_root(resolved)
    run = _child(root, "run")
    if run is None:
        raise MalformedFileError(f"'{resolved}' has no <run> element; not valid mzML.")
    chromatogram_list = _child(run, "chromatogramList")
    if chromatogram_list is None:
        return ()
    return tuple(
        _parse_chromatogram(chromatogram)
        for chromatogram in _iter_children(chromatogram_list, "chromatogram")
    )


def read_tic(path: str | Path) -> Chromatogram:
    """Return the single TIC channel (``MS:1000235``) in the file at *path*.

    Raises :class:`~chromamcp.errors.ChannelResolutionError` if the file has no
    TIC, or more than one — the reader never picks one of several silently.
    """
    tics = [c for c in read_chromatograms(path) if c.kind is ChromatogramKind.TIC]
    if not tics:
        raise ChannelResolutionError(
            f"'{path}' has no TIC channel (MS:1000235). "
            f"Call read_chromatograms() to list the channels present."
        )
    if len(tics) > 1:
        raise ChannelResolutionError(
            f"'{path}' has {len(tics)} TIC channels; the channel is ambiguous."
        )
    return tics[0]


def read_xic(path: str | Path, *, chromatogram_id: str | None = None) -> Chromatogram:
    """Return an XIC channel (``MS:1000627``) from the file at *path*.

    If *chromatogram_id* is given, the XIC with that id is returned; otherwise
    the file must contain exactly one XIC.  Raises
    :class:`~chromamcp.errors.ChannelResolutionError` when the channel cannot be
    resolved unambiguously.
    """
    xics = [c for c in read_chromatograms(path) if c.kind is ChromatogramKind.XIC]
    if chromatogram_id is not None:
        for chromatogram in xics:
            if chromatogram.id == chromatogram_id:
                return chromatogram
        raise ChannelResolutionError(
            f"No XIC channel with id '{chromatogram_id}' in '{path}'."
        )
    if not xics:
        raise ChannelResolutionError(
            f"'{path}' has no XIC channel (MS:1000627). "
            f"Call read_chromatograms() to list the channels present."
        )
    if len(xics) > 1:
        raise ChannelResolutionError(
            f"'{path}' has {len(xics)} XIC channels; pass chromatogram_id to "
            f"select one."
        )
    return xics[0]


# ---------------------------------------------------------------------------
# Path resolution and format refusal
# ---------------------------------------------------------------------------
def _resolve_readable(path: str | Path) -> Path:
    """Return *path* as an existing regular file, or refuse it explicitly.

    The format check runs first so that a vendor file — including a Bruker
    ``.d`` directory, which is not a regular file — gets the actionable
    conversion message rather than a generic "not a file" error.
    """
    resolved = Path(path)
    _check_supported_format(resolved)
    if not resolved.exists():
        raise InaccessiblePathError(f"No such file: '{resolved}'.")
    if not resolved.is_file():
        raise InaccessiblePathError(f"Not a regular file: '{resolved}'.")
    return resolved


def _check_supported_format(path: Path) -> None:
    name = path.name.lower()
    if name.endswith(".mzml") or name.endswith(".mzml.gz"):
        return

    suffix = path.suffix.lower()
    if suffix in _REFUSED_FORMATS:
        raise UnsupportedFormatError(
            f"{_REFUSED_FORMATS[suffix]} files ('{path.name}') cannot be read "
            f"directly. Convert to mzML first, e.g. with ProteoWizard MSConvert "
            f"(`msconvert {path.name} --mzML`), then point the reader at the "
            f".mzML file."
        )

    raise UnsupportedFormatError(
        f"Unrecognised extension '{suffix}'. This reader accepts only .mzML "
        f"(and gzipped .mzML.gz). Convert other formats to mzML with "
        f"ProteoWizard MSConvert."
    )


# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------
def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(elem: ET.Element, name: str) -> ET.Element | None:
    for child in elem:
        if _local(child.tag) == name:
            return child
    return None


def _iter_children(elem: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in elem if _local(child.tag) == name]


def _accessions(elem: ET.Element) -> set[str]:
    return {
        child.get("accession", "")
        for child in elem
        if _local(child.tag) == "cvParam" and child.get("accession")
    }


def _to_int_or_none(raw: str | None) -> int | None:
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _empty_array() -> NDArray[np.float64]:
    """A zero-length, read-only float64 array — a channel with no points."""
    array = np.empty(0, dtype=np.float64)
    array.setflags(write=False)
    return array


# ---------------------------------------------------------------------------
# Chromatogram parsing
# ---------------------------------------------------------------------------
def _classify(elem: ET.Element) -> ChromatogramKind:
    accessions = _accessions(elem)
    if _ACC_TIC in accessions:
        return ChromatogramKind.TIC
    if _ACC_XIC in accessions:
        return ChromatogramKind.XIC
    if _ACC_BPC in accessions:
        return ChromatogramKind.BPC
    return ChromatogramKind.OTHER


def _selected_ion_mz(elem: ET.Element) -> float | None:
    for child in elem:
        if (
            _local(child.tag) == "cvParam"
            and child.get("accession") == _ACC_SELECTED_ION_MZ
        ):
            raw = child.get("value")
            if raw is None:
                return None
            try:
                return float(raw)
            except ValueError:
                return None
    return None


def _array_type(accessions: set[str]) -> str | None:
    if _ACC_TIME_ARRAY in accessions:
        return "time"
    if _ACC_INTENSITY_ARRAY in accessions:
        return "intensity"
    if _ACC_MZ_ARRAY in accessions:
        return "mz"
    return None


def _time_unit_accession(elem: ET.Element) -> str | None:
    for child in elem:
        if _local(child.tag) == "cvParam" and child.get("accession") == _ACC_TIME_ARRAY:
            return child.get("unitAccession")
    return None


def _decode_binary_data_array(
    elem: ET.Element,
) -> tuple[str | None, NDArray[np.float64]]:
    """Decode one ``<binaryDataArray>`` to an ordered float64 array.

    Returns ``(array_type, values)`` where *array_type* is ``"time"``,
    ``"intensity"``, ``"mz"`` or ``None``.  Refuses MS-Numpress, unmet precision
    and a non-minute time unit rather than guessing (see the module docstring).
    """
    accessions = _accessions(elem)
    if accessions & _NUMPRESS:
        raise UnsupportedFormatError(
            "This chromatogram uses MS-Numpress compression, which this reader "
            "does not decode. Re-export the file without Numpress (the MSConvert "
            "default) and retry."
        )
    array_type = _array_type(accessions)
    if array_type == "time":
        unit = _time_unit_accession(elem)
        if unit is not None and unit != _ACC_UNIT_MINUTE:
            raise UnsupportedFormatError(
                f"Chromatogram time array is in unit '{unit}', not minutes "
                f"('{_ACC_UNIT_MINUTE}'). This reader reports retention time in "
                f"minutes and will not silently convert."
            )

    binary = _child(elem, "binary")
    raw_text = binary.text if binary is not None else None
    if raw_text is None or not raw_text.strip():
        return array_type, _empty_array()

    if _ACC_64BIT_FLOAT in accessions:
        itemsize = 8
    elif _ACC_32BIT_FLOAT in accessions:
        itemsize = 4
    else:
        raise MalformedFileError(
            "A chromatogram <binaryDataArray> does not state its precision "
            "(MS:1000521 32-bit or MS:1000523 64-bit); the element size cannot "
            "be inferred, so the file is refused rather than guessed."
        )
    dtype = np.dtype(f"<f{itemsize}")

    clean = "".join(raw_text.split())
    try:
        raw = base64.b64decode(clean, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise MalformedFileError(
            "A chromatogram <binaryDataArray> payload is not valid base64."
        ) from exc

    if _ACC_ZLIB in accessions:
        try:
            raw = zlib.decompress(raw)
        except zlib.error as exc:
            raise MalformedFileError(
                "A chromatogram <binaryDataArray> payload failed zlib decompression."
            ) from exc

    if len(raw) % dtype.itemsize:
        raise MalformedFileError(
            "A chromatogram <binaryDataArray> payload length is not a multiple "
            "of its element size."
        )
    values = np.frombuffer(raw, dtype=dtype).astype(np.float64, copy=False)
    values.setflags(write=False)
    return array_type, values


def _parse_chromatogram(elem: ET.Element) -> Chromatogram:
    chromatogram_id = elem.get("id", "")
    declared = _to_int_or_none(elem.get("defaultArrayLength"))

    time: NDArray[np.float64] | None = None
    intensity: NDArray[np.float64] | None = None
    binary_data_array_list = _child(elem, "binaryDataArrayList")
    if binary_data_array_list is not None:
        for binary_data_array in _iter_children(
            binary_data_array_list, "binaryDataArray"
        ):
            array_type, values = _decode_binary_data_array(binary_data_array)
            if array_type == "time":
                time = values
            elif array_type == "intensity":
                intensity = values

    if time is None:
        raise MalformedFileError(
            f"Chromatogram '{chromatogram_id}' has no time array (MS:1000595)."
        )
    if intensity is None:
        raise MalformedFileError(
            f"Chromatogram '{chromatogram_id}' has no intensity array (MS:1000515)."
        )
    if time.size != intensity.size:
        raise MalformedFileError(
            f"Chromatogram '{chromatogram_id}' has {time.size} time points but "
            f"{intensity.size} intensities."
        )
    if declared is not None and declared != time.size:
        raise MalformedFileError(
            f"Chromatogram '{chromatogram_id}' declares defaultArrayLength="
            f"{declared} but carries {time.size} time points."
        )

    return Chromatogram(
        id=chromatogram_id,
        kind=_classify(elem),
        time=time,
        intensity=intensity,
        target_mz=_selected_ion_mz(elem),
    )


# ---------------------------------------------------------------------------
# Document parsing
# ---------------------------------------------------------------------------
def _parse_root(path: Path) -> ET.Element:
    try:
        if path.name.lower().endswith(".gz"):
            with gzip.open(path, "rb") as handle:
                root = ET.parse(handle).getroot()
        else:
            root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise MalformedFileError(
            f"'{path}' is not well-formed XML and cannot be read as mzML."
        ) from exc
    except gzip.BadGzipFile as exc:
        raise MalformedFileError(
            f"'{path}' is named .gz but is not a valid gzip stream."
        ) from exc
    except OSError as exc:
        raise InaccessiblePathError(f"Could not read '{path}': {exc}") from exc

    if _local(root.tag) != "mzML":
        raise MalformedFileError(
            f"'{path}' is not an mzML document (root element is "
            f"'{_local(root.tag)}', expected 'mzML')."
        )
    return root

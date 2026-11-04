"""W1 tests — the mzML chromatogram reader.

Every fixture here is **generated in-test** as mzML text with analytically
placed values, so no data file is committed (``AGENTS.md`` §8).  The builder
below writes real mzML structure — a ``<chromatogramList>`` of base64-encoded
binary arrays — so the reader is exercised against the actual format, not a
convenience shim.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import os
import zlib
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

from chromamcp.errors import (
    ChannelResolutionError,
    InaccessiblePathError,
    MalformedFileError,
    SourceChangedError,
    UnsupportedFormatError,
)
from chromamcp.io import (
    ChromatogramKind,
    mzml,
    read_chromatograms,
    read_chromatograms_with_source,
    read_tic,
    read_xic,
)

# --- synthetic mzML builder -------------------------------------------------
_ACC_TIC = "MS:1000235"
_ACC_XIC = "MS:1000627"
_ACC_TIME = "MS:1000595"
_ACC_INTENSITY = "MS:1000515"
_ACC_SELECTED_ION_MZ = "MS:1000744"
_MINUTE = ("UO:0000031", "minute")


def _payload(
    values: NDArray[np.float64] | list[float],
    *,
    dtype: str = "<f8",
    compression: str = "none",
) -> str:
    raw = np.asarray(values, dtype=dtype).tobytes()
    if compression == "zlib":
        raw = zlib.compress(raw)
    return base64.b64encode(raw).decode("ascii")


def _bda(
    values: NDArray[np.float64] | list[float],
    *,
    array_accession: str,
    array_name: str,
    precision: str | None = "64",
    compression: str | None = "none",
    unit: tuple[str, str] | None = None,
    extra_cv: str = "",
) -> str:
    parts: list[str] = []
    unit_attr = ""
    if unit is not None:
        unit_attr = f' unitCvRef="UO" unitAccession="{unit[0]}" unitName="{unit[1]}"'
    parts.append(
        f'<cvParam cvRef="MS" accession="{array_accession}" '
        f'name="{array_name}" value=""{unit_attr}/>'
    )
    if precision == "64":
        parts.append(
            '<cvParam cvRef="MS" accession="MS:1000523" name="64-bit float" value=""/>'
        )
    elif precision == "32":
        parts.append(
            '<cvParam cvRef="MS" accession="MS:1000521" name="32-bit float" value=""/>'
        )
    if compression == "none":
        parts.append(
            '<cvParam cvRef="MS" accession="MS:1000576" name="no compression" value=""/>'
        )
    elif compression == "zlib":
        parts.append(
            '<cvParam cvRef="MS" accession="MS:1000574" name="zlib compression" value=""/>'
        )
    parts.append(extra_cv)
    dtype = {None: "<f8", "32": "<f4", "64": "<f8"}[precision]
    payload = _payload(values, dtype=dtype, compression=compression or "none")
    return (
        f'<binaryDataArray encodedLength="{len(payload)}">'
        + "".join(parts)
        + f"<binary>{payload}</binary></binaryDataArray>"
    )


def _chromatogram(
    chromatogram_id: str,
    *,
    kind_accession: str,
    kind_name: str,
    time: NDArray[np.float64] | list[float],
    intensity: NDArray[np.float64] | list[float] | None,
    precision: str | None = "64",
    compression: str | None = "none",
    time_unit: tuple[str, str] | None = _MINUTE,
    intensity_unit: tuple[str, str] | None = None,
    target_mz: float | None = None,
    declared: int | None = None,
    extra_cv: str = "",
) -> str:
    cv: list[str] = []
    if target_mz is not None:
        cv.append(
            f'<cvParam cvRef="MS" accession="{_ACC_SELECTED_ION_MZ}" '
            f'name="selected ion m/z" value="{target_mz}" unitCvRef="MS" '
            f'unitAccession="MS:1000040" unitName="m/z"/>'
        )
    arrays = [
        _bda(
            time,
            array_accession=_ACC_TIME,
            array_name="time array",
            precision=precision,
            compression=compression,
            unit=time_unit,
            extra_cv=extra_cv,
        )
    ]
    if intensity is not None:
        arrays.append(
            _bda(
                intensity,
                array_accession=_ACC_INTENSITY,
                array_name="intensity array",
                unit=intensity_unit,
                precision=precision,
                compression=compression,
            )
        )
    length = len(time) if declared is None else declared
    return (
        f'<chromatogram id="{chromatogram_id}" index="0" '
        f'defaultArrayLength="{length}">'
        f'<cvParam cvRef="MS" accession="{kind_accession}" name="{kind_name}" '
        f'value=""/>'
        + "".join(cv)
        + f'<binaryDataArrayList count="{len(arrays)}">'
        + "".join(arrays)
        + "</binaryDataArrayList></chromatogram>"
    )


def _document(chromatograms: list[str]) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<mzML xmlns="http://psi.hupo.org/ms/mzml" version="1.1.0">'
        '<run id="run1" defaultInstrumentConfigurationRef="ic1">'
        f'<chromatogramList count="{len(chromatograms)}">'
        + "".join(chromatograms)
        + "</chromatogramList></run></mzML>"
    )


def _write(tmp_path: Path, text: str, name: str = "sample.mzML") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _tic_document(
    time: list[float],
    intensity: list[float],
    *,
    precision: str | None = "64",
    compression: str | None = "none",
    time_unit: tuple[str, str] | None = _MINUTE,
    intensity_unit: tuple[str, str] | None = None,
    declared: int | None = None,
    extra_cv: str = "",
) -> str:
    return _document(
        [
            _chromatogram(
                "tic",
                kind_accession=_ACC_TIC,
                kind_name="total ion current chromatogram",
                time=time,
                intensity=intensity,
                precision=precision,
                compression=compression,
                time_unit=time_unit,
                intensity_unit=intensity_unit,
                declared=declared,
                extra_cv=extra_cv,
            )
        ]
    )


# --- reading ----------------------------------------------------------------
def test_read_tic_returns_channel(tmp_path: Path) -> None:
    doc = _tic_document([0.0, 0.5, 1.0], [10.0, 20.0, 30.0])
    chrom = read_tic(_write(tmp_path, doc))

    assert chrom.kind is ChromatogramKind.TIC
    assert chrom.id == "tic"
    assert chrom.n_points == 3
    np.testing.assert_array_equal(chrom.time, [0.0, 0.5, 1.0])
    np.testing.assert_array_equal(chrom.intensity, [10.0, 20.0, 30.0])


def test_read_xic_and_target_mz(tmp_path: Path) -> None:
    doc = _document(
        [
            _chromatogram(
                "xic_521",
                kind_accession=_ACC_XIC,
                kind_name="selected ion current chromatogram",
                time=[0.0, 1.0, 2.0],
                intensity=[0.0, 5.0, 2.0],
                target_mz=521.3155,
            )
        ]
    )
    chrom = read_xic(_write(tmp_path, doc))

    assert chrom.kind is ChromatogramKind.XIC
    assert chrom.target_mz == pytest.approx(521.3155)
    np.testing.assert_array_equal(chrom.intensity, [0.0, 5.0, 2.0])


def test_read_chromatograms_returns_all_in_order(tmp_path: Path) -> None:
    doc = _document(
        [
            _chromatogram(
                "tic",
                kind_accession=_ACC_TIC,
                kind_name="total ion current chromatogram",
                time=[0.0, 1.0],
                intensity=[1.0, 2.0],
            ),
            _chromatogram(
                "xic_1",
                kind_accession=_ACC_XIC,
                kind_name="selected ion current chromatogram",
                time=[0.0, 1.0],
                intensity=[3.0, 4.0],
                target_mz=200.0,
            ),
        ]
    )
    chroms = read_chromatograms(_write(tmp_path, doc))

    assert [c.id for c in chroms] == ["tic", "xic_1"]
    assert [c.kind for c in chroms] == [
        ChromatogramKind.TIC,
        ChromatogramKind.XIC,
    ]


def test_document_without_chromatogram_list_is_empty(tmp_path: Path) -> None:
    doc = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<mzML xmlns="http://psi.hupo.org/ms/mzml" version="1.1.0">'
        '<run id="run1"></run></mzML>'
    )
    assert read_chromatograms(_write(tmp_path, doc)) == ()


def test_read_xic_by_id(tmp_path: Path) -> None:
    doc = _document(
        [
            _chromatogram(
                "xic_a",
                kind_accession=_ACC_XIC,
                kind_name="selected ion current chromatogram",
                time=[0.0],
                intensity=[1.0],
                target_mz=100.0,
            ),
            _chromatogram(
                "xic_b",
                kind_accession=_ACC_XIC,
                kind_name="selected ion current chromatogram",
                time=[0.0],
                intensity=[2.0],
                target_mz=200.0,
            ),
        ]
    )
    chrom = read_xic(_write(tmp_path, doc), chromatogram_id="xic_b")
    assert chrom.id == "xic_b"
    assert chrom.target_mz == pytest.approx(200.0)


# --- value fidelity ---------------------------------------------------------
def test_nan_intensity_is_preserved_not_zeroed(tmp_path: Path) -> None:
    doc = _tic_document([0.0, 1.0, 2.0], [1.0, float("nan"), 3.0])
    chrom = read_tic(_write(tmp_path, doc))

    assert chrom.intensity[0] == 1.0
    assert np.isnan(chrom.intensity[1])
    assert chrom.intensity[2] == 3.0
    assert not np.any(chrom.intensity == 0.0)  # a gap was not filled with a zero


def test_float32_precision_is_decoded(tmp_path: Path) -> None:
    doc = _tic_document([0.0, 1.0], [1.5, 2.5], precision="32")
    chrom = read_tic(_write(tmp_path, doc))
    np.testing.assert_allclose(chrom.intensity, [1.5, 2.5])


def test_zlib_compressed_arrays_are_decoded(tmp_path: Path) -> None:
    doc = _tic_document([0.0, 1.0, 2.0], [7.0, 8.0, 9.0], compression="zlib")
    chrom = read_tic(_write(tmp_path, doc))
    np.testing.assert_array_equal(chrom.intensity, [7.0, 8.0, 9.0])


def test_gzipped_file_is_decoded(tmp_path: Path) -> None:
    doc = _tic_document([0.0, 1.0], [4.0, 5.0])
    path = tmp_path / "sample.mzML.gz"
    with gzip.open(path, "wb") as handle:
        handle.write(doc.encode("utf-8"))
    chrom = read_tic(path)
    np.testing.assert_array_equal(chrom.intensity, [4.0, 5.0])


def test_arrays_are_read_only(tmp_path: Path) -> None:
    doc = _tic_document([0.0, 1.0], [1.0, 2.0])
    chrom = read_tic(_write(tmp_path, doc))
    with pytest.raises(ValueError):
        chrom.intensity[0] = 99.0


# --- refusal: vendor formats and other extensions ---------------------------
@pytest.mark.parametrize("suffix", [".raw", ".d", ".lcd", ".wiff"])
def test_vendor_formats_are_refused_with_conversion_guidance(
    tmp_path: Path, suffix: str
) -> None:
    path = tmp_path / f"injection{suffix}"
    path.write_bytes(b"not really a vendor file")
    with pytest.raises(UnsupportedFormatError) as excinfo:
        read_tic(path)
    message = str(excinfo.value)
    assert "MSConvert" in message
    assert suffix in message


def test_directory_named_d_is_refused_as_vendor(tmp_path: Path) -> None:
    path = tmp_path / "sample.d"
    path.mkdir()
    with pytest.raises(UnsupportedFormatError) as excinfo:
        read_tic(path)
    assert "MSConvert" in str(excinfo.value)


def test_unknown_extension_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "sample.txt"
    path.write_text("hello", encoding="utf-8")
    with pytest.raises(UnsupportedFormatError) as excinfo:
        read_tic(path)
    assert ".mzML" in str(excinfo.value)


def test_missing_file_raises_inaccessible(tmp_path: Path) -> None:
    with pytest.raises(InaccessiblePathError):
        read_tic(tmp_path / "absent.mzML")


# --- refusal: malformed mzML ------------------------------------------------
def test_non_mzml_root_is_refused(tmp_path: Path) -> None:
    doc = '<?xml version="1.0"?><notmzml><run/></notmzml>'
    with pytest.raises(MalformedFileError) as excinfo:
        read_chromatograms(_write(tmp_path, doc))
    assert "mzML" in str(excinfo.value)


def test_indexed_mzml_wrapper_is_refused_with_conversion_guidance(
    tmp_path: Path,
) -> None:
    plain = _tic_document([0.0], [1.0])
    body = plain.split("?>", maxsplit=1)[1]
    doc = (
        '<?xml version="1.0"?>'
        '<indexedmzML xmlns="http://psi.hupo.org/ms/mzml">'
        f'{body}<indexList count="1"><index name="chromatogram">'
        '<offset idRef="tic">0</offset></index></indexList>'
        "<indexListOffset>0</indexListOffset><fileChecksum>abc</fileChecksum>"
        "</indexedmzML>"
    )
    with pytest.raises(UnsupportedFormatError) as excinfo:
        read_chromatograms(_write(tmp_path, doc))
    assert "indexedmzML" in str(excinfo.value)
    assert "plain mzML" in str(excinfo.value)


def test_malformed_xml_is_refused(tmp_path: Path) -> None:
    with pytest.raises(MalformedFileError):
        read_chromatograms(_write(tmp_path, "<mzML><run>"))


def test_invalid_base64_is_refused(tmp_path: Path) -> None:
    doc = _tic_document([0.0], [1.0]).replace(_payload([1.0]), "!!!not base64!!!")
    with pytest.raises(MalformedFileError) as excinfo:
        read_tic(_write(tmp_path, doc))
    assert "base64" in str(excinfo.value)


def test_mismatched_array_lengths_are_refused(tmp_path: Path) -> None:
    doc = _document(
        [
            _chromatogram(
                "tic",
                kind_accession=_ACC_TIC,
                kind_name="total ion current chromatogram",
                time=[0.0, 1.0, 2.0],
                intensity=[1.0, 2.0],
            )
        ]
    )
    with pytest.raises(MalformedFileError):
        read_tic(_write(tmp_path, doc))


def test_declared_length_mismatch_is_refused(tmp_path: Path) -> None:
    doc = _tic_document([0.0, 1.0], [1.0, 2.0], declared=5)
    with pytest.raises(MalformedFileError):
        read_tic(_write(tmp_path, doc))


def test_chromatogram_list_count_mismatch_is_refused(tmp_path: Path) -> None:
    doc = _tic_document([0.0], [1.0]).replace(
        '<chromatogramList count="1">', '<chromatogramList count="2">'
    )
    with pytest.raises(MalformedFileError, match="<chromatogramList> count"):
        read_chromatograms(_write(tmp_path, doc))


def test_non_schema_integer_list_count_is_refused(tmp_path: Path) -> None:
    chromatograms = [
        _chromatogram(
            f"tic-{index}",
            kind_accession=_ACC_TIC,
            kind_name="total ion current chromatogram",
            time=[0.0],
            intensity=[1.0],
        )
        for index in range(10)
    ]
    doc = _document(chromatograms).replace(
        '<chromatogramList count="10">', '<chromatogramList count="1_0">'
    )
    with pytest.raises(MalformedFileError, match="<chromatogramList> count"):
        read_chromatograms(_write(tmp_path, doc))


@pytest.mark.parametrize("count", [None, "-1", "one"])
def test_invalid_chromatogram_list_count_is_refused(
    tmp_path: Path, count: str | None
) -> None:
    doc = _tic_document([0.0], [1.0])
    replacement = (
        "<chromatogramList>" if count is None else f'<chromatogramList count="{count}">'
    )
    doc = doc.replace('<chromatogramList count="1">', replacement)
    with pytest.raises(MalformedFileError, match="<chromatogramList> count"):
        read_chromatograms(_write(tmp_path, doc))


def test_binary_data_array_list_count_mismatch_is_refused(tmp_path: Path) -> None:
    doc = _tic_document([0.0], [1.0]).replace(
        '<binaryDataArrayList count="2">',
        '<binaryDataArrayList count="3">',
    )
    with pytest.raises(MalformedFileError, match="<binaryDataArrayList> count"):
        read_chromatograms(_write(tmp_path, doc))


def test_duplicate_intensity_array_is_refused(tmp_path: Path) -> None:
    duplicate = _bda(
        [9.0], array_accession=_ACC_INTENSITY, array_name="intensity array"
    )
    doc = _tic_document([0.0], [1.0]).replace(
        "</binaryDataArrayList>", f"{duplicate}</binaryDataArrayList>"
    )
    doc = doc.replace(
        '<binaryDataArrayList count="2">', '<binaryDataArrayList count="3">'
    )
    with pytest.raises(MalformedFileError, match="more than one intensity array"):
        read_chromatograms(_write(tmp_path, doc))


def test_conflicting_array_types_are_refused(tmp_path: Path) -> None:
    doc = _tic_document(
        [0.0],
        [1.0],
        extra_cv='<cvParam cvRef="MS" accession="MS:1000515" name="intensity array" value=""/>',
    )
    with pytest.raises(MalformedFileError, match="conflicting array type"):
        read_chromatograms(_write(tmp_path, doc))


def test_unresolved_referenceable_parameter_group_is_refused(tmp_path: Path) -> None:
    doc = _tic_document([0.0], [1.0]).replace(
        "<binary>", '<referenceableParamGroupRef ref="arrayParams"/><binary>', 1
    )
    with pytest.raises(UnsupportedFormatError, match="referenceableParamGroupRef"):
        read_chromatograms(_write(tmp_path, doc))


def test_missing_intensity_array_is_refused(tmp_path: Path) -> None:
    doc = _document(
        [
            _chromatogram(
                "tic",
                kind_accession=_ACC_TIC,
                kind_name="total ion current chromatogram",
                time=[0.0, 1.0],
                intensity=None,
            )
        ]
    )
    with pytest.raises(MalformedFileError) as excinfo:
        read_tic(_write(tmp_path, doc))
    assert "intensity" in str(excinfo.value)


def test_missing_precision_is_refused(tmp_path: Path) -> None:
    doc = _tic_document([0.0, 1.0], [1.0, 2.0], precision=None)
    with pytest.raises(MalformedFileError) as excinfo:
        read_tic(_write(tmp_path, doc))
    assert "precision" in str(excinfo.value)


def test_seconds_are_converted_and_source_axis_is_retained(tmp_path: Path) -> None:
    doc = _tic_document(
        [0.0, 30.0, 60.0],
        [1.0, 2.0, 3.0],
        time_unit=("UO:0000010", "second"),
    )
    chrom = read_tic(_write(tmp_path, doc))
    np.testing.assert_array_equal(chrom.time, [0.0, 0.5, 1.0])
    np.testing.assert_array_equal(chrom.source_time, [0.0, 30.0, 60.0])
    assert chrom.source_time.dtype == np.dtype("float64")
    assert chrom.source_time_unit_accession == "UO:0000010"
    assert chrom.source_time_unit_name == "second"
    assert chrom.source_time_unit_cv_ref == "UO"
    assert chrom.time_conversion_factor == 1.0 / 60.0
    with pytest.raises(ValueError):
        chrom.source_time[0] = 99.0
    with pytest.raises(ValueError):
        chrom.time[0] = 99.0


def test_minute_axis_retains_source_values_and_identity_conversion(
    tmp_path: Path,
) -> None:
    chrom = read_tic(_write(tmp_path, _tic_document([0.0, 0.5], [1.0, 2.0])))
    np.testing.assert_array_equal(chrom.source_time, [0.0, 0.5])
    assert chrom.source_time_unit_accession == "UO:0000031"
    assert chrom.source_time_unit_name == "minute"
    assert chrom.time_conversion_factor == 1.0


@pytest.mark.parametrize(
    "unit",
    [None, ("", "minute"), ("UO:0000028", "millisecond"), ("UO:9999999", "unknown")],
)
def test_missing_or_unsupported_time_units_are_refused(
    tmp_path: Path, unit: tuple[str, str] | None
) -> None:
    doc = _tic_document([0.0, 30.0, 60.0], [1.0, 2.0, 3.0], time_unit=unit)
    with pytest.raises(UnsupportedFormatError, match=r"time.*unit"):
        read_tic(_write(tmp_path, doc))


@pytest.mark.parametrize(
    "unit, expected",
    [
        (("UO:0000269", "absorbance unit"), "absorbance unit"),
        (("CUSTOM:123", "instrument response"), "instrument response"),
        (("CUSTOM:123", ""), "CUSTOM:123"),
        (None, "unknown"),
    ],
)
def test_intensity_unit_metadata_is_retained_without_conversion(
    tmp_path: Path, unit: tuple[str, str] | None, expected: str
) -> None:
    doc = _tic_document([0.0, 1.0], [1.0, 2.0], intensity_unit=unit)
    chrom = read_tic(_write(tmp_path, doc))
    np.testing.assert_array_equal(chrom.intensity, [1.0, 2.0])
    assert chrom.intensity_unit == expected
    assert chrom.intensity_unit_accession == (unit[0] if unit else None)
    assert chrom.intensity_unit_name == (unit[1] if unit else None)
    assert chrom.intensity_unit_cv_ref == ("UO" if unit else None)


def test_numpress_is_refused(tmp_path: Path) -> None:
    numpress_cv = (
        '<cvParam cvRef="MS" accession="MS:1002312" '
        'name="MS-Numpress linear prediction compression" value=""/>'
    )
    doc = _tic_document([0.0, 1.0], [1.0, 2.0], extra_cv=numpress_cv)
    with pytest.raises(UnsupportedFormatError) as excinfo:
        read_tic(_write(tmp_path, doc))
    assert "Numpress" in str(excinfo.value)


# --- channel resolution -----------------------------------------------------
def test_no_tic_channel_raises_channel_resolution(tmp_path: Path) -> None:
    doc = _document(
        [
            _chromatogram(
                "xic_1",
                kind_accession=_ACC_XIC,
                kind_name="selected ion current chromatogram",
                time=[0.0],
                intensity=[1.0],
            )
        ]
    )
    with pytest.raises(ChannelResolutionError):
        read_tic(_write(tmp_path, doc))


def test_ambiguous_xic_requires_id(tmp_path: Path) -> None:
    doc = _document(
        [
            _chromatogram(
                "xic_a",
                kind_accession=_ACC_XIC,
                kind_name="selected ion current chromatogram",
                time=[0.0],
                intensity=[1.0],
            ),
            _chromatogram(
                "xic_b",
                kind_accession=_ACC_XIC,
                kind_name="selected ion current chromatogram",
                time=[0.0],
                intensity=[2.0],
            ),
        ]
    )
    with pytest.raises(ChannelResolutionError):
        read_xic(_write(tmp_path, doc))


# --- source identity (F2) ---------------------------------------------------
def test_the_snapshot_hash_describes_the_parsed_bytes(tmp_path: Path) -> None:
    path = _write(tmp_path, _tic_document([0.0, 1.0], [10.0, 20.0]))
    snapshot, chroms = read_chromatograms_with_source(path)

    raw = path.read_bytes()
    assert snapshot.sha256 == hashlib.sha256(raw).hexdigest()
    assert snapshot.n_bytes == len(raw)
    assert snapshot.path == str(path)
    assert chroms[0].n_points == 2


def test_a_replaced_file_cannot_yield_the_other_version(tmp_path: Path) -> None:
    """One call's hash identifies that call's numbers — the defect F2 reported.

    The review reproduced a measurement of 10.0 returned with the hash of a file
    whose peak was 90.0.  Reading the path twice now ties each result to the
    bytes it was parsed from; the assertion is on both directions, so a stale or
    future hash fails it either way.
    """
    path = _write(tmp_path, _tic_document([0.0, 1.0], [10.0, 10.0]))
    first, first_chroms = read_chromatograms_with_source(path)
    first_bytes = path.read_bytes()
    assert float(first_chroms[0].intensity.max()) == 10.0

    path.write_text(_tic_document([0.0, 1.0], [90.0, 90.0]), encoding="utf-8")
    second, second_chroms = read_chromatograms_with_source(path)

    assert float(second_chroms[0].intensity.max()) == 90.0
    assert second.sha256 != first.sha256
    assert first.sha256 == hashlib.sha256(first_bytes).hexdigest()
    assert second.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


def test_a_file_changed_while_being_read_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A moving input issues no evidence rather than a guessed identity."""
    path = _write(tmp_path, _tic_document([0.0, 1.0], [10.0, 20.0]))
    real_fstat = os.fstat
    calls = {"n": 0}

    class _Stat:
        def __init__(self, size: int, mtime_ns: int, inode: int) -> None:
            self.st_size = size
            self.st_mtime_ns = mtime_ns
            self.st_ino = inode

    def moving_fstat(fd: int) -> _Stat:
        result = real_fstat(fd)
        calls["n"] += 1
        # The second look sees a later mtime: the file moved under the read.
        return _Stat(
            result.st_size,
            result.st_mtime_ns + (1 if calls["n"] == 2 else 0),
            result.st_ino,
        )

    monkeypatch.setattr(mzml, "fstat", moving_fstat)
    with pytest.raises(SourceChangedError):
        read_chromatograms_with_source(path)
    assert calls["n"] == 2


def test_a_gzipped_file_is_hashed_as_stored(tmp_path: Path) -> None:
    """The hash is of the file's own bytes, not of the decompressed document."""
    text = _tic_document([0.0, 1.0], [10.0, 20.0])
    path = tmp_path / "sample.mzML.gz"
    path.write_bytes(gzip.compress(text.encode("utf-8")))

    snapshot, chroms = read_chromatograms_with_source(path)

    assert snapshot.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert chroms[0].n_points == 2

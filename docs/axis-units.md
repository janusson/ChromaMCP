# Axis units and the A3 repair

Primary format sources were read on 2026-10-26. These rules describe this
reader's supported subset; they do not assert that an entire source document
meets the mzML schema or controlled vocabulary rules.

- [HUPO-PSI mzML 1.1.0 schema, CVParamType](https://raw.githubusercontent.com/HUPO-PSI/mzML/33340a8cdb7ef441e290272d5895d17cc258c5e7/schema/schema_1.1/mzML1.1.0.xsd)
  declares `unitAccession`, `unitName`, and `unitCvRef` as optional attributes.
  They respectively identify a unit term, supply its name, and refer to its
  vocabulary in the file. The schema does not prescribe minutes when these
  attributes are absent. Consulted bytes: SHA-256
  `141877fd774653617ad1c067533bc74d51e63fb9f19f78558faff50a3e14a206`.
- [HUPO-PSI PSI-MS controlled vocabulary, version 4.2.12](https://raw.githubusercontent.com/HUPO-PSI/psi-ms-CV/1fa9ad2daa95f9c2ee3bc2c373435c30173d6df3/psi-ms.obo)
  associates `MS:1000595` (time array) with `UO:0000010` (second) and
  `UO:0000031` (minute). Its minute definition is: “A time unit which is equal
  to 60 seconds.” The same vocabulary associates `MS:1000515` (intensity
  array) with multiple units, including `UO:0000269` (absorbance unit),
  `MS:1000131` (number of detector counts), and `MS:1000814` (counts per second).
  It provides no basis for interpreting every intensity array as counts.
  Consulted bytes: SHA-256
  `b3edca8427e684766ace537ee51851fce51ae5993774b97615527271ada99486`.
  Vocabulary attribution: HUPO Proteomics Standards Initiative, CC BY 4.0;
  [licence](https://creativecommons.org/licenses/by/4.0/).

The reader requires an explicit supported time `unitAccession`. A unit name
alone is insufficient, including the name `minute`. No rule was found in these
sources that supports a default time unit when the accession is absent; that
case is refused. A second array is multiplied by `1/60`; a minute array uses
factor `1`. These are unit definitions, with no estimator tolerance added.
The resulting `time` array is in minutes. The original decoded `source_time`
array, the three source time-unit attributes, and `time_conversion_factor`
remain available for provenance. Both time arrays are read-only float64.

Intensity values are not converted. All three source intensity-unit attributes
are retained as opaque metadata, including unfamiliar accessions or names.
The display label uses the source name, otherwise the accession, otherwise
`unknown`. Retaining a label does not establish its dimensional correctness or
its membership in a vocabulary. No unit is inferred from chromatogram kind.
`peak_height` accepts an explicit `intensity_unit` label and otherwise reports
`unknown`. `peak_area` requires its time grid in minutes, and combines the same
label with `·min`; with no label it reports `unknown·min`. A caller supplying
seconds directly to that pure metric must convert its grid first.

Synthetic regression cases exercise no time unit, an unsupported time unit,
seconds, minutes, absorbance, arbitrary opaque intensity metadata, missing
intensity metadata, and height/area unit labels. The absence of units is not
replaced with a numerical zero or a detector convention.

# Fixture estimator disagreement replay

Domain: `synthetic-w4-w12-v1`. Independent dense grid: 1e-5 min.
Working grids: 0.002 and 0.001 min; Gaussian noise SD: 0.002 of height.
Seeds: 20261011, 20261012, 20261013, 20261014, 20261015, 20261016, 20261017, 20261018.
All comparisons are serial; no domain inference is made for caller traces.
The %RSD route is the same fixed positive-response vector in every case.
The S/N blank is shared by the two routes (seed 990001, 20x width).

| Metric | Noiseless maximum | Noisy maximum | 2x noisy maximum | Worst rate | Worst seed | Historical reference bound |
|---|---|---|---|---|---|---|
| capacity_factor | 9.010126e-12 | 3.265915e-03 | 6.531829e-03 | 0.002 | 20261016 | 1.000000e-02 |
| peak_area | 2.214575e-16 | 9.968660e-04 | 1.993732e-03 | 0.002 | 20261011 | 2.000000e-03 |
| peak_height | 1.136868e-13 | 3.301640e-03 | 6.603281e-03 | 0.002 | 20261011 | 1.000000e-02 |
| peak_to_valley | 2.501779e-04 | 9.208243e-03 | 1.841649e-02 | 0.001 | 20261011 | 2.000000e-02 |
| plate_number | 1.105854e-04 | 9.369774e-03 | 1.873955e-02 | 0.002 | 20261018 | 2.000000e-02 |
| resolution | 5.713995e-05 | 2.393439e-02 | 4.786879e-02 | 0.002 | 20261014 | 5.000000e-02 |
| rsd_replicates | 0.000000e+00 | 0.000000e+00 | not-derived | 0.002 | 20261011 | 1.000000e-12 |
| selectivity | 1.449126e-08 | 6.936897e-03 | 1.387379e-02 | 0.002 | 20261014 | 1.500000e-02 |
| signal_to_noise | 1.137597e-13 | 3.301640e-03 | 6.603281e-03 | 0.002 | 20261011 | 1.000000e-02 |
| symmetry_factor | 1.120081e-04 | 2.379721e-02 | 4.759443e-02 | 0.001 | 20261015 | 5.000000e-02 |

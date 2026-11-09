Analysis set: first 61 tasks of the prereg order (37 fastapi, 24 rich), 183 units per config. Excluded (incomplete at stop): fastapi_14448 (1/9)

| config | solved units | solve rate | tool calls | tokens (k) | minutes | units reading a gold file | agent steps to first gold read (median) |
|---|---|---|---|---|---|---|---|
| B0 | 13/183 | 7.1% | 9.3 | 102 | 6.7 | 116/183 | 1 |
| B1 | 12/183 | 6.6% | 11.6 | 127 | 7.5 | 126/183 | 2 |
| B2 | 16/183 | 8.7% | 11.7 | 129 | 8.1 | 133/183 | 1 |

| comparison | effect (pp) | 95% CI (pp) | discordant (a only / b only) | McNemar p | Holm p |
|---|---|---|---|---|---|
| B2-B0 | +1.6 | [-4.4, +8.2] | 11 / 8 | 0.648 | 0.848 |
| B2-B1 | +2.2 | [-3.3, +8.2] | 9 / 5 | 0.424 | 0.848 |
| B1-B0 (secondary) | -0.5 | [-4.4, +2.7] | 6 / 7 | 1.000 | – |

| failure | B0 | B1 | B2 |
|---|---|---|---|
| resolved | 13 | 12 | 16 |
| harness_error | 0 | 2 | 3 |
| no_patch | 26 | 15 | 23 |
| broken_syntax | 27 | 19 | 30 |
| broken_import | 17 | 21 | 16 |
| hang | 6 | 7 | 2 |
| tests_fail | 94 | 107 | 93 |

Per-repo solved units: B0 fastapi 9/111, rich 4/72; B1 fastapi 6/111, rich 6/72; B2 fastapi 13/111, rich 3/72
B2 by hint confidence: high 11/54 units, low 5/129 units

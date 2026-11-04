| A | B | metric | n | A only | B only | p (exact) |
|---|---|---|---|---|---|---|
| c4 | grep | file@5 | 128 | 31 | 15 | 0.026 |
| c4 | grep | file@10 | 128 | 33 | 10 | 0.001 |
| c4 | bm25 | file@5 | 128 | 18 | 11 | 0.265 |
| c4 | bm25 | file@10 | 128 | 16 | 11 | 0.442 |
| c4 | c4_released | file@5 | 128 | 10 | 12 | 0.832 |
| c4 | c4_released | file@10 | 128 | 6 | 12 | 0.238 |
| repaired_2hop | released_2hop | sym_2hop@5 | 128 | 22 | 3 | 0.000 |
| repaired_2hop | released_2hop | file@5 | 128 | 14 | 6 | 0.115 |

| C4 top file == BM25 top file | n | C4 file Hit@1 |
|---|---|---|
| True | 42 | 20/42 (47.6%) |
| False | 86 | 19/86 (22.1%) |

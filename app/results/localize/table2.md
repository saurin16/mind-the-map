# Table 2: model-free localization (leave-one-repo-out for C4)

| method | fold | n | file@1 | file@5 | file@10 | sym@1 | sym@5 | sym@10 | sym_2hop@5 |
|---|---|---|---|---|---|---|---|---|---|
| grep | fastapi | 66 | 25.8 | 56.1 | 60.6 | – | – | – | – |
| grep | httpx | 1 | 100.0 | 100.0 | 100.0 | – | – | – | – |
| grep | requests | 13 | 61.5 | 84.6 | 84.6 | – | – | – | – |
| grep | rich | 48 | 18.8 | 29.2 | 43.8 | – | – | – | – |
| grep | all | 128 | 27.3 | 49.2 | 57.0 | – | – | – | – |
| bm25 | fastapi | 66 | 27.3 | 53.0 | 72.7 | 19.7 | 39.4 | 47.0 | 72.7 |
| bm25 | httpx | 1 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| bm25 | requests | 13 | 69.2 | 92.3 | 100.0 | 23.1 | 61.5 | 69.2 | 92.3 |
| bm25 | rich | 48 | 14.6 | 50.0 | 60.4 | 12.5 | 33.3 | 43.8 | 75.0 |
| bm25 | all | 128 | 27.3 | 56.2 | 71.1 | 18.0 | 39.8 | 48.4 | 75.8 |
| released_2hop | fastapi | 66 | 18.2 | 39.4 | 45.5 | 9.1 | 16.7 | 22.7 | 45.5 |
| released_2hop | httpx | 1 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| released_2hop | requests | 13 | 53.8 | 61.5 | 61.5 | 30.8 | 38.5 | 38.5 | 69.2 |
| released_2hop | rich | 48 | 37.5 | 43.8 | 45.8 | 18.8 | 35.4 | 37.5 | 54.2 |
| released_2hop | all | 128 | 29.7 | 43.8 | 47.7 | 15.6 | 26.6 | 30.5 | 51.6 |
| repaired_2hop | fastapi | 66 | 19.7 | 36.4 | 43.9 | 9.1 | 21.2 | 27.3 | 59.1 |
| repaired_2hop | httpx | 1 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| repaired_2hop | requests | 13 | 53.8 | 69.2 | 69.2 | 38.5 | 53.8 | 61.5 | 69.2 |
| repaired_2hop | rich | 48 | 39.6 | 62.5 | 68.8 | 20.8 | 37.5 | 39.6 | 75.0 |
| repaired_2hop | all | 128 | 31.2 | 50.0 | 56.2 | 17.2 | 31.2 | 35.9 | 66.4 |
| c4_released | fastapi | 66 | 24.2 | 56.1 | 75.8 | 7.6 | 25.8 | 37.9 | 81.8 |
| c4_released | httpx | 1 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| c4_released | requests | 13 | 69.2 | 92.3 | 92.3 | 23.1 | 46.2 | 69.2 | 84.6 |
| c4_released | rich | 48 | 31.2 | 64.6 | 81.2 | 6.2 | 22.9 | 37.5 | 83.3 |
| c4_released | all | 128 | 32.0 | 63.3 | 79.7 | 9.4 | 27.3 | 41.4 | 82.8 |
| c4 | fastapi | 66 | 22.7 | 56.1 | 69.7 | 6.1 | 30.3 | 43.9 | 75.8 |
| c4 | httpx | 1 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| c4 | requests | 13 | 53.8 | 92.3 | 92.3 | 23.1 | 61.5 | 69.2 | 92.3 |
| c4 | rich | 48 | 33.3 | 60.4 | 77.1 | 10.4 | 27.1 | 37.5 | 81.2 |
| c4 | all | 128 | 30.5 | 61.7 | 75.0 | 10.2 | 32.8 | 44.5 | 79.7 |

## Verifiable subset (98 tasks)

| method | fold | n | file@1 | file@5 | file@10 | sym@1 | sym@5 | sym@10 | sym_2hop@5 |
|---|---|---|---|---|---|---|---|---|---|
| grep | fastapi | 59 | 25.4 | 55.9 | 59.3 | – | – | – | – |
| grep | rich | 38 | 15.8 | 28.9 | 44.7 | – | – | – | – |
| grep | all | 97 | 21.6 | 45.4 | 53.6 | – | – | – | – |
| bm25 | fastapi | 59 | 28.8 | 52.5 | 69.5 | 18.6 | 39.0 | 47.5 | 76.3 |
| bm25 | rich | 38 | 13.2 | 47.4 | 55.3 | 13.2 | 34.2 | 42.1 | 73.7 |
| bm25 | all | 97 | 22.7 | 50.5 | 63.9 | 16.5 | 37.1 | 45.4 | 75.3 |
| released_2hop | fastapi | 59 | 18.6 | 39.0 | 45.8 | 10.2 | 16.9 | 22.0 | 45.8 |
| released_2hop | rich | 38 | 39.5 | 44.7 | 44.7 | 18.4 | 34.2 | 36.8 | 57.9 |
| released_2hop | all | 97 | 26.8 | 41.2 | 45.4 | 13.4 | 23.7 | 27.8 | 50.5 |
| repaired_2hop | fastapi | 59 | 20.3 | 35.6 | 44.1 | 10.2 | 20.3 | 27.1 | 59.3 |
| repaired_2hop | rich | 38 | 39.5 | 60.5 | 65.8 | 18.4 | 36.8 | 36.8 | 73.7 |
| repaired_2hop | all | 97 | 27.8 | 45.4 | 52.6 | 13.4 | 26.8 | 30.9 | 64.9 |
| c4_released | fastapi | 59 | 25.4 | 57.6 | 72.9 | 8.5 | 27.1 | 39.0 | 83.1 |
| c4_released | rich | 38 | 28.9 | 60.5 | 76.3 | 5.3 | 18.4 | 31.6 | 81.6 |
| c4_released | all | 97 | 26.8 | 58.8 | 74.2 | 7.2 | 23.7 | 36.1 | 82.5 |
| c4 | fastapi | 59 | 20.3 | 54.2 | 67.8 | 6.8 | 30.5 | 44.1 | 74.6 |
| c4 | rich | 38 | 34.2 | 57.9 | 73.7 | 10.5 | 23.7 | 34.2 | 81.6 |
| c4 | all | 97 | 25.8 | 55.7 | 70.1 | 8.2 | 27.8 | 40.2 | 77.3 |

## LORO choices

- held out fastapi (repaired): alpha=0.7 mix=1.0 types=calls+contains (train file@5 0.7903)
- held out httpx (repaired): alpha=0.7 mix=1.0 types=calls+contains (train file@5 0.6693)
- held out requests (repaired): alpha=0.7 mix=1.0 types=calls+contains (train file@5 0.6435)
- held out rich (repaired): alpha=0.3 mix=1.0 types=calls+contains (train file@5 0.625)
- held out fastapi (released): alpha=0.7 mix=0.5 types=calls (train file@5 0.7742)
- held out httpx (released): alpha=0.7 mix=0.5 types=calls (train file@5 0.6614)
- held out requests (released): alpha=0.7 mix=0.5 types=calls (train file@5 0.6348)
- held out rich (released): alpha=0.7 mix=1.0 types=calls (train file@5 0.675)

## Calibration (C4, held-out predictions): confidence bin → file Hit@1

| confidence | n | file Hit@1 |
|---|---|---|
| 0.0–0.2 | 0 | – |
| 0.2–0.4 | 99 | 32.3 |
| 0.4–0.6 | 27 | 22.2 |
| 0.6–0.8 | 2 | 50.0 |
| 0.8–1.0 | 0 | – |

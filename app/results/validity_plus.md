| repo | tasks | verifiable | gold fails | empty passes | no empty run |
|---|---|---|---|---|---|
| fastapi | 67 | 60 | 5 | 2 | 0 |
| httpx | 1 | 0 | 1 | 0 | 0 |
| requests | 13 | 0 | 10 | 3 | 0 |
| rich | 48 | 38 | 9 | 1 | 0 |
| all | 129 | 98 | 25 | 6 | 0 |

Gold-patch failure reasons:

- tests fail with gold patch: 22
- harness: Required test node did not pass: test_model_description_escaped_with_f: 1
- env: AttributeError: module 'httpx' has no attribute 'Stream': 1
- harness: Required test node did not pass: test_traceback_finely_grained_missing: 1

| repo | tasks | verifiable | gold fails | empty passes | no empty run |
|---|---|---|---|---|---|
| fastapi | 67 | 1 | 66 | 0 | 0 |
| httpx | 1 | 0 | 1 | 0 | 0 |
| requests | 13 | 0 | 10 | 3 | 0 |
| rich | 48 | 38 | 9 | 1 | 0 |
| all | 129 | 39 | 86 | 4 | 0 |

Gold-patch failure reasons:

- env: missing wheel `typing_inspection`: 62
- tests fail with gold patch: 9
- env: missing wheel `pytest-httpbin`: 8
- env: missing wheel `dirty_equals`: 4
- env: AttributeError: module 'httpx' has no attribute 'Stream': 1
- env: missing wheel `attr`: 1
- harness: Required test node did not pass: test_traceback_finely_grained_missing: 1

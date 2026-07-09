# `tests/e2e/` — End-to-End Tests

Full-stack end-to-end tests that may require ML dependencies, running containers, or GPU hardware.

---

## Test Files

| File | Description |
|---|---|
| `test_placeholder.py` | Placeholder test validating that the E2E test infrastructure and pytest discovery are working correctly. |

---

## Notes

- E2E tests are separated from unit and integration tests because they may have heavier requirements (PyTorch, vLLM containers, GPU access).
- Use `scripts/smoke_test_hosting.py` for manual E2E validation of the full hosting pipeline.
- Future E2E tests will cover: full register → deploy → chat → unload workflows against real backends.

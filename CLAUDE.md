# dishka-autogen

Integration of [Dishka](https://github.com/reagento/dishka) DI framework with [AG2](https://github.com/ag2ai/ag2) agent framework.

## Project structure

```
src/dishka_autogen/
  _consts.py      # Constants: container keys, hidden Context parameter, CurrentContainer alias
  _container.py   # Container getters from AG2 Context
  _injectors.py   # inject() decorator using wrap_injection + fast_depends
  _middleware.py   # DishkaMiddleware: on_turn (SESSION) + on_tool_execution (REQUEST)
  autogen.py      # AG2Provider, public re-exports
  __init__.py     # Public API: AG2Provider, DishkaMiddleware, FromDishka, inject
```

## Commands

- `just linter` — ruff format + ruff check + codespell
- `just mypy` — strict mypy check
- `uv run pytest tests/ -v` — run all tests
- `uv run pytest tests/unit -v` — unit tests only
- `uv run pytest tests/integration -v` — integration tests only

## Architecture

AG2 uses `fast_depends` for DI. The `inject()` decorator adds a hidden `___dishka_context` parameter (annotated with AG2's `Context`), which `fast_depends` auto-injects. The `container_getter` extracts the Dishka container from `context.dependencies`.

### Scope mapping

| Dishka Scope     | AG2 Hook            | Container stored in                         |
|------------------|---------------------|---------------------------------------------|
| `Scope.APP`      | —                   | Root container passed to middleware          |
| `Scope.SESSION`  | `on_turn`           | `context.dependencies["dishka_session_container"]` |
| `Scope.REQUEST`  | `on_tool_execution` | `context.dependencies["dishka_container"]`  |

`on_tool_execution` creates REQUEST from SESSION (if available) or APP (fallback).

### AG2Provider context types

- `BaseEvent` — available at SESSION scope (initial turn event)
- `Context` — available at SESSION scope
- `ToolCallEvent` — available at REQUEST scope

## Test structure

```
tests/
  common.py           # Shared: dep types (AppDep, SessionDep, RequestDep), AppProvider, DummyStream
  conftest.py         # Shared fixtures: app_provider, make_context, make_tool_call
  unit/
    conftest.py       # create_ag2_env() context manager
    test_middleware.py # Scope lifecycle: REQUEST, SESSION, APP, cleanup
    test_errors.py    # Error cases: wrong container type, missing middleware
  integration/
    test_agent.py     # Full agent.ask() flow via TestConfig
```

## Code style

- Python 3.10+, strict mypy, ruff with `ALL` rules
- No public exports of internal constants (`CONTAINER_NAME`, `SESSION_CONTAINER_NAME`)
- Tests may import from `dishka_autogen._consts` (allowed via `PLC2701` in ruff.toml)

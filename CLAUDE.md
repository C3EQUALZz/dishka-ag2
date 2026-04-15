# dishka-ag2

Integration of [Dishka](https://github.com/reagento/dishka) DI framework with [AG2](https://github.com/ag2ai/ag2) agent framework.

## Project structure

```
src/dishka_ag2/
  _consts.py            # Constants: container keys and hidden Context parameter
  _types.py             # NewType wrappers and generic helper types
  _scope.py             # AG2Scope definition
  _container.py         # Container getters from AG2 Context + scope walking helpers
  _container_context.py # SESSION/REQUEST context managers around AG2 context.dependencies
  _context_getter.py    # build_context_getter: resolves Context param from func signature
  _injectors.py         # inject() decorator using dishka wrap_injection
  _middleware.py        # DishkaAsyncMiddleware / DishkaSyncMiddleware
  ag2.py                # AG2Provider, public re-exports
  __init__.py           # Public API: AG2Provider, middleware, FromDishka, inject
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

All containers share a single key `context.dependencies["dishka_container"]`. The
middleware puts the root container there on `__init__`, and each scope hook uses
save/restore: it captures the current value, overwrites with the new child
container, and restores on exit.

| AG2 scope               | AG2 Hook / lifecycle                                   | How it gets there                                      |
|-------------------------|--------------------------------------------------------|--------------------------------------------------------|
| `AG2Scope.APP`          | root container                                         | Root container set in `context.dependencies`           |
| `AG2Scope.CONVERSATION` | explicit `container(scope=AG2Scope.CONVERSATION)`      | Opened by user and passed via `dependencies`           |
| `AG2Scope.SESSION`      | `on_turn`                                              | Child of the current container                         |
| `AG2Scope.REQUEST`      | `on_tool_execution`, `on_llm_call`, `on_human_input`   | Child of SESSION, or root/current container if needed  |

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
    middleware/        # Scope lifecycle: REQUEST, SESSION, APP, cleanup
    test_errors.py    # Error cases: wrong container type, missing middleware
  integration/
    */                 # Feature-oriented packages with async/sync coverage
```

## Code style

- Python 3.10+, strict mypy, ruff with `ALL` rules
- `CONTAINER_NAME` is public for the `@agent.prompt` workaround (prompts run before middleware `__init__`)
- Tests may import from `dishka_ag2._consts` (allowed via `PLC2701` in ruff.toml)

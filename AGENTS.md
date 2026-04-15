# AGENTS.md

Guidance for coding agents working in this repository.

## Project Summary

`dishka-ag2` integrates Dishka dependency injection with AG2 beta agents.
The public API is exported from `dishka_ag2` and includes:

- `AG2Scope`
- `AG2Provider`
- `DishkaAsyncMiddleware`
- `DishkaSyncMiddleware`
- `FromDishka`
- `inject`
- `CONTAINER_NAME`
- `ConversationAsyncContainer`
- `ConversationContainer`

Use `AG2Scope`, not `dishka.Scope`, in providers and containers.

## Source Layout

```text
src/dishka_ag2/
  ag2.py                # public integration exports and AG2Provider
  __init__.py           # package public API
  _scope.py             # AG2Scope definition
  _consts.py            # container dependency keys and hidden Context parameter
  _types.py             # NewType wrappers and generic helper types
  _container.py         # container lookup and parent-scope walking helpers
  _container_context.py # SESSION/REQUEST context managers for AG2 Context
  _context_getter.py    # resolves AG2 Context from function arguments
  _injectors.py         # @inject implementation via dishka wrap_injection
  _middleware.py        # async/sync AG2 middleware
```

Keep private helpers small and purpose-specific. Prefer adding local helpers
near the feature under test instead of growing global modules.

## Scope Model

The AG2 container chain is:

```text
APP -> CONVERSATION -> SESSION -> REQUEST
```

- `AG2Scope.APP`: root container lifetime.
- `AG2Scope.CONVERSATION`: explicitly opened by user code with
  `container(scope=AG2Scope.CONVERSATION)`.
- `AG2Scope.SESSION`: opened by middleware for each `Agent.ask()` turn.
- `AG2Scope.REQUEST`: opened by `@inject` for tool calls, LLM calls, HITL,
  dynamic prompts, and response schema validators.

`CONTAINER_NAME` is a pointer to the current active container in AG2
`context.dependencies`. Scope context managers save and restore this pointer.
Do not write to Dishka private container internals.

For subagents, inject `ConversationAsyncContainer` or `ConversationContainer`
and forward it to nested `Agent.ask()`:

```python
await child_agent.ask(
    "Inspect scopes",
    dependencies={CONTAINER_NAME: conversation_container},
)
```

## Test Layout

Integration tests are feature-oriented and usually split by registration form
and by async/sync container behavior:

```text
tests/integration/
  dynamic_prompt/
    decorator/test_async.py
    decorator/test_sync.py
    argument/test_async.py
    argument/test_sync.py
  response_schema/
    decorator/test_async.py
    decorator/test_sync.py
    argument/test_async.py
    argument/test_sync.py
  hitl/
    decorator/test_async.py
    decorator/test_sync.py
    argument/test_async.py
    argument/test_sync.py
  toolkit/
    decorator/test_async.py
    decorator/test_sync.py
    argument/test_async.py
    argument/test_sync.py
  subagents/
    conversation/
    session/
```

Use local `common.py` modules for repeated test-only types/providers inside a
feature package. Avoid moving feature-specific helpers into `tests/common.py`.

## Commands

Use the project commands from `justfile`:

```sh
just linter
just mypy
just pre-commit
just pre-commit-all
```

Direct commands used in CI-style checks:

```sh
uv run --active --frozen ruff check src tests examples
uv run --active --frozen mypy
uv run --active --frozen pytest -q
```

For focused runs:

```sh
uv run --active --frozen pytest tests/unit -q
uv run --active --frozen pytest tests/integration -q
uv run --active --frozen pytest tests/integration/subagents -q
```

## Coding Rules

- Keep the public API backwards-compatible unless the task explicitly says
  otherwise.
- Do not add legacy `dishka.Scope` support. Use `AG2Scope` consistently.
- Prefer existing Dishka APIs such as `wrap_injection`.
- Do not mutate private Dishka container attributes.
- Keep async container tests and sync container tests separate.
- If a feature has multiple AG2 registration forms, test each form explicitly.
- Do not introduce global abstractions for one-off test helpers.
- Keep examples and README snippets aligned with files in `examples/`.

## Documentation

README documents user-facing behavior:

- scope mapping
- supported AG2 features
- dynamic prompts
- response schemas
- HITL hooks
- Toolkit usage
- `AG2Scope.CONVERSATION` and subagents

When adding a public feature or supported AG2 registration style, update both
tests and README.

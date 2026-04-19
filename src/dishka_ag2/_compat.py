try:
    from autogen.beta.context import ConversationContext as Context
except ImportError:  # pragma: no cover - ag2 < 0.12
    from autogen.beta.context import Context  # type: ignore[attr-defined, no-redef]

__all__ = ("Context",)

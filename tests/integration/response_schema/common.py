from dishka import Provider, provide

from dishka_ag2 import AG2Scope


class ParserService:
    def parse_int(self, content: str) -> int:
        return int(content.strip())


class SchemaProvider(Provider):
    @provide(scope=AG2Scope.APP)
    def parser(self) -> ParserService:
        return ParserService()

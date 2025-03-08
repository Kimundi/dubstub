import ast
from pathlib import Path
from types import CodeType
from typing import Any, Callable, TypeGuard

from ..source import AstConfig, Source
from ..util import regex_match
from .match_ctx import MatchContext

FUNCTIONS = [
    "parent_node_is",
    "node_is",
    "file_path_is",
    "name_is",
    "annotation_is",
    "value_is",
    "any_child_node_is",
]


class AstValidator:
    reasons: list[str]

    def __init__(self):
        self.reasons = []

    def fail(self, reason: str) -> bool:
        self.reasons = [reason]
        return False

    def is_allowed(self, node: ast.AST) -> bool:
        match node:
            case ast.Constant() if self.is_simple_constant(node, bool):
                return True
            case ast.Call() if self.is_allowed_call(node):
                return True
            case ast.BoolOp(ast.And() | ast.Or(), values) if all(self.is_allowed(value) for value in values):
                return True
            case ast.UnaryOp(ast.Not(), value) if self.is_allowed(value):
                return True
            case _:
                self.reasons.append(f"unsupported type: ast.{type(node).__name__}")
                return False

    def is_simple_constant(self, node: ast.AST, value_type: Any) -> bool:
        if not isinstance(node, ast.Constant):
            return self.fail(f"expected ast.Constant, got: {type(node).__name__}")

        if not isinstance(node.value, value_type):
            return self.fail(f"unsupported constant type: {type(node.value).__name__}")

        if node.kind is not None:
            return self.fail(f"unsupported node kind: {node.kind}")

        return True

    def is_allowed_name(self, node: ast.AST) -> TypeGuard[ast.Name]:
        if not isinstance(node, ast.Name):
            return self.fail("expected ast.Name")

        if not isinstance(node.ctx, ast.Load):
            return self.fail("expected ast.Name with ctx ast.Load")

        return True

    def is_allowed_call(self, node: ast.Call) -> bool:
        if not self.is_allowed_name(node.func):
            return self.fail("unsupported function syntax")

        if node.func.id not in FUNCTIONS:
            return self.fail("unsupported function name")

        if node.keywords or len(node.args) != 1:
            return self.fail("unsupported function signature")

        arg0 = node.args[0]
        if not self.is_simple_constant(arg0, str):
            return self.fail("unsupported function argument")
        return True


def make_pattern_eval(compiled: CodeType) -> Callable[[MatchContext], bool]:
    def inner(ctx: MatchContext) -> bool:
        class Funcs:
            @staticmethod
            def parent_node_is(pat: str) -> bool:
                return regex_match(pat, [tag.value for tag in ctx.parent_tags])

            @staticmethod
            def node_is(pat: str) -> bool:
                return regex_match(pat, [tag.value for tag in ctx.tags])

            @staticmethod
            def name_is(pat: str) -> bool:
                return ctx.name is not None and regex_match(pat, ctx.name)

            @staticmethod
            def file_path_is(pat: str) -> bool:
                return regex_match(pat, ctx.file_path)

            @staticmethod
            def annotation_is(pat: str) -> bool:
                return ctx.annotation is not None and regex_match(pat, ctx.annotation)

            @staticmethod
            def value_is(pat: str) -> bool:
                return ctx.value is not None and regex_match(pat, ctx.value)

            @staticmethod
            def any_child_node_is(pat: str) -> bool:
                return ctx.child_tags is not None and regex_match(pat, [tag.value for tag in ctx.child_tags])

        env = {func: getattr(Funcs, func) for func in FUNCTIONS}

        # pylint: disable-next=eval-used
        ret = eval(compiled, env, env)
        assert isinstance(ret, bool)
        return ret

    return inner


def parse_pattern(pattern: bool | str) -> tuple[Callable[[MatchContext], bool], ast.Expression]:
    source = Source("", Path(), AstConfig())

    if isinstance(pattern, bool):
        pattern = repr(pattern)

    parsed = source.parse_standalone_expr(f"({pattern})")
    validator = AstValidator()
    if not validator.is_allowed(parsed.body):
        raise ValueError(
            f"Pattern is not allowed to contain Python AST element: `{source.unparse(parsed)}` ({', '.join(validator.reasons)})"
        )
    compiled = compile(parsed, "<pattern>", mode="eval")
    return make_pattern_eval(compiled), parsed


class Pattern:
    pattern: Callable[[MatchContext], bool]
    _raw: bool | str
    _parsed: ast.Expression

    def __init__(self, pattern: bool | str):
        self.pattern, self._parsed = parse_pattern(pattern)
        self._raw = pattern

    def is_match(self, ctx: MatchContext) -> bool:
        return self.pattern(ctx)

    def __bool__(self):
        raise TypeError

    def get_raw(self, reformat: bool = False) -> str:
        if reformat:
            return ast.unparse(self._parsed)
        return str(self._raw)

    def __str__(self) -> str:
        return ast.unparse(self._parsed)

    def __repr__(self) -> str:
        return f"Pattern({repr(str(self))})"

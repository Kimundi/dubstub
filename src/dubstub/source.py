import ast
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

SpannedNode: TypeAlias = ast.stmt | ast.expr


@dataclass
class AstConfig:
    feature_version: tuple[int, int] | None = None
    type_comments: bool = False


class Source:
    src: bytes
    src_decoded: str
    relative_path: Path
    filename: str
    line_offsets: list[tuple[int, int]]
    config: AstConfig

    def __init__(self, src: str, relative_path: Path, config: AstConfig):
        self.src = src.encode()
        self.src_decoded = src
        self.relative_path = relative_path
        self.filename = relative_path.name
        self.line_offsets = []
        self.config = config

        offset = 0
        for line in self.src.splitlines(keepends=True):
            end = offset + len(line)
            self.line_offsets.append((offset, end))
            offset = end

        assert offset == len(self.src)

    def parse_module(self) -> ast.Module:
        module: ast.Module = ast.parse(
            self.src_decoded,
            self.filename,
            feature_version=self.config.feature_version,
            type_comments=self.config.type_comments,
        )
        assert isinstance(module, ast.Module)
        return module

    def parse_standalone_expr(self, src: str) -> ast.Expression:
        expr: ast.Expression = ast.parse(
            src,
            mode="eval",
            feature_version=self.config.feature_version,
            type_comments=self.config.type_comments,
        )
        assert isinstance(expr, ast.Expression)
        return expr

    def parse_expr(self, src: str) -> ast.expr:
        return self.parse_standalone_expr(src).body

    def unparse_offsets(
        self, node: SpannedNode, include_decorators: bool = True, verify: bool = False
    ) -> tuple[int, int]:
        # check invariants
        assert node.lineno is not None
        assert node.end_lineno is not None
        assert node.col_offset is not None
        assert node.end_col_offset is not None

        # process position data
        lineno = node.lineno - 1
        end_lineno = node.end_lineno - 1
        col_offset = node.col_offset
        end_col_offset = node.end_col_offset

        # decorators are not included in the span of a class or function,
        # so we need to manually extend the span here
        if include_decorators:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                for decorator in node.decorator_list:
                    decorator_lineno = decorator.lineno - 1
                    decorator_col_offset = decorator.col_offset

                    # check if we got a decorator on an earlier syntactic position
                    if decorator_lineno < lineno:
                        lineno = decorator_lineno
                        # NB: The prefix "@" is not covered by the expression,
                        # so we need to manually step back
                        col_offset = decorator_col_offset - 1
                        assert col_offset >= 0

        # start of syntax element
        start_offset = self.line_offsets[lineno][0] + col_offset

        # end of syntax element
        end_offset = self.line_offsets[end_lineno][0] + end_col_offset

        # check against python impl
        if verify:
            sliced = self.src[start_offset:end_offset].decode()
            unparsed = ast.get_source_segment(self.src_decoded, node)
            assert unparsed == sliced, "\n".join(
                [
                    "",
                    f"sliced:   >{sliced}<",
                    f"unparsed: >{unparsed}<",
                ]
            )

        # return start and end
        return (start_offset, end_offset)

    def unparse(self, node: ast.AST) -> str:
        return ast.unparse(node)

    def unparse_original_source(self, node: SpannedNode, verify: bool = False) -> str:
        start, end = self.unparse_offsets(node, verify=verify)
        return self.src[start:end].decode()

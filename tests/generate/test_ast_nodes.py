import ast
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent, indent

import pytest

from .. import TESTDATA


@dataclass
class Case:
    ast_type: type[ast.AST]
    raw: str
    special: str | None = None


EXPRESSIONS: list[Case] = [
    # constants
    Case(ast.Constant, r"123"),
    Case(ast.Constant, r"'hello'"),
    Case(ast.Constant, r"True"),
    Case(ast.Constant, r"..."),
    # not a constant during parse, but can be after compilation/optimization
    Case(ast.Tuple, r"(1, 2, 3)"),
    Case(ast.Call, r"frozenset((1, 2, 3))"),
    # other
    Case(ast.JoinedStr, r"f'hello{value_str!r}'"),
    Case(ast.JoinedStr, r"f'{value_str}'"),
    Case(ast.List, r"[1, 2, 3]"),
    Case(ast.Set, r"{1, 2, 3}"),
    Case(ast.Dict, r"{'a': 1, **value_dict}"),
    Case(ast.Name, r"value_int"),
    Case(ast.Starred, r"*value_list", special="ignore"),  # covered by assignment case
    #
    Case(ast.UnaryOp, r"not value_bool"),
    Case(ast.UnaryOp, r"+value_int"),
    Case(ast.UnaryOp, r"-value_int"),
    Case(ast.UnaryOp, r"~value_int"),
    #
    Case(ast.BinOp, r"value_int + value_int"),
    Case(ast.BinOp, r"value_int - value_int"),
    Case(ast.BinOp, r"value_int * value_int"),
    Case(ast.BinOp, r"value_int / value_int"),
    Case(ast.BinOp, r"value_int // value_int"),
    Case(ast.BinOp, r"value_int % value_int"),
    Case(ast.BinOp, r"value_int ** value_int"),
    Case(ast.BinOp, r"value_int << value_int"),
    Case(ast.BinOp, r"value_int >> value_int"),
    Case(ast.BinOp, r"value_int | value_int"),
    Case(ast.BinOp, r"value_int & value_int"),
    Case(ast.BinOp, r"value_int ^ value_int"),
    Case(ast.BinOp, r"value_int @ value_int", special="ignore"),  # too obscure
    #
    Case(ast.BoolOp, r"value_bool and value_bool"),
    Case(ast.BoolOp, r"value_bool or value_bool"),
    #
    Case(ast.Compare, r"value_int == value_int"),
    Case(ast.Compare, r"value_int != value_int"),
    Case(ast.Compare, r"value_int < value_int"),
    Case(ast.Compare, r"value_int <= value_int"),
    Case(ast.Compare, r"value_int > value_int"),
    Case(ast.Compare, r"value_int >= value_int"),
    Case(ast.Compare, r"value_int is value_int"),
    Case(ast.Compare, r"value_int is not value_int"),
    Case(ast.Compare, r"value_int in value_list"),
    Case(ast.Compare, r"value_int not in value_list"),
    #
    Case(ast.Call, r"func(value_int)"),
    Case(ast.Call, r"klass.func(value_int)"),
    #
    Case(ast.IfExp, r"value_int if value_bool else value_int"),
    #
    Case(ast.Attribute, r"klass.value"),
    #
    Case(ast.NamedExpr, r"(value_bool := True)"),
    #
    Case(ast.Subscript, r"value_list[0]"),
    Case(ast.Subscript, r"value_list[0:1]"),
    Case(ast.Subscript, r"value_list[0, 1]", special="ignore"),  # too obscure
    Case(ast.Subscript, r"value_list[0:1, 0:1]", special="ignore"),  # too obscure
    #
    Case(ast.ListComp, r"[value_int for value_int in value_list]"),
    Case(ast.SetComp, r"{value_int for value_int in value_list}"),
    Case(ast.GeneratorExp, r"(value_int for value_int in value_list)"),
    Case(ast.DictComp, r"{value_int: value_int for value_int in value_list}"),
    #
    Case(ast.Lambda, r"lambda x,y: ..."),
    #
    Case(ast.Yield, "yield", special="func_body"),
    Case(ast.Yield, "yield None", special="func_body"),
    Case(ast.YieldFrom, "yield from value_list", special="func_body"),
    #
    Case(ast.Await, "await x", special="async_func_body"),
]

# TODO:
# LoadCtx variations
# r"a"
# r"a = 2"
# r"del a"
# r"x.y.z"
# r"x.y.z = 2"
# r"del x.y.z"
# r"x[y]"
# r"x[y] = z"
# r"del x[y]"


@pytest.mark.parametrize("case", EXPRESSIONS)
def test_expression(case: Case):
    module = ast.parse(case.raw)
    assert len(module.body) == 1
    stmt = module.body[0]

    assert isinstance(stmt, ast.Expr)
    value = stmt.value

    assert isinstance(value, case.ast_type)


STATEMENTS: list[Case] = [
    Case(ast.Assign, r"x = value_int"),
    Case(ast.Assign, r"x = y = value_int"),
    Case(ast.Assign, r"x, y = value_list"),
    Case(ast.Assign, r"[x, y] = value_list"),
    Case(ast.Assign, r"(x, y) = value_list"),
    Case(ast.Assign, r"x, *value_list = value_list"),
    #
    *[
        Case(ast.AnnAssign, f"{dst}: int{val}")
        for dst in [
            "x",
            "(x)",
            "klass.x",
            "(klass.x)",
            "value_list[0]",
            "(value_list[0])",
        ]
        for val in [
            "",
            " = value_int",
        ]
    ],
    #
    *[
        Case(ast.AugAssign, f"{dst} {op}= value_int", special=special)
        for op, special in [
            ("+", None),
            ("-", None),
            ("*", None),
            ("/", None),
            ("//", None),
            ("%", None),
            ("**", None),
            ("<<", None),
            (">>", None),
            ("|", None),
            ("&", None),
            ("^", None),
            ("@", "ignore"),
        ]
        for dst in [
            "value_int",
            "klass.value",
            "value_list[0]",
        ]
    ],
    #
    Case(ast.Raise, "raise Error", special="raise"),
    Case(ast.Raise, "raise", special="raise"),
    #
    Case(ast.Assert, "assert value_bool"),
    Case(ast.Assert, "assert value_bool, 'err'"),
    #
    Case(ast.Delete, "del value_int"),
    Case(ast.Delete, "del klass.value"),
    Case(ast.Delete, "del value_list[0]"),
    #
    Case(ast.Pass, "pass"),
    #
    *(
        [
            Case(ast.TypeAlias, "type x[y] = v"),  # pylint: disable=no-member
            Case(ast.TypeAlias, "type x[y: z] = v"),  # pylint: disable=no-member
            Case(ast.TypeAlias, "type x[**y] = v"),  # pylint: disable=no-member
            Case(ast.TypeAlias, "type x[*y] = v"),  # pylint: disable=no-member
            Case(ast.TypeAlias, "type Tuple[*T] = tuple[*T]"),  # pylint: disable=no-member
        ]
        if sys.version_info >= (3, 12)
        else []
    ),
    *(
        [
            Case(ast.TypeAlias, "type x[y: z = u] = v"),  # pylint: disable=no-member
            Case(ast.TypeAlias, "type x[**y = u] = v"),  # pylint: disable=no-member
            Case(ast.TypeAlias, "type x[*y = u] = v"),  # pylint: disable=no-member
        ]
        if sys.version_info >= (3, 13)
        else []
    ),
    #
    Case(ast.Import, "import mod_a, mod_b.mod_ba, mod_c as mod_foo"),
    Case(ast.ImportFrom, "from .mod_b import mod_ba, ba_value as value", special="as_module"),
    #
    Case(
        ast.If,
        dedent(
            """
            if value_bool:
                import mod_a
            elif value_int:
                import mod_b
            else:
                import mod_c
            """
        ),
    ),
    Case(
        ast.For,
        dedent(
            """
            for x in value_list:
                import mod_a
            else:
                import mod_b
            """
        ),
    ),
    Case(
        ast.AsyncFor,
        dedent(
            """
            async for x in y:
                pass
            else:
                pass
            """
        ),
        special="async_func_body",
    ),
    Case(
        ast.While,
        dedent(
            """
            while not value_bool:
                import mod_a
            else:
                import mod_b
            """
        ),
    ),
    Case(ast.Break, "break", special="loop"),
    Case(ast.Continue, "continue", special="loop"),
    #
    Case(
        ast.Try,
        dedent(
            """
            try:
                import mod_a
            except Error:
                import mod_b
            except Error2 as y:
                import mod_c
            else:
                import mod_c as mod_d
            finally:
                import mod_c as mod_e
            """
        ),
    ),
    *(
        [
            Case(
                ast.TryStar,  # pylint: disable=no-member
                dedent(
                    """
                    try:
                        import mod_a
                    except* Error:
                        import mod_b
                    """
                ),
            )
        ]
        if sys.version_info >= (3, 11)
        else []
    ),
    #
    Case(
        ast.With,
        dedent(
            """
            with mgr():
                import mod_a
            """
        ),
    ),
    Case(
        ast.AsyncWith,
        dedent(
            """
            async with mgr():
                import mod_a
            """
        ),
        special="async_func_body",
    ),
    #
    *(
        [
            Case(
                ast.Match,
                dedent(
                    """
                    match value_int:
                        case 0:
                            import mod_a
                        case 1:
                            import mod_b
                        case 2:
                            import mod_c
                    """
                ),
            )
        ]
        if sys.version_info >= (3, 10)
        else []
    ),
    #
    Case(
        ast.FunctionDef,
        dedent(
            """
            @deco
            def x(a: int = value_int) -> int:
                pass
            """
        ),
    ),
    Case(
        ast.AsyncFunctionDef,
        dedent(
            """
            @deco
            async def x(a: int = value_int) -> int:
                pass
            """
        ),
    ),
    *(
        [
            Case(
                ast.FunctionDef,
                dedent(
                    """
                    @deco
                    def x[T](a: int = value_int, *args, k=value_int, **kwargs) -> int:
                        pass
                    """
                ),
            ),
            Case(
                ast.AsyncFunctionDef,
                dedent(
                    """
                    @deco
                    async def x[T](a: int = value_int, *args, k=value_int, **kwargs) -> int:
                        pass
                    """
                ),
            ),
        ]
        if sys.version_info >= (3, 12)
        else []
    ),
    Case(ast.Return, "return", special="func_body"),
    #
    Case(ast.Global, "global value_int, value_list", special="func_body"),
    Case(ast.Nonlocal, "nonlocal a, b", special="nested_func_body"),
    #
    Case(
        ast.ClassDef,
        dedent(
            """
            @class_deco
            class y(Base, metaclass=Meta, a=value_int):
                pass
            """
        ),
    ),
    *(
        [
            Case(
                ast.ClassDef,
                dedent(
                    """
                    @class_deco
                    class y[T](Base, metaclass=Meta, a=value_int):
                        pass
                    """
                ),
            )
        ]
        if sys.version_info >= (3, 12)
        else []
    ),
]


@pytest.mark.parametrize("case", STATEMENTS)
def test_statement(case: Case):
    module = ast.parse(case.raw)
    assert len(module.body) == 1
    stmt = module.body[0]

    assert isinstance(stmt, case.ast_type)


@pytest.mark.parametrize("case", [pytest.param(case, id=case.raw) for case in EXPRESSIONS + STATEMENTS])
def test_executable(case: Case, tmp_path: Path):  # pylint: disable=unused-argument
    root_path = tmp_path / "generated"

    shutil.copytree(TESTDATA / "ast_template", root_path)
    file_path = root_path / "file.py"
    out_path = tmp_path / "output"

    assert file_path.exists()

    content = file_path.read_text() + "\n"
    as_module = False
    raw = dedent(case.raw)

    if case.special == "func_body":
        content += dedent(
            """
            def foo():
            {}
            """
        ).format(indent(raw, "    "))
    elif case.special == "nested_func_body":
        content += dedent(
            """
            def foo():
                a = 42
                b = "asdf"
                def bar():
            {}
            """
        ).format(indent(raw, "        "))
    elif case.special == "async_func_body":
        content += dedent(
            """
            async def foo():
            {}
            """
        ).format(indent(raw, "    "))
    elif case.special == "raise":
        content += dedent(
            """
            try:
            {}
            except:
                import mod_a
            """
        ).format(indent(raw, "    "))
    elif case.special == "loop":
        content += dedent(
            """
            while False:
                import mod_a
            {}
            """
        ).format(indent(raw, "    "))
    elif case.special == "as_module":
        as_module = True
        content += f"{raw}\n"
    elif case.special == "ignore":
        pytest.skip("skipped because it is too obscure")
    else:
        content += f"{raw}\n"

    print("----------------------------------")
    print(content)
    print("----------------------------------")

    file_path.write_text(content)

    print(case.ast_type)
    print(raw)
    if as_module:
        subprocess.run(
            [sys.executable, "-m", f"{file_path.parent.name}.{file_path.stem}"],
            check=True,
            cwd=file_path.parent.parent,
        )
    else:
        subprocess.run(
            [sys.executable, str(file_path)],
            check=True,
        )

    out = subprocess.run(
        [
            sys.executable,
            "-c",
            "from dubstub import main; main()",
            "gen",
            "--input",
            str(root_path),
            "--output",
            str(out_path),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
    )

    lines = [line for line in out.stdout.splitlines() if line.strip()]
    assert all(any(l.startswith(prefix) for prefix in ("Clean", "Stub")) for l in lines), "\n" + out.stdout

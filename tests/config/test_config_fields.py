import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent

import pytest

from dubstub import generate_stubs
from dubstub.config import Config, FormatterCmd
from dubstub.config.show import fmt_config


def test_meta_configs():
    expected_tests: set[str] = set()
    for field_name in Config.get_fields():
        expected_tests.add(f"test_config_{field_name}")

    missing_tests = expected_tests - set(globals())
    assert not missing_tests


def normalize_test_src(src: str) -> str:
    return "\n".join(line for line in dedent(src).strip().splitlines() if line.strip())


def config_helper(config: Config, inp: str, expected: str, filename: str | list[str] = "file.py"):
    inp = normalize_test_src(inp)
    expected = normalize_test_src(expected)
    with TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        (tmp / "input").mkdir()
        (tmp / "output").mkdir()

        if isinstance(filename, str):
            inp_path = tmp / "input" / filename
            inp_path.write_text(inp)

            out_path = (tmp / "output" / filename).with_suffix(".pyi")

            generate_stubs(inp_path, out_path, config)
            stubbed = normalize_test_src(out_path.read_text())
        else:
            inp_path = tmp / "input"
            for fname in filename:
                (inp_path / fname).write_text(inp)

            out_path = tmp / "output"

            generate_stubs(inp_path, out_path, config)

            stubbed = ""
            for out_path_file in out_path.iterdir():
                if out_path_file.is_file():
                    stubbed += f"# {out_path_file.name}\n"
                    stubbed += out_path_file.read_text() + "\n"

            stubbed = normalize_test_src(stubbed)

    print(fmt_config(config.validate(), show_format="toml"))
    assert stubbed == expected


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        pytest.param(
            Config(
                keep_definitions=True,
            ),
            """
                def foo():
                    ...
                def _bar():
                    ...
                x = ...
                _y = ...
                x: y = ...
                _y: z = ...
                def _():
                    ...
                __special__ = ...
                _x = TypeVar('_x')
                _x: TypeAlias
                _x: TypeAlias = T
                _x: TypeAlias = TypeVar('_x')

                _A: TypeAlias = int
                _B: TypeAlias = list[_A]
                C: TypeAlias = list[_B]

                class foo:
                    ...
                class _foo:
                    ...
            """,
            id="keep-all",
        ),
        pytest.param(
            Config(
                keep_definitions=False,
            ),
            """
            """,
            id="keep-nothing",
        ),
        pytest.param(
            Config(
                keep_definitions=r"""
                    not (
                        node_is('function|variable|class') and name_is('_[^_].*')
                    )
                """,
            ),
            """
                def foo():
                    ...
                x = ...
                x: y = ...
                def _():
                    ...
                __special__ = ...

                _A: TypeAlias = int
                _B: TypeAlias = list[_A]
                C: TypeAlias = list[_B]

                class foo:
                    ...
            """,
            id="keep-no-private",
        ),
        pytest.param(
            Config(
                keep_definitions=r"""
                    not (
                        node_is('function|variable|class') and name_is('_[^_].*')
                    )
                    or annotation_is("TypeAlias")
                    or value_is("TypeVar.*")
                """,
            ),
            """
                def foo():
                    ...
                x = ...
                x: y = ...
                def _():
                    ...
                __special__ = ...
                _x = TypeVar('_x')
                _x: TypeAlias
                _x: TypeAlias = T
                _x: TypeAlias = TypeVar('_x')

                _A: TypeAlias = int
                _B: TypeAlias = list[_A]
                C: TypeAlias = list[_B]

                class foo:
                    ...
            """,
            id="keep-no-private-except-some-variables",
        ),
        pytest.param(
            Config(),
            """
                def foo():
                    ...
                x = ...
                x: y = ...
                def _():
                    ...
                __special__ = ...

                _A: TypeAlias = int
                _B: TypeAlias = list[_A]
                C: TypeAlias = list[_B]

                class foo:
                    ...
            """,
            id="keep-default",
        ),
        pytest.param(
            Config(
                profile="pyright",
            ),
            """
                def foo():
                    ...
                x = ...
                _y = ...
                x: y = ...
                _y: z = ...
                def _():
                    ...
                __special__ = ...
                _x = TypeVar('_x')
                _x: TypeAlias
                _x: TypeAlias = T
                _x: TypeAlias = TypeVar('_x')

                _A: TypeAlias = int
                _B: TypeAlias = list[_A]
                C: TypeAlias = list[_B]

                class foo:
                    ...
                class _foo:
                    ...
            """,
            id="keep-pyright",
        ),
    ],
)
def test_config_keep_definitions(config: Config, expected: str):
    config.add_implicit_none_return = False
    config_helper(
        config,
        """
            def foo():
                pass
            def _bar():
                pass
            x = 42
            _y = 42
            x: y = 42
            _y: z = 42
            def _():
                pass
            __special__ = 42
            _x = TypeVar('_x')
            _x: TypeAlias
            _x: TypeAlias = T
            _x: TypeAlias = TypeVar('_x')

            _A: TypeAlias = int
            _B: TypeAlias = list[_A]
            C: TypeAlias = list[_B]

            class foo:
                pass
            class _foo:
                pass
        """,
        expected,
    )


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        pytest.param(
            Config(
                keep_trailing_docstrings=False,
            ),
            """
            '''a'''

            x = ...
            y = ...

            class foo:
                '''a'''

                x = ...
                y = ...

            def bar():
                '''a'''

            import foo

            class e:
                ...
            """,
            id="no",
        ),
        pytest.param(
            Config(
                keep_trailing_docstrings=True,
            ),
            """
            '''a'''

            x = ...
            '''b'''

            y = ...
            '''c'''

            class foo:
                '''a'''

                x = ...
                '''b'''

                y = ...
                '''c'''

            def bar():
                '''a'''

            import foo
            '''d'''

            class e:
                ...
            '''e'''
            """,
            id="yes",
        ),
        pytest.param(
            Config(
                keep_trailing_docstrings="node_is('variable|import')",
            ),
            """
            '''a'''

            x = ...
            '''b'''

            y = ...
            '''c'''

            class foo:
                '''a'''

                x = ...
                '''b'''

                y = ...
                '''c'''

            def bar():
                '''a'''

            import foo
            '''d'''

            class e:
                ...
            """,
            id="var-or-import",
        ),
    ],
)
def test_config_keep_trailing_docstrings(config: Config, expected: str):
    config.add_implicit_none_return = False
    config.keep_unused_imports = True
    config_helper(
        config,
        """
            '''a'''

            x = 42
            '''b'''

            y = 42
            '''c'''

            class foo:
                '''a'''

                x = 42
                '''b'''

                y = 42
                '''c'''

            def bar():
                '''a'''

                x = 42
                '''b'''

                y = 42
                '''c'''

            import foo
            '''d'''

            class e:
                pass
            '''e'''
        """,
        expected,
    )


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        pytest.param(
            Config(
                add_implicit_none_return="parent_node_is('class') and name_is('__init__')",
            ),
            """
                def a():
                    ...
                def b() -> int:
                    ...
                def __init__(self):
                    ...
                class foo:
                    def c():
                        ...
                    def d() -> int:
                        ...
                    def __init__(self) -> None:
                        ...
            """,
            id="init-only",
        ),
        pytest.param(
            Config(
                add_implicit_none_return=True,
            ),
            """
                def a() -> None:
                    ...
                def b() -> int:
                    ...
                def __init__(self) -> None:
                    ...
                class foo:
                    def c() -> None:
                        ...
                    def d() -> int:
                        ...
                    def __init__(self) -> None:
                        ...
            """,
            id="all",
        ),
        pytest.param(
            Config(
                add_implicit_none_return=False,
            ),
            """
                def a():
                    ...
                def b() -> int:
                    ...
                def __init__(self):
                    ...
                class foo:
                    def c():
                        ...
                    def d() -> int:
                        ...
                    def __init__(self):
                        ...
            """,
            id="none",
        ),
    ],
)
def test_config_add_implicit_none_return(config: Config, expected: str):
    config_helper(
        config,
        """
            def a():
                pass
            def b() -> int:
                pass
            def __init__(self):
                pass
            class foo:
                def c():
                    pass
                def d() -> int:
                    pass
                def __init__(self):
                    pass
        """,
        expected,
    )


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        pytest.param(
            Config(flatten_if=True),
            """
                import a
                if TYPE_CHECKING:
                    ...

                import b
                if foo:
                    ...
                elif bar:
                    import c
                else:
                    import d
            """,
            id="yes",
        ),
        pytest.param(
            Config(flatten_if=False),
            """
                if TYPE_CHECKING:
                    import a

                if foo:
                    import b
                elif bar:
                    import c
                else:
                    import d
            """,
            id="no",
        ),
        pytest.param(
            Config(),
            """
                import a
                if TYPE_CHECKING:
                    ...
                if foo:
                    import b
                elif bar:
                    import c
                else:
                    import d
            """,
            id="default",
        ),
    ],
)
def test_config_flatten_if(config: Config, expected: str):
    config.keep_unused_imports = True
    config.keep_if_statements = True
    config_helper(
        config,
        """
            if TYPE_CHECKING:
                import a

            if foo:
                import b
            elif bar:
                import c
            else:
                import d
        """,
        expected,
    )


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        pytest.param(
            Config(keep_if_statements=False),
            """
            """,
            id="no",
        ),
        pytest.param(
            Config(keep_if_statements=True),
            """
                if TYPE_CHECKING:
                    import foo
                if FOO:
                    import bar
                elif BAR:
                    import baz
                else:
                    import qux
            """,
            id="yes",
        ),
    ],
)
def test_config_keep_if_statements(config: Config, expected: str):
    config.flatten_if = False
    config.keep_unused_imports = True
    config_helper(
        config,
        """
            if TYPE_CHECKING:
                import foo

            if FOO:
                import bar
            elif BAR:
                import baz
            else:
                import qux
        """,
        expected,
    )


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        pytest.param(
            Config(
                profile="pyright",
            ),
            """
                def a():
                    ...
                def b():
                    '''b'''
                    ...
                class c:
                    def d():
                        ...
                    def e():
                        '''e'''
                        ...

                class foo:
                    ...
                class bar:
                    x: y = ...
                class baz:
                    def x(y):
                        ...
                class abc:
                    x = ...
                class defg:
                    x: y
                    ...
                class mixed:
                    @property
                    def foo(self) -> T:
                        ...
                    bar: baz
                class nested1:
                    class nested2:
                        foo = ...
            """,
            id="pyright",
        ),
        pytest.param(
            Config(
                add_redundant_ellipsis=True,
            ),
            """
                def a():
                    ...
                def b():
                    '''b'''
                    ...
                class c:
                    def d():
                        ...
                    def e():
                        '''e'''
                        ...
                    ...

                class foo:
                    ...
                class bar:
                    x: y = ...
                    ...
                class baz:
                    def x(y):
                        ...
                    ...
                class abc:
                    x = ...
                    ...
                class defg:
                    x: y
                    ...
                class mixed:
                    @property
                    def foo(self) -> T:
                        ...
                    bar: baz
                    ...
                class nested1:
                    class nested2:
                        foo = ...
                        ...
                    ...
            """,
            id="yes",
        ),
        pytest.param(
            Config(
                add_redundant_ellipsis=False,
            ),
            """
                def a():
                    ...
                def b():
                    '''b'''
                class c:
                    def d():
                        ...
                    def e():
                        '''e'''

                class foo:
                    ...
                class bar:
                    x: y = ...
                class baz:
                    def x(y):
                        ...
                class abc:
                    x = ...
                class defg:
                    x: y
                class mixed:
                    @property
                    def foo(self) -> T:
                        ...
                    bar: baz
                class nested1:
                    class nested2:
                        foo = ...
            """,
            id="no",
        ),
    ],
)
def test_config_add_redundant_ellipsis(config: Config, expected: str):
    config.add_implicit_none_return = False
    config_helper(
        config,
        """
            def a():
                print()
            def b():
                '''b'''
                print()
            class c:
                def d():
                    print()
                def e():
                    '''e'''
                    print()

            class foo:
                pass
            class bar:
                x: y = z
            class baz:
                def x(y):
                    pass
            class abc:
                x = 1
            class defg:
                x: y
            class mixed:
                @property
                def foo(self) -> T:
                    pass
                bar: baz
            class nested1:
                class nested2:
                    foo = bar
        """,
        expected,
    )


@pytest.mark.parametrize(
    ("config", "filename", "expected"),
    [
        pytest.param(
            Config(keep_unused_imports=False),
            "file.py",
            """
                import a
                import foo.c

                import e as e1
                import foo.g as g1

                from .foo import i
                from .foo import k as k1

                import rexport as rexport
                from all import *

                class usage:
                    field: a
                    field: foo
                    field: foo.c
                    field: e1
                    field: g1
                    field: i
                    field: k1
            """,
            id="prune",
        ),
        pytest.param(
            Config(
                keep_unused_imports=r"""
                    file_path_is(".*__init__.py")
                """
            ),
            "__init__.py",
            """
                import a
                import b
                import foo.c
                import bar.d

                import e as e1
                import f as f1
                import foo.g as g1
                import bar.h as h1

                from .foo import i
                from .foo import j

                from .foo import k as k1
                from .foo import l as l1

                import rexport as rexport
                from all import *

                class usage:
                    field: a
                    field: foo
                    field: foo.c
                    field: e1
                    field: g1
                    field: i
                    field: k1
            """,
            id="prune-init",
        ),
        pytest.param(
            Config(keep_unused_imports=True),
            "file.py",
            """
                import a
                import b
                import foo.c
                import bar.d

                import e as e1
                import f as f1
                import foo.g as g1
                import bar.h as h1

                from .foo import i
                from .foo import j

                from .foo import k as k1
                from .foo import l as l1

                import rexport as rexport
                from all import *

                class usage:
                    field: a
                    field: foo
                    field: foo.c
                    field: e1
                    field: g1
                    field: i
                    field: k1
            """,
            id="keep",
        ),
    ],
)
def test_config_keep_unused_imports(config: Config, filename: str, expected: str):
    config_helper(
        config,
        """
            import a
            import b
            import foo.c
            import bar.d

            import e as e1
            import f as f1
            import foo.g as g1
            import bar.h as h1

            from .foo import i
            from .foo import j

            from .foo import k as k1
            from .foo import l as l1

            import rexport as rexport
            from all import *

            class usage:
                field: a
                field: foo
                field: foo.c
                field: e1
                field: g1
                field: i
                field: k1
        """,
        expected,
        filename=filename,
    )


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        pytest.param(
            Config(keep_variable_value=True),
            """
                x: y
                x: y = z
                x = z

                x: TypeAlias = z
                x: type = z
                x: type[Any] = z
                x: type[Foo] = z
                x: Type = z
                x: Type[Any] = z
                x: Type[Foo] = z

                x = TypeVar(...)
                x = TypeVarTuple(...)
                x = ParamSpec(...)
                x = NamedTuple(...)
                x = NewType(...)
                x = TypedDict(...)

                __all__ = [...]
                __model__ = Foo

                class Foo:
                    __all__ = [...]
                    __model__ = Foo

                x: Type[Foo].bar = z
                x = TypeVar(...).bar
            """,
            id="yes",
        ),
        pytest.param(
            Config(keep_variable_value=False),
            """
                x: y
                x: y = ...
                x = ...

                x: TypeAlias = ...
                x: type = ...
                x: type[Any] = ...
                x: type[Foo] = ...
                x: Type = ...
                x: Type[Any] = ...
                x: Type[Foo] = ...

                x = ...
                x = ...
                x = ...
                x = ...
                x = ...
                x = ...

                __all__ = ...
                __model__ = ...

                class Foo:
                    __all__ = ...
                    __model__ = ...

                x: Type[Foo].bar = ...
                x = ...
            """,
            id="no",
        ),
        pytest.param(
            Config(),
            """
                x: y
                x: y = ...
                x = ...

                x: TypeAlias = z
                x: type = z
                x: type[Any] = z
                x: type[Foo] = z
                x: Type = z
                x: Type[Any] = z
                x: Type[Foo] = z

                x = TypeVar(...)
                x = TypeVarTuple(...)
                x = ParamSpec(...)
                x = NamedTuple(...)
                x = NewType(...)
                x = TypedDict(...)

                __all__ = [...]
                __model__ = ...

                class Foo:
                    __all__ = ...
                    __model__ = Foo

                x: Type[Foo].bar = ...
                x = ...
            """,
            id="default",
        ),
    ],
)
def test_config_keep_variable_value(config: Config, expected: str):
    config.keep_definitions = True
    config_helper(
        config,
        """
            x
            x: y
            x: y = z
            x = z

            x: TypeAlias = z
            x: type = z
            x: type[Any] = z
            x: type[Foo] = z
            x: Type = z
            x: Type[Any] = z
            x: Type[Foo] = z

            x = TypeVar(...)
            x = TypeVarTuple(...)
            x = ParamSpec(...)
            x = NamedTuple(...)
            x = NewType(...)
            x = TypedDict(...)

            __all__ = [...]
            __model__ = Foo

            class Foo:
                __all__ = [...]
                __model__ = Foo

            x: Type[Foo].bar = z
            x = TypeVar(...).bar
        """,
        expected,
    )


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        pytest.param(Config(), "default", id="implicit_default"),
        pytest.param(Config(profile="default"), "default", id="explicit_default"),
        pytest.param(Config(profile="pyright"), "pyright", id="explicit_pyright"),
    ],
)
def test_config_profile(config: Config, expected: str):
    config = config.validate()
    for field in config.get_fields():
        assert config.get(field) is not None

    assert config.profile == expected


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        pytest.param(
            Config(format=True),
            """
            from x import (
                aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa,
                bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb,
            )
            """,
            id="yes",
        ),
        pytest.param(
            Config(format=False),
            """
            from x import aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
            """,
            id="no",
        ),
    ],
)
def test_config_format(config: Config, expected: str):
    config.keep_definitions = True
    config.keep_unused_imports = True
    config_helper(
        config,
        """
        from x import (
            aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa,
            bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb,
        )
        """,
        expected,
    )


DUMMY_FORMATTER = r"""\
import sys
from pathlib import Path

major, minor, executable = sys.argv[1:][:3]
print(major)
print(minor)
print(executable)

for i, arg in enumerate(sys.argv[1:][3:]):
    Path(arg).write_text(f"{major}, {minor}, {executable}, {Path(arg).name}, #{i}")
"""


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        pytest.param(
            Config(
                python_version="3.10",
                format=True,
                formatter_cmds=[
                    FormatterCmd(
                        name="foo",
                        cmdline=[
                            sys.executable,
                            "-c",
                            DUMMY_FORMATTER,
                            "${dubstub_py_major}",
                            "${dubstub_py_minor}",
                            "${dubstub_py_exe}",
                            "${dubstub_file_args}",
                        ],
                    )
                ],
            ),
            f"""
            # file1.pyi
            3, 10, {sys.executable}, file1.pyi, #0
            # file2.pyi
            3, 10, {sys.executable}, file2.pyi, #1
            """,
            id="multiple-args",
        ),
        pytest.param(
            Config(
                python_version="3.10",
                format=True,
                formatter_cmds=[
                    FormatterCmd(
                        name="foo",
                        cmdline=[
                            sys.executable,
                            "-c",
                            DUMMY_FORMATTER,
                            "${dubstub_py_major}",
                            "${dubstub_py_minor}",
                            "${dubstub_py_exe}",
                            "${dubstub_file_arg}",
                        ],
                    )
                ],
            ),
            f"""
            # file1.pyi
            3, 10, {sys.executable}, file1.pyi, #0
            # file2.pyi
            3, 10, {sys.executable}, file2.pyi, #0
            """,
            id="single-arg",
        ),
    ],
)
def test_config_formatter_cmds(config: Config, expected: str):
    config.keep_definitions = True
    config_helper(
        config,
        """
        x: y
        """,
        expected,
        filename=["file1.py", "file2.py"],
    )


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        (Config(), (sys.version_info.major, sys.version_info.minor)),
        (Config(python_version="auto"), (sys.version_info.major, sys.version_info.minor)),
        (Config(python_version="3.10"), (3, 10)),
        (Config(python_version="3.11"), (3, 11)),
        (Config(python_version="3.12"), (3, 12)),
        (Config(python_version="3.13"), (3, 13)),
    ],
)
def test_config_python_version(config: Config, expected: tuple[int, int]):
    assert config.validate().get_python_version() == expected


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        pytest.param(
            Config(add_class_attributes_from_init=True),
            """
            class Foo:
                bar: int
                def __init__(self) -> None:
                    ...

            class Bar:
                bar: str
                foo: str
                def __init__(self) -> None:
                    ...
            """,
            id="yes",
        ),
        pytest.param(
            Config(add_class_attributes_from_init=False),
            """
            class Foo:
                def __init__(self) -> None:
                    ...

            class Bar:
                bar: str
                def __init__(self) -> None:
                    ...
            """,
            id="no",
        ),
    ],
)
def test_config_add_class_attributes_from_init(config: Config, expected: str):
    config_helper(
        config,
        """
        class Foo:
            def __init__(self):
                self.foo = 1
                self.bar: int = 2

        class Bar:
            bar: str
            def __init__(self):
                self.foo: str = ""
                self.bar: int = 2
        """,
        expected,
    )

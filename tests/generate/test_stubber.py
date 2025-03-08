import ast
import sys
from pathlib import Path

import pytest

from dubstub.config import Config
from dubstub.generate.stubber import Stubber, stubgen_single_file_src
from dubstub.source import AstConfig, Source

from .. import TESTDATA

TEST_CONFIG = Config(
    # Default profile, with justified exceptions
    keep_unused_imports=True,  # don't remove imports
    keep_trailing_docstrings=True,  # include all docstrings
    add_implicit_none_return=True,  # add return types
).validate()


@pytest.mark.parametrize(
    "module",
    [pytest.param(mod, id=mod.stem) for mod in (TESTDATA / "modules").glob("*.py")],
)
def test_stubs(module: Path):
    module_content = module.read_text()
    expected_content = module.with_suffix(".pyi").read_text().rstrip() + "\n"

    if module.stem == "py312" and sys.version_info < (3, 12):
        pytest.skip()
    if module.stem == "py313" and sys.version_info < (3, 13):
        pytest.skip()

    stubbed = stubgen_single_file_src(module_content, Path(module.name), TEST_CONFIG)

    assert stubbed == expected_content


@pytest.mark.parametrize(
    "module",
    [pytest.param(mod, id=mod.stem) for mod in (TESTDATA / "modules").glob("*.py")],
)
def test_idempotence(module: Path):
    module_content = module.read_text()

    if module.stem == "py312" and sys.version_info < (3, 12):
        pytest.skip()
    if module.stem == "py313" and sys.version_info < (3, 13):
        pytest.skip()

    stubbed = stubgen_single_file_src(module_content, Path(module.name), TEST_CONFIG)
    restubbed = stubgen_single_file_src(stubbed, Path(module.name), TEST_CONFIG)

    assert stubbed == restubbed


DISCOVER_NAMES = """
import a
from b import c
import some.other
import some2.other
import some3

def d(e: f) -> g:
    ...

__all__ = ['h', 'i']
__all__ = ('j', 'k')

l: m

@q
class n(o):
    @r
    def p():
        pass

Foo: TypeAlias = Callable[["Bar"], "Baz"]
l = some.other
l = some
l = some2
l = some3
"""


def test_discover_names():
    source = Source(DISCOVER_NAMES, Path("file.py"), AstConfig())
    ast_module = source.parse_module()

    s = Stubber(source, TEST_CONFIG)
    s.discover_module_names(ast_module)
    assert s.used_names == {
        "f",
        "g",
        "h",
        "i",
        "j",
        "k",
        "l",
        "m",
        "o",
        "q",
        "r",
        "Bar",
        "Baz",
        "Callable",
        "TypeAlias",
        "Foo",
        "__all__",
        "some",
        "some2",
        "some3",
    }


@pytest.mark.parametrize(
    ("import_src", "expected"),
    [
        ("import X as X", True),
        ("import X as Y", False),
        ("import a.b.c.X as X", False),
        ("from a.b.c import X as X", True),
        ("from a.b.c import *", True),
    ],
)
def test_is_rexport(import_src: str, expected: bool):
    source = Source(import_src, Path("file.py"), AstConfig())
    ast_module = source.parse_module()

    stmt = ast_module.body[0]
    assert isinstance(stmt, ast.Import | ast.ImportFrom)

    assert len(stmt.names) == 1
    name = stmt.names[0]

    result = Stubber.import_is_export(name)
    assert result == expected, f"expected {expected} for `{import_src}`"


@pytest.mark.parametrize(
    ("import_src", "expected"),
    [
        ("import X as X", "X"),
        ("import X as Y", "Y"),
        ("import a.b.c.X as X", "X"),
        ("import a.b.c.X", "a"),
        ("import X", "X"),
        #
        ("from a.b.c import X as X", "X"),
        ("from a.b.c import *", "*"),
        ("from .foo.bar import X", "X"),
        ("from . import X", "X"),
        ("from .... import X", "X"),
    ],
)
def test_get_importesd_name(import_src: str, expected: bool):
    source = Source(import_src, Path("file.py"), AstConfig())
    ast_module = source.parse_module()

    stmt = ast_module.body[0]
    assert isinstance(stmt, ast.Import | ast.ImportFrom)

    assert len(stmt.names) == 1
    name = stmt.names[0]

    result = Stubber.get_imported_name(name)
    assert result == expected, f"expected `{import_src}` to import `{expected}`"

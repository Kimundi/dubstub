import re
from pathlib import Path

import pytest

from dubstub import toml
from dubstub.config import Config
from dubstub.config.match_ctx import MatchContext, Tag
from dubstub.config.pattern import Pattern, parse_pattern
from dubstub.util import regex_match

CONTEXT = MatchContext(
    parent_tags={Tag.CLASS},
    tags={Tag.IF},
    file_path="foo/bar",
    name="qux",
    annotation="&str",
    value="PhantomData",
    child_tags={Tag.MODULE},
)


@pytest.mark.parametrize(
    "pattern",
    [
        Pattern(True),
        Pattern('parent_node_is("class")'),
        Pattern('parent_node_is("cl.ss")'),
        Pattern('node_is("if")'),
        Pattern('node_is("i.")'),
        Pattern('name_is("qux")'),
        Pattern('name_is("q.x")'),
        Pattern('file_path_is("foo/bar")'),
        Pattern('file_path_is(".*/bar")'),
        Pattern('file_path_is("foo/.*")'),
        Pattern('annotation_is("&str")'),
        Pattern('annotation_is(".str")'),
        Pattern('value_is("PhantomData")'),
        Pattern('value_is(".*Data")'),
        Pattern('any_child_node_is("module")'),
        Pattern('any_child_node_is("mod.*e")'),
    ],
)
def test_pattern_matches(pattern: Pattern):
    assert pattern.is_match(CONTEXT)


@pytest.mark.parametrize(
    "pattern",
    [
        Pattern('parent_node_is("o")'),
        Pattern('node_is("a")'),
        Pattern('name_is("u")'),
        Pattern('file_path_is("abc/.*")'),
        Pattern('file_path_is("foo/_.*")'),
        Pattern('annotation_is("x")'),
        Pattern('value_is("y")'),
        Pattern('any_child_node_is("z")'),
    ],
)
def test_pattern_no_matches(pattern: Pattern):
    assert not pattern.is_match(CONTEXT)


def test_default_private_name_re():
    private_name = r"_[^_].*"

    assert regex_match(private_name, "_hello")
    assert regex_match(private_name, "_h_42")

    assert not regex_match(private_name, "foo")
    assert not regex_match(private_name, "f_")

    assert not regex_match(private_name, "_")
    assert not regex_match(private_name, "__")
    assert not regex_match(private_name, "__foo")
    assert not regex_match(private_name, "__foo__")


@pytest.mark.parametrize(
    "pattern",
    [
        True,
        False,
        "True",
        "False",
        "parent_node_is('.*')",
        "node_is('.*')",
        "file_path_is('.*')",
        "name_is('.*')",
        "node_is('.*') and name_is('.*') and file_path_is('.*')",
        "node_is('.*') or name_is('.*') or file_path_is('.*')",
        "node_is('.*') and name_is('.*') or file_path_is('.*')",
        "node_is('.*') or name_is('.*') and file_path_is('.*')",
        "not True",
        "not (True or False)",
        "(not True or not False)",
    ],
)
def test_parse_valid_pattern2(pattern: str | bool):
    parse_pattern(pattern)


@pytest.mark.parametrize(
    ("pattern", "message"),
    [
        pytest.param(
            "42",
            re.escape("unsupported constant type: int"),
            id="wrong-const-type",
        ),
        pytest.param(
            "foo.bar('')",
            re.escape("unsupported function syntax"),
            id="wrong-call-type",
        ),
        pytest.param(
            "bar('')",
            re.escape("unsupported function name"),
            id="wrong-call-name",
        ),
        pytest.param(
            "node_is('', x=y)",
            re.escape("unsupported function signature"),
            id="wrong-call-sig",
        ),
        pytest.param(
            "node_is(42)",
            re.escape("unsupported function argument"),
            id="wrong-call-arg",
        ),
    ],
)
def test_parse_invalid_pattern2(pattern: str | bool, message: str):
    with pytest.raises(ValueError, match=message):
        parse_pattern(pattern)


@pytest.mark.parametrize(
    ("pattern", "ctx", "expected"),
    [
        # simple case
        (True, MatchContext(set(), set(), "", None), True),
        ("True", MatchContext(set(), set(), "", None), True),
        (False, MatchContext(set(), set(), "", None), False),
        ("False", MatchContext(set(), set(), "", None), False),
        # parent
        ("parent_node_is('class')", MatchContext({Tag.CLASS}, set(), "", None), True),
        ("parent_node_is('class')", MatchContext({Tag.IF}, set(), "", None), False),
        # node
        ("node_is('class')", MatchContext(set(), {Tag.CLASS}, "", None), True),
        ("node_is('class')", MatchContext(set(), {Tag.IF}, "", None), False),
        # path
        ("file_path_is('/foo.*')", MatchContext(set(), set(), "/foo/bar", None), True),
        ("file_path_is('/foo.*')", MatchContext(set(), set(), "/bar/foo", None), False),
        # name
        ("name_is('foo')", MatchContext(set(), set(), "", "foo"), True),
        ("name_is('foo')", MatchContext(set(), set(), "", "bar"), False),
        ("name_is('foo')", MatchContext(set(), set(), "", None), False),
        # complex and
        ("node_is('class') and name_is('foo')", MatchContext(set(), {Tag.CLASS}, "", "foo"), True),
        ("node_is('class') and name_is('foo')", MatchContext(set(), {Tag.CLASS}, "", "bar"), False),
        ("node_is('class') and name_is('foo')", MatchContext(set(), {Tag.IF}, "", "foo"), False),
        # complex or
        ("node_is('class') or name_is('foo')", MatchContext(set(), {Tag.CLASS}, "", "foo"), True),
        ("node_is('class') or name_is('foo')", MatchContext(set(), {Tag.CLASS}, "", "bar"), True),
        ("node_is('class') or name_is('foo')", MatchContext(set(), {Tag.IF}, "", "foo"), True),
        # tag or
        ("node_is('class|if')", MatchContext(set(), {Tag.IF}, "", None), True),
        ("node_is('class|if')", MatchContext(set(), {Tag.CLASS}, "", None), True),
        ("node_is('class|if')", MatchContext(set(), {Tag.IF, Tag.CLASS}, "", None), True),
        ("node_is('class|if')", MatchContext(set(), {Tag.IF, Tag.CLASS, Tag.MODULE}, "", None), True),
    ],
)
def test_eval_pattern2(pattern: str | bool, ctx: MatchContext, expected: bool):
    matcher, _ = parse_pattern(pattern)
    assert matcher(ctx) == expected


CONFIG_TOML = r"""
[tool.dubstub]
profile = "pyright"
keep_definitions = "True or False"
"""

CONFIG_PARSED = toml.loads(CONFIG_TOML)


def test_parse_obj():
    config = Config.parse_config(obj=CONFIG_PARSED)

    assert config.profile == "pyright"
    assert config.keep_definitions is not None
    assert config.keep_definitions == "True or False"


def test_parse_raw():
    config = Config.parse_config(raw=CONFIG_TOML)

    assert config.profile == "pyright"
    assert config.keep_definitions is not None
    assert config.keep_definitions == "True or False"


def test_parse_path(tmp_path: Path):
    (tmp_path / "config.toml").write_text(CONFIG_TOML)

    config = Config.parse_config(path=tmp_path / "config.toml")

    assert config.profile == "pyright"
    assert config.keep_definitions is not None
    assert config.keep_definitions == "True or False"

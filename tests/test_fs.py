from pathlib import Path

import pytest

from dubstub.fs import Kind, Walker, find_module_roots


@pytest.mark.parametrize(
    ("files", "inp", "out", "expected_visited"),
    [
        pytest.param(
            [
                "file.py",
                "other.py",
                "py.typed",
                "__init__.py",
                "foo.pyi",
                "abc.def",
            ],
            "file.py",
            "foo.xyz",
            [
                ("root", ".", "file.py", "foo.xyz"),
                ("stub", ".", "file.py", "foo.xyz"),
            ],
            id="file",
        ),
        pytest.param(
            [
                "file.py",
                "other.py",
                "sub/sub/file.py",
                "sub/sub/mod/__init__.py",
                "sub/sub/mod/other.py",
                "mod/__init__.py",
                "mod/other.py",
                "x.pyi",
                "y.pyc",
                "z.abc",
                "keep.pyi",
                "py.typed",
            ],
            ".",
            ".",
            [
                ("root", ".", "file.py", "file.pyi"),
                ("stub", ".", "file.py", "file.pyi"),
                #
                ("root", ".", "mod", "mod"),
                ("stub", ".", "mod/__init__.py", "mod/__init__.pyi"),
                ("stub", ".", "mod/other.py", "mod/other.pyi"),
                #
                ("root", ".", "other.py", "other.pyi"),
                ("stub", ".", "other.py", "other.pyi"),
                #
                ("root", ".", "sub/sub/file.py", "sub/sub/file.pyi"),
                ("stub", ".", "sub/sub/file.py", "sub/sub/file.pyi"),
                #
                ("root", ".", "sub/sub/mod", "sub/sub/mod"),
                ("stub", ".", "sub/sub/mod/__init__.py", "sub/sub/mod/__init__.pyi"),
                ("stub", ".", "sub/sub/mod/other.py", "sub/sub/mod/other.pyi"),
                #
                ("root", ".", "x.pyi", "x.pyi"),
                ("copy", ".", "x.pyi", "x.pyi"),
                #
                ("root", ".", "keep.pyi", "keep.pyi"),
                ("copy", ".", "keep.pyi", "keep.pyi"),
                #
                ("root", ".", "py.typed", "py.typed"),
                ("copy", ".", "py.typed", "py.typed"),
            ],
            id="dir",
        ),
        pytest.param(
            [
                "file.py",
                "other.py",
                "sub/sub/file.py",
                "sub/sub/mod/__init__.py",
                "sub/sub/mod/other.py",
                "sub/sub/mod/keep.pyi",
                "sub/sub/mod/py.typed",
                "mod/__init__.py",
                "mod/other.py",
                "x.pyi",
                "y.pyc",
                "z.abc",
            ],
            "sub",
            "sub",
            [
                ("root", "sub", "sub/file.py", "sub/file.pyi"),
                ("stub", "sub", "sub/file.py", "sub/file.pyi"),
                #
                ("root", "sub", "sub/mod", "sub/mod"),
                ("stub", "sub", "sub/mod/__init__.py", "sub/mod/__init__.pyi"),
                ("stub", "sub", "sub/mod/other.py", "sub/mod/other.pyi"),
                ("copy", "sub", "sub/mod/keep.pyi", "sub/mod/keep.pyi"),
                ("copy", "sub", "sub/mod/py.typed", "sub/mod/py.typed"),
            ],
            id="subdir",
        ),
        pytest.param(
            [
                "__init__.py",
                "other.py",
                "keep.pyi",
                "py.typed",
            ],
            ".",
            ".",
            [
                ("root", ".", ".", "."),
                ("stub", ".", "__init__.py", "__init__.pyi"),
                ("stub", ".", "other.py", "other.pyi"),
                ("copy", ".", "keep.pyi", "keep.pyi"),
                ("copy", ".", "py.typed", "py.typed"),
            ],
            id="module",
        ),
    ],
)
# pylint: disable-next=too-many-locals
def test_walker(tmp_path: Path, files: list[str], inp: str, out: str, expected_visited: list[tuple[str, ...]]):
    inp_base = tmp_path / "input"
    out_base = tmp_path / "output"

    inp_base.mkdir()
    out_base.mkdir()

    for file in files:
        file_path = inp_base / file
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.touch()

    inp_root = inp_base / inp
    out_root = out_base / out

    walker = Walker(inp_root, out_root)

    expected: list[dict[str, str]] = [
        {
            ".kind": kind,
            "inp_rel": str(Path(rel) / i),
            "inp_pat": i,
            "out_rel": str(Path(rel) / o),
            "out_pat": o,
        }
        for kind, rel, i, o in expected_visited
    ]
    visited: list[dict[str, str]] = []
    for event in walker.walk():
        kind = event.kind.name.lower()

        visited.append(
            {
                ".kind": kind,
                "inp_rel": str(event.inp_path.relative_to(inp_base)),
                "inp_pat": event.inp_rel_pattern,
                "out_rel": str(event.out_path.relative_to(out_base)),
                "out_pat": event.out_rel_pattern,
            }
        )

    expected.sort(key=lambda e: (e["inp_rel"], e[".kind"]))
    visited.sort(key=lambda e: (e["inp_rel"], e[".kind"]))

    assert expected == visited


@pytest.mark.parametrize(
    ("files", "inp", "expected_visited"),
    [
        pytest.param(
            [
                "file.py",
                "other.py",
            ],
            "file.py",
            [
                "file.py",
            ],
            id="file",
        ),
        pytest.param(
            [
                "file.py",
                "other.py",
                "sub/sub/file.py",
                "sub/sub/mod/__init__.py",
                "sub/sub/mod/other.py",
                "mod/__init__.py",
                "mod/other.py",
                "x.pyi",
                "y.pyc",
                "z.abc",
            ],
            ".",
            [
                "file.py",
                "other.py",
                "sub/sub/file.py",
                "sub/sub/mod",
                "mod",
                "x.pyi",
            ],
            id="dir",
        ),
        pytest.param(
            [
                "file.py",
                "other.py",
                "sub/sub/file.py",
                "sub/sub/mod/__init__.py",
                "sub/sub/mod/other.py",
                "mod/__init__.py",
                "mod/other.py",
                "x.pyi",
                "y.pyc",
                "z.abc",
            ],
            "sub",
            [
                "sub/sub/file.py",
                "sub/sub/mod",
            ],
            id="subdir",
        ),
    ],
)
def test_find_module_roots(tmp_path: Path, files: list[str], inp: str, expected_visited: list[str]):
    inp_base = tmp_path / "input"

    for file in files:
        file_path = inp_base / file
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.touch()

    visited: set[str] = set()
    for root in find_module_roots(inp_base / inp):
        rel = root.relative_to(inp_base)
        visited.add(str(rel))

    assert visited == set(expected_visited)


def test_file_to_dir_output_existing(tmp_path: Path):
    (tmp_path / "file.py").touch()
    (tmp_path / "out").mkdir()

    walker = Walker(tmp_path / "file.py", tmp_path / "out")
    events = list(walker.walk())
    assert len(events) == 2

    assert events[0].kind == Kind.ROOT

    assert events[1].inp_path == tmp_path / "file.py"
    assert events[1].inp_rel_pattern == "file.py"
    assert events[1].kind == Kind.STUB
    assert events[1].out_path == tmp_path / "out" / "file.pyi"
    assert events[1].out_rel_pattern == "file.pyi"


def test_file_to_dir_output_missing(tmp_path: Path):
    (tmp_path / "file.py").touch()

    walker = Walker(tmp_path / "file.py", tmp_path / "out")
    events = list(walker.walk())
    assert len(events) == 2

    assert events[0].kind == Kind.ROOT

    assert events[1].inp_path == tmp_path / "file.py"
    assert events[1].inp_rel_pattern == "file.py"
    assert events[1].kind == Kind.STUB
    assert events[1].out_path == tmp_path / "out"
    assert events[1].out_rel_pattern == "out"

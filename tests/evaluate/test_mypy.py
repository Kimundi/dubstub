from pathlib import Path

import pytest

from dubstub.evaluate.gen_mypy import find_matching_output

INPUT1 = [
    # namespace package
    "foo",
    # normal nested package
    "foo/foo",
    "foo/foo/__init__.py",
    # normal nested package
    "foo/foo/foo",
    "foo/foo/foo/__init__.py",
    # normal single-file package
    "foo/foo/foo/foo.py",
]


def make_dir_entry(dst: Path, rel: str):
    cur = dst / rel
    if cur.suffix:
        cur.parent.mkdir(parents=True, exist_ok=True)
        cur.touch()
    else:
        cur.mkdir(parents=True, exist_ok=True)


@pytest.mark.parametrize(
    ("inp", "arg", "mypy_out", "expected_found"),
    [
        (
            INPUT1,
            ".",
            [
                "foo/foo/__init__.pyi",
                "foo/foo/foo/__init__.pyi",
                "foo/foo/foo/foo.pyi",
            ],
            ".",
        ),
        (
            INPUT1,
            ".",
            [
                "foo/foo/__init__.pyi",
                "foo/foo/foo/__init__.pyi",
                "foo/foo/foo/foo/__init__.pyi",
            ],
            ".",
        ),
        (
            INPUT1,
            "foo/foo/foo",
            [
                "foo/foo/__init__.pyi",
                "foo/foo/foo/__init__.pyi",
                "foo/foo/foo/foo.pyi",
            ],
            "foo/foo/foo",
        ),
        (
            [
                "foo/bar/baz/__init__.py",
            ],
            "foo/bar",
            [
                "foo/bar/baz.py",
            ],
            "foo/bar",
        ),
        (
            [
                "foo/bar/baz/__init__.py",
            ],
            "foo/bar/baz",
            [
                "foo/bar/baz.py",
            ],
            "foo/bar/baz",
        ),
        (
            [
                "foo/bar/baz/__init__.py",
            ],
            "foo/bar/baz",
            [
                "baz.py",
            ],
            "baz",
        ),
    ],
)
def test_find_output(tmp_path: Path, inp: list[str], arg: str, mypy_out: list[str], expected_found: str):
    inp_path = tmp_path / "inp"
    out_path = tmp_path / "out"

    for single_inp in inp:
        make_dir_entry(inp_path, single_inp)

    for single_mypy_out in mypy_out:
        make_dir_entry(out_path, single_mypy_out)

    # subprocess.run(["tree", "-a", str(tmp_path)])

    arg_path = inp_path / arg
    found = find_matching_output(arg_path, out_path)
    assert str(found) == expected_found

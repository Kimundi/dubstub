from pathlib import Path

import pytest

from dubstub.fs import walk_dir

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


def find_module_structure(path: Path) -> list[tuple[str, ...]]:
    modules: set[tuple[str, ...]] = set()

    for subpath in walk_dir(path):
        if subpath.is_file() and subpath.suffix in (".py", ".pyi"):
            if subpath.stem == "__init__":
                modules.add(tuple([*subpath.parent.relative_to(path).parts]))
            else:
                modules.add(tuple([*subpath.parent.relative_to(path).parts, subpath.stem]))

    for found in modules.copy():
        while len(found) > 0:
            found = tuple(list(found)[:-1])
            modules.add(found)

    return sorted(modules)


def evaluate_structure(expected: list[tuple[str, ...]], current: list[tuple[str, ...]]) -> tuple[float, int]:
    """
    Evaluates how much the `current` structure matches the `expected` structure.

    Return two number:
    - a float that contains a value between 0.0 and 1.0 to express how much of the expected structure exists in the current structure.
    - a integer that counts the number of extra elements in the current structure that do not exist in the expected structure.
    """

    found = 0
    extra = 0

    for exp in expected:
        if exp in current:
            found += 1
    for ext in current:
        if ext not in expected:
            extra += 1

    found_percent = float(found) / float(len(expected))

    return (found_percent, extra)


def evaluate_structures(
    expected: list[tuple[str, ...]],
    current: list[tuple[str, ...]],
    ctx: tuple[str, ...],
) -> list[tuple[float, int, tuple[str, ...]]]:
    ret: list[tuple[float, int, tuple[str, ...]]] = []

    found_percent, extra = evaluate_structure(expected, current)
    ret.append((found_percent, extra, ctx))

    child_names: set[str] = set()
    for cur in current:
        if len(cur) < 1:
            continue
        child_names.add(cur[0])

    for child_name in child_names:
        children: set[tuple[str, ...]] = set()
        for cur in current:
            if len(cur) > 0 and cur[0] == child_name:
                children.add(cur[1:])
        child_ctx = ctx + (child_name,)
        ret.extend(evaluate_structures(expected, list(children), child_ctx))

    return ret


def find_matching_output(mypy_inp_path: Path, mypy_out_path: Path) -> Path:
    """
    Given an input path to mypy, and the output directory that mypy wrote to,
    find the relative path in `mypy_out_path` that matches the directory nesting level
    at `mypy_inp_path`.

    This is needed because mypy seems to walk up in the directory tree from its
    input to discover the outermost python module, and include it in its
    entirety in the output directory tree, which makes it hard to match input
    and output 1 to 1.

    This function performs a search based on heuristics, as a python module
    could in theory contain multiple nested module structures that match the input
    path. We expect that this is not the case for most real-life code, however.
    """

    expected = find_module_structure(mypy_inp_path)
    current = find_module_structure(mypy_out_path)

    print(expected)
    print(current)
    evaluated = evaluate_structures(expected, current, ())

    weighted = sorted(evaluated, key=lambda tup: (1.0 - tup[0], tup[1]))
    for x in weighted:
        print(x)

    return Path(*weighted[0][2])


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

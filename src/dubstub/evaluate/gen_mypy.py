import subprocess
from pathlib import Path
from shutil import copy2, rmtree
from tempfile import TemporaryDirectory

from ..config import ValidatedConfig
from ..format import format_pyi_tree
from ..fs import Kind, Walker, remove, walk_dir


def generate_copy(inp: Path, out: Path):
    # in copy mode we just copy the pyi file as-is

    out.parent.mkdir(exist_ok=True, parents=True)
    copy2(inp, out)


def run_mypy(tmp: Path, dir_or_file: Path, out_dir: Path):
    subprocess.run(
        [
            "stubgen",
            "--verbose",
            # "--inspect-mode",
            "--include-docstrings",
            "-o",
            str(out_dir),
            str(dir_or_file),
        ],
        cwd=tmp,
        check=True,
    )


def find_mypy_out(inp: Path, out_name: str, mypy_out: Path) -> Path:
    candidate_paths: list[Path] = []
    candidate_path = Path(out_name)
    for part in reversed(inp.parent.parts):
        candidate_paths.append(candidate_path)
        candidate_path = Path(part) / candidate_path
    candidate_paths.reverse()

    for candidate_path in candidate_paths:
        if (mypy_out / candidate_path).exists():
            return mypy_out / candidate_path

    raise AssertionError("could not find expected files in mypy output")


def find_module_structure(path: Path) -> list[tuple[str, ...]]:
    modules: set[tuple[str, ...]] = set()

    for subpath in walk_dir(path):
        subpath_is_file = subpath.is_file()

        if subpath_is_file and subpath.suffix in (".py", ".pyi"):
            if subpath == path:
                modules.add(tuple())
            else:
                rel_parts = subpath.parent.relative_to(path).parts
                if subpath.stem == "__init__":
                    modules.add(tuple([*rel_parts]))
                else:
                    modules.add(tuple([*rel_parts, subpath.stem]))

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

    # NB: If we have zero paths, we just compute a value of 0.0
    found_percent = float(found) / float(max(len(expected), 1))

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

    # print(expected)
    # print(current)
    evaluated = evaluate_structures(expected, current, ())

    weighted = sorted(evaluated, key=lambda tup: (1.0 - tup[0], tup[1]))
    # for x in weighted:
    #    print(x)

    return Path(*weighted[0][2])


def generate_mypy(inp: Path, out: Path, is_file: bool):
    # otherwise we invoke pyright with the right base directory to do a src import from
    with TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        tmp_out = tmp / "out"
        tmp_out.mkdir()

        # call mypy
        run_mypy(tmp, inp, tmp_out)

        found_rel_path = find_matching_output(inp, tmp_out)

        print(found_rel_path)

        if is_file and inp.suffix == ".py":
            out_name = inp.with_suffix(".pyi").name
        else:
            out_name = inp.name

        gen = find_mypy_out(inp, out_name, tmp_out)

        if is_file:
            # copy to output
            out.parent.mkdir(parents=True, exist_ok=True)
            gen.rename(out)
        else:
            # copy to output
            out.parent.mkdir(parents=True, exist_ok=True)
            rmtree(out, ignore_errors=True)
            gen.rename(out)


def generate(inp_root: Path, out_root: Path, config: ValidatedConfig):
    # pylint: disable=duplicate-code

    walker = Walker(inp_root, out_root)

    for event in walker.walk():
        inp = event.inp_path
        out = event.out_path

        match event.kind:
            case Kind.ROOT:
                print(f"Clean {event.out_rel_pattern}")
                remove(out)

                if inp.is_dir() or (inp.suffix in (".py", ".pyi")):
                    print(f"Stub {event.inp_rel_pattern} -> {event.out_rel_pattern}")
                    generate_mypy(inp, out, inp.is_file())
            case Kind.COPY:
                print(f"Copy {event.out_rel_pattern}")
                generate_copy(inp, out)
            case Kind.STUB:
                pass

    format_pyi_tree(walker, config)

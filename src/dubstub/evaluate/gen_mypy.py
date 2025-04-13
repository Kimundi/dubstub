import subprocess
from pathlib import Path
from shutil import copy2, rmtree
from tempfile import TemporaryDirectory

from ..config import ValidatedConfig
from ..format import format_pyi_tree
from ..fs import Event, Kind, Walker, remove, walk_dir


def generate_copy(inp: Path, out: Path):
    # in copy mode we just copy the pyi file as-is

    out.parent.mkdir(exist_ok=True, parents=True)
    copy2(inp, out)


def run_mypy(tmp: Path, dir_or_file: Path, out_dir: Path):
    cmd = [
        "stubgen",
        "--verbose",
        # "--inspect-mode",
        "--include-docstrings",
        "-o",
        str(out_dir),
        str(dir_or_file),
    ]
    cwd = tmp

    print("mypy cmd:", cmd)
    print("mypy cwd:", cwd)

    subprocess.run(
        cmd,
        cwd=cwd,
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

    print(mypy_inp_path)
    print(mypy_out_path)
    subprocess.run(["tree", "-a", str(mypy_out_path)])

    expected = find_module_structure(mypy_inp_path)
    current = find_module_structure(mypy_out_path)

    # print(expected)
    # print(current)
    evaluated = evaluate_structures(expected, current, ())

    weighted = sorted(evaluated, key=lambda tup: (1.0 - tup[0], tup[1]))
    # for x in weighted:
    #    print(x)

    return Path(*weighted[0][2])


def generate_mypy(inp: Path, out: Path, is_file: bool, stub_out_paths: list[tuple[Path, Path]]):
    # otherwise we invoke pyright with the right base directory to do a src import from
    with TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        tmp_out = tmp / "out"
        tmp_out.mkdir()

        # call mypy
        run_mypy(tmp, inp, tmp_out)

        # TODO: take walker Events output paths,
        # and check them against the modules found at found_rel_path
        # Then rewrite them to the expected output.
        found_rel_path = find_matching_output(inp, tmp_out)
        print()
        print("found_rel_path", found_rel_path)
        for stub_out_path_rel, stub_out_path_abs in stub_out_paths:
            mypy_out_src = tmp_out / found_rel_path / stub_out_path_rel
            if mypy_out_src.stem == "__init__":
                mypy_out_src = mypy_out_src.parent
            else:
                mypy_out_src = mypy_out_src.with_suffix("")
            print("mypy_out_src: ", mypy_out_src)
            print("-> out:", stub_out_path_abs)
            assert mypy_out_src.suffix == ""
            candidates = [
                mypy_out_src.with_suffix(".pyi"),
                mypy_out_src / "__init__.pyi",
            ]
            for candidate in candidates:
                print("candidate:", candidate, candidate.exists())
        print()

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

    roots: list[tuple[Event, list[Event], list[Event]]] = []

    for event in walker.walk():
        match event.kind:
            case Kind.ROOT:
                roots.append((event, [], []))
            case Kind.STUB:
                root, stub_events, _ = roots[-1]
                if root.is_file:
                    assert event.inp_path == root.inp_path
                else:
                    assert root.inp_path in [event.inp_path, *event.inp_path.parents]
                stub_events.append(event)
            case Kind.COPY:
                root, _, copy_events = roots[-1]
                if root.is_file:
                    assert event.inp_path == root.inp_path
                else:
                    assert root.inp_path in [event.inp_path, *event.inp_path.parents]
                copy_events.append(event)

    for root, stub_events, copy_events in roots:
        print("DEBUG: root", root.inp_path)
        print(f"  {root.out_path}")
        for stub_event in stub_events:
            print("DEBUG: stub", stub_event.inp_path)
            print(f"  {stub_event.out_path}")
            print(f"    {stub_event.out_path.relative_to(root.out_path)}")
        for copy_event in copy_events:
            print("DEBUG: copy", copy_event.inp_path)

        stub_out_paths: list[tuple[Path, Path]] = []
        for stub_event in stub_events:
            stub_out_paths.append((stub_event.out_path.relative_to(root.out_path), stub_event.out_path))
        print("DEBUG: stub_out_paths", stub_out_paths)

        print(f"Clean {root.out_rel_pattern}")
        remove(root.out_path)

        # only call mypy if there is at least one file we need to have stubbed
        if stub_events and (not root.is_file or (root.inp_path.suffix in (".py", ".pyi"))):
            print(f"Stub {root.inp_rel_pattern} -> {root.out_rel_pattern}")
            generate_mypy(root.inp_path, root.out_path, root.is_file, stub_out_paths)

        # Files that can be kept as-is get copied directly afterwards. This
        # also ensures any mypy files get overridden
        for event in copy_events:
            print(f"Copy {event.out_rel_pattern}")
            generate_copy(event.inp_path, event.out_path)

        print()

    format_pyi_tree(walker, config)

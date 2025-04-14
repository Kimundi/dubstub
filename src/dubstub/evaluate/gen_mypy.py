import subprocess
from pathlib import Path
from shutil import copy2
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
    subprocess.run(
        cmd,
        cwd=cwd,
        check=True,
    )


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


def find_mypy_out_subdir(mypy_inp_path: Path, mypy_out_path: Path) -> Path:
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
    evaluated = evaluate_structures(expected, current, ())
    weighted = sorted(evaluated, key=lambda tup: (1.0 - tup[0], tup[1]))

    return Path(*weighted[0][2])


def generate_mypy(root: Event, stub_events: list[Event]):
    inp = root.inp_path

    # otherwise we invoke pyright with the right base directory to do a src import from
    with TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        tmp_out = tmp / "out"
        tmp_out.mkdir()

        # call mypy
        run_mypy(tmp, inp, tmp_out)

        # Analyze mypy's output directory to figure out which of the files
        # in there match the input and output paths from the stub events.
        #
        # This is needed because mypy will walk up the directory tree for
        # its input until it finds something it identifies as the root of
        # the module tree, and then it will output the stubbed files under this
        # discovered directory path in the output directory.
        #
        # Additionally, mypy also will also not always match the kind of
        # module file of the source (`<name>/__init__.pyi` vs `<name>.pyi`).
        #
        # For example, stubbing `foo/bar/baz.py` _should_ just generate `baz.pyi`,
        # but can also end up generating `foo/bar/baz.pyi` or `foo/bar/baz/__init__.pyi`.
        #
        # We solve this issue heuristically in multiple phases:
        # - First we identify which output paths should be generated relative
        #   to the current root stubbing Event.
        # - Then we heuristically try to figure out at which nesting level in the
        #   mypy output directory we find the type stubs that match the same level
        #   as the path argument passed to mypy.
        # - Finally we combine the both, by looking at the stub files at the
        #   right location in the mypy output, and moving them to the the
        #   expected output paths.
        root_relative_out_paths = get_root_relative_out_paths(root, stub_events)
        mypy_out_subdir = find_mypy_out_subdir(inp, tmp_out)
        for stub_out_root_relative, stub_out in root_relative_out_paths:
            # Compute the expected path to the module, in form of a directory
            # path whose last component contains the name of the module.
            #
            # This is used as a placeholder to then derive the two possible
            # module file paths from it.
            mypy_out_mod_path = tmp_out / mypy_out_subdir / stub_out_root_relative
            if mypy_out_mod_path.stem == "__init__":
                mypy_out_mod_path = mypy_out_mod_path.parent
            else:
                mypy_out_mod_path = mypy_out_mod_path.with_suffix("")
            assert mypy_out_mod_path.suffix == ""

            # NB: Mypy might generate either `<name>/__init__.pyi` or `<name>.pyi`,
            # so we check both variants
            mod_file_candidates = (
                mypy_out_mod_path.with_suffix(".pyi"),
                mypy_out_mod_path / "__init__.pyi",
            )
            for candidate in mod_file_candidates:
                if candidate.exists():
                    stub_out.parent.mkdir(exist_ok=True, parents=True)
                    candidate.rename(stub_out)
                    break


def group_per_root(walker: Walker) -> list[tuple[Event, list[Event], list[Event]]]:
    """
    Group up Walker Events, such that each ROOT event is matched with
    all its child STUB and COPY events.
    """

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

    return roots


def get_root_relative_out_paths(root: Event, stub_events: list[Event]) -> list[tuple[Path, Path]]:
    """Returns a list of tuples that contain the path of a stub file both relative to its root, and absolute"""

    stub_out_paths: list[tuple[Path, Path]] = []
    for stub_event in stub_events:
        stub_out_paths.append((stub_event.out_path.relative_to(root.out_path), stub_event.out_path))

    return stub_out_paths


def generate(inp_root: Path, out_root: Path, config: ValidatedConfig):
    walker = Walker(inp_root, out_root)
    roots = group_per_root(walker)
    for root, stub_events, copy_events in roots:
        print(f"Clean {root.out_rel_pattern}")
        remove(root.out_path)

        # only call mypy if there is at least one file we need to have stubbed
        if stub_events and (not root.is_file or (root.inp_path.suffix in (".py", ".pyi"))):
            print(f"Stub {root.inp_rel_pattern} -> {root.out_rel_pattern}")
            generate_mypy(root, stub_events)

        # Files that can be kept as-is get copied directly afterwards. This
        # also ensures any .pyi files mypy might have copied over will be ignored
        # in favour of their original content.
        for event in copy_events:
            print(f"Copy {event.out_rel_pattern}")
            generate_copy(event.inp_path, event.out_path)

    format_pyi_tree(walker, config)

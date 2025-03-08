import os
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from shutil import rmtree
from typing import Iterable


def walk_dir(root: Path) -> Iterable[Path]:
    assert root.exists(), f"Path does not exist: >{root}<"

    if root.is_file():
        yield Path(root)

    for dirname, _, filenames in os.walk(root):
        yield Path(dirname)
        for filename in sorted(filenames):
            yield Path(dirname) / filename


def remove(path: Path):
    if path.is_file():
        path.unlink()
    elif path.is_dir():
        rmtree(path)


def find_module_roots(path: Path) -> Iterable[Path]:
    """
    Find all paths that define the root of a module tree for the purpose of type
    checking.

    This includes isolated `.py` and `.pyi` files, as well as directories that contain
    `__init__.py` files.

    The paths will not overlap, so if a directory is yield, no child files from it will
    be yielded.
    """

    # the entire directory tree defines a module
    if path.is_dir() and (path / "__init__.py").exists():
        yield path
        return

    # this single file defines a module
    if path.is_file() and (path.suffix in (".py", ".pyi") or path.name == "py.typed"):
        yield path
        return

    # recursively look in children instead
    if path.is_dir():
        for child in sorted(path.iterdir()):
            yield from find_module_roots(child)


class Kind(Enum):
    ROOT = auto()
    COPY = auto()
    STUB = auto()


@dataclass
class Event:
    walker: "Walker"

    inp_path: Path
    inp_rel_pattern: str

    out_path: Path
    out_rel_pattern: str

    kind: Kind


# pylint: disable-next=too-few-public-methods
class Walker:
    inp_root: Path
    out_root: Path

    root_is_file: bool

    cache: list[Event] | None

    def __init__(self, inp_root: Path, out_root: Path):
        assert inp_root.exists()

        self.inp_root = inp_root.resolve()
        self.out_root = out_root.resolve()

        self.root_is_file = self.inp_root.is_file()

        # support writing a single file to an output directory
        if self.root_is_file and self.out_root.is_dir():
            self.out_root = self.out_root / self.inp_root.name
            if self.inp_root.suffix == ".py":
                self.out_root = self.out_root.with_suffix(".pyi")

        self.cache = None

    def _get_paths(self, inp_path: Path) -> tuple[Path, str, str]:
        """
        Given an input path:
        - Return the matching output path
        - Return the matching input pattern string
        - Return the matching output pattern string
        """

        # Relative path for input file
        rel_inp = inp_path.relative_to(self.inp_root)

        # Output path with potentially wrong target file name
        out_path = self.out_root / rel_inp

        if self.root_is_file:
            # If root is a file, we keep the output as it is
            inp_rel_pattern = inp_path.name
            out_rel_pattern = out_path.name
        else:
            # Otherwise we determine the new file suffixes
            if inp_path.suffix == ".py":
                out_path = out_path.with_suffix(".pyi")
            inp_rel_pattern = str(rel_inp)
            out_rel_pattern = str(out_path.relative_to(self.out_root))

        return (out_path, inp_rel_pattern, out_rel_pattern)

    def _walk_module_root(self, inp_path_root: Path) -> Iterable[Event]:
        """Yield all walk events relative to a python module root."""

        for inp_path in walk_dir(inp_path_root):
            out_path, inp_rel_pattern, out_rel_pattern = self._get_paths(inp_path)

            # NB: If we have both a .py and pyi file, we prefer keeping the .pyi file
            if inp_path.suffix == ".py" and not inp_path.with_suffix(".pyi").exists():
                # this file we stub
                kind = Kind.STUB
            elif inp_path.suffix == ".pyi" or inp_path.name == "py.typed":
                # these files we just copy
                kind = Kind.COPY
            else:
                # other files we silently ignore
                continue

            yield Event(
                walker=self,
                inp_path=inp_path,
                out_path=out_path,
                inp_rel_pattern=inp_rel_pattern,
                out_rel_pattern=out_rel_pattern,
                kind=kind,
            )

    def _walk(self) -> Iterable[Event]:
        """Yield all walk events."""

        for inp_path in find_module_roots(self.inp_root):
            out_path, inp_rel_pattern, out_rel_pattern = self._get_paths(inp_path)

            # we want to clean the entire module root
            yield Event(
                walker=self,
                inp_path=inp_path,
                out_path=out_path,
                inp_rel_pattern=inp_rel_pattern,
                out_rel_pattern=out_rel_pattern,
                kind=Kind.ROOT,
            )
            yield from self._walk_module_root(inp_path)

    def walk(self) -> Iterable[Event]:
        """Yield all walk events."""

        if self.cache is not None:
            yield from self.cache
        else:
            cache: list[Event] = []
            for event in self._walk():
                yield event
                cache.append(event)
            self.cache = cache

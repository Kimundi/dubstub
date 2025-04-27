import re
from difflib import Differ
from pathlib import Path
from typing import Iterable

from rich.console import Console
from rich.table import Column, Table
from rich.text import Text

from ..fs import walk_dir


def walk_rel_stub_files(root: Path) -> Iterable[Path]:
    for path in walk_dir(root):
        if path.is_file() and (path.suffix in (".py", ".pyi") or path.name == "py.typed"):
            yield path.relative_to(root)


# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements,too-many-arguments,too-many-positional-arguments
def run(
    eval_path: Path,
    left: str,
    right: str,
    width: int,
    hide_missing: bool,
    filter_re: str | None,
):
    a_path = eval_path / left
    b_path = eval_path / right

    paths: set[Path] = set()
    paths.update(walk_rel_stub_files(a_path))
    paths.update(walk_rel_stub_files(b_path))

    for path in sorted(paths):
        if filter_re is not None and not re.match(filter_re, str(path)):
            continue

        a_file = a_path / path
        b_file = b_path / path

        a_content = ""
        if a_file.exists():
            a_content = a_file.read_text()
        elif hide_missing:
            continue

        b_content = ""
        if b_file.exists():
            b_content = b_file.read_text()
        elif hide_missing:
            continue

        if a_content == b_content:
            continue

        a_lines = a_content.splitlines()
        b_lines = b_content.splitlines()

        chunks: list[tuple[str, list[str], list[str]]] = [
            ("-", [], []),
        ]

        differ = Differ()
        for line in differ.compare(a_lines, b_lines):
            marker = line[0]

            pair: tuple[str, list[str], list[str]]
            if marker == " ":
                pair = ("==", [line[2:]], [line[2:]])
            elif marker == "-":
                pair = ("!=", [line[2:]], [])
            elif marker == "+":
                pair = ("!=", [], [line[2:]])
            else:
                continue

            if chunks[-1][0] == pair[0]:
                chunks[-1][1].extend(pair[1])
                chunks[-1][2].extend(pair[2])
            else:
                chunks.append(pair)

        for ci, chunk in enumerate(chunks):
            if chunk[0] == "==":
                if len(chunk[1]) > 6 and ci + 1 < len(chunks):
                    new = [
                        *chunk[1][0:3],
                        # Text("[...]", style="bright_black"),
                        "<<SEPARATOR>>",
                        *chunk[1][-3:],
                    ]
                    chunk[1].clear()
                    chunk[2].clear()
                    chunk[1].extend(new)
                    chunk[2].extend(new)
                elif len(chunk[1]) > 3 and ci + 1 == len(chunks):
                    new = [
                        *chunk[1][0:3],
                        "<<SEPARATOR>>",
                    ]
                    chunk[1].clear()
                    chunk[2].clear()
                    chunk[1].extend(new)
                    chunk[2].extend(new)
                elif len(chunk[1]) > 3 and ci == 0:
                    new = [
                        "<<SEPARATOR>>",
                        *chunk[1][-3:],
                    ]
                    chunk[1].clear()
                    chunk[2].clear()
                    chunk[1].extend(new)
                    chunk[2].extend(new)

        console = Console(color_system="standard")
        tbl = Table(
            Column(left, width=width // 2),
            Column(right, width=width // 2),
            title=str(path),
            title_justify="left",
        )

        for kind, a_chunk_lines, b_chunk_lines in chunks:
            ml = max(len(a_chunk_lines), len(b_chunk_lines))
            for i in range(ml):
                a_chunk_line = ""
                b_chunk_line = ""

                if i < len(a_chunk_lines):
                    a_chunk_line = a_chunk_lines[i]
                if i < len(b_chunk_lines):
                    b_chunk_line = b_chunk_lines[i]

                if kind == "!=":
                    tbl.add_row(
                        Text(a_chunk_line, style="red"),
                        Text(b_chunk_line, style="green"),
                    )
                elif a_chunk_line == "<<SEPARATOR>>":
                    tbl.add_section()
                else:
                    tbl.add_row(a_chunk_line, b_chunk_line)

        console.print(tbl)
        print()

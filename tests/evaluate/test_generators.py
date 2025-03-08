import hashlib
from pathlib import Path
from types import ModuleType

import pytest

from dubstub.config import Config
from dubstub.evaluate.main import GENERATORS
from dubstub.fs import walk_dir

from .. import TESTDATA

TREE_INPUT = TESTDATA / "tree" / "src"
TREE_EXPECTED = TESTDATA / "tree" / "stubs"


def tree_to_dict(path: Path) -> tuple[dict[str, str], dict[str, str]]:
    file_hashes: dict[str, str] = {}
    file_contents: dict[str, str] = {}
    print(path)
    for child in walk_dir(path):
        if child.is_file():
            file_contents[str(child.relative_to(path))] = child.read_text()
            file_hashes[str(child.relative_to(path))] = hashlib.sha256(child.read_bytes()).hexdigest()
    file_hashes = dict(sorted(file_hashes.items()))
    return file_hashes, file_contents


@pytest.mark.parametrize(
    ("inp_sub_path", "out_sub_path"),
    [
        ("", ""),
        ("sub/sub/a", "sub/sub/a"),
        ("sub/sub/a/check.pyi", "sub/sub/a/check.pyi"),
        ("sub/sub/a/foo.py", "sub/sub/a/foo.pyi"),
        ("sub/sub/b/bar", "sub/sub/b/bar"),
    ],
)
@pytest.mark.parametrize(("name", "module"), list(GENERATORS.items()))
def test_generator(name: str, module: ModuleType, tmp_path: Path, inp_sub_path: str, out_sub_path: str):
    print(name)

    inp = TREE_INPUT / Path(inp_sub_path)
    expected = TREE_EXPECTED / Path(out_sub_path)
    out = tmp_path / Path(out_sub_path)

    # now call the actual generator
    module.generate(inp, out, Config().validate())

    expected_dict, _ = tree_to_dict(expected)
    out_dict, out_content = tree_to_dict(out)

    if out_dict != expected_dict:
        for file, content in out_content.items():
            print(f"- {file} ------------------------")
            print(content)
            print("----------------------------------")

    assert out_dict == expected_dict, f"Output at {out} is unexpected"


@pytest.mark.parametrize(("name", "module"), list(GENERATORS.items()))
def test_min_dir_replacement(name: str, module: ModuleType, tmp_path: Path):
    print(name)

    for child in walk_dir(TREE_INPUT):
        if child.is_dir():
            rel = child.relative_to(TREE_INPUT)
            out_child = tmp_path / rel
            out_child.mkdir(parents=True, exist_ok=True)
            (out_child / "MARKER").touch()

    # now call the actual generator
    module.generate(TREE_INPUT, tmp_path, Config().validate())

    survived_markers: list[str] = []
    for child in walk_dir(tmp_path):
        rel = child.relative_to(tmp_path)
        if rel.name == "MARKER":
            survived_markers.append(str(rel))
    survived_markers = sorted(survived_markers)

    assert survived_markers == [
        "MARKER",
        "sub/MARKER",
        "sub/sub/MARKER",
        "sub/sub/a/MARKER",
        "sub/sub/b/MARKER",
        "sub/sub/c/MARKER",
    ]

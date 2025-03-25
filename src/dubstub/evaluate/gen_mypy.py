import subprocess
from pathlib import Path
from shutil import copy2, rmtree
from tempfile import TemporaryDirectory

from ..config import ValidatedConfig
from ..format import format_pyi_tree
from ..fs import Kind, Walker, remove


def generate_copy(inp: Path, out: Path):
    # in copy mode we just copy the pyi file as-is

    out.parent.mkdir(exist_ok=True, parents=True)
    copy2(inp, out)


def run_mypy(tmp: Path, dir_or_file: Path, out_dir: Path):
    subprocess.run(
        [
            "stubgen",
            "--verbose",
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


def generate_mypy(inp: Path, out: Path, is_file: bool):
    # otherwise we invoke pyright with the right base directory to do a src import from
    with TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        tmp_out = tmp / "out"
        tmp_out.mkdir()

        # call mypy
        run_mypy(tmp, inp, tmp_out)

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

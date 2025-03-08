from pathlib import Path
from shutil import copy2

from ..config import Config, ValidatedConfig
from ..format import format_pyi_tree
from ..fs import Kind, Walker, remove
from .stubber import stubgen_single_file_src


def generate_stubs(
    input_path: Path,
    output_path: Path,
    config: Config | None = None,
):
    """
    Generate type stubs for all files found in `inp_root`,
    and writing them with the same structure to `out_root`.

    Optionally runs a formatter over the result.

    Optionally uses the provided `config` (otherwise the default config is used).
    """

    # NB: We want to support merging namespace module directories, so
    # we actually descent down into all non-namespace modules when processing the input directory
    inp: Path = input_path.resolve()
    out: Path = output_path.resolve()

    validated = (config or Config()).validate()

    walker = Walker(inp, out)

    _generate_stubs(walker, validated)

    format_pyi_tree(walker, validated)


def _generate_stubs(walker: Walker, config: ValidatedConfig):
    # pylint: disable=duplicate-code

    for event in walker.walk():
        inp = event.inp_path
        out = event.out_path

        match event.kind:
            case Kind.ROOT:
                print(f"Clean {event.out_rel_pattern}")
                remove(out)
            case Kind.COPY:
                print(f"Copy {event.out_rel_pattern}")
                out.parent.mkdir(parents=True, exist_ok=True)
                copy2(inp, out)
            case Kind.STUB:
                print(f"Stub {event.inp_rel_pattern} -> {event.out_rel_pattern}")
                content = inp.read_text()
                content = stubgen_single_file_src(content, Path(event.inp_rel_pattern), config)
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(content)

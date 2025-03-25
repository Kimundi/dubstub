from argparse import ArgumentParser, Namespace, RawTextHelpFormatter
from pathlib import Path
from types import ModuleType
from typing import Callable

from ..cli.common import add_common_options, parse_config_from_cli
from ..config import Config
from . import gen_dubstub, gen_mypy, gen_pyright

GENERATORS: dict[str, ModuleType] = {
    "dubstub": gen_dubstub,
    "pyright": gen_pyright,
    "mypy": gen_mypy,
}


def register_args(make_parser: Callable[..., ArgumentParser]):
    parser = make_parser("eval", formatter_class=RawTextHelpFormatter)
    parser.set_defaults(entrypoint=main)
    parser.add_argument("--input", type=Path, required=True, help="Input file or directory tree")
    parser.add_argument("--output", type=Path, required=True, help="Output file or directory tree")
    parser.add_argument(
        "--type",
        choices=["dubstub", "pyright", "mypy", "all"],
        default="all",
        help="Which typestub generators to run. Their output will be placed side-by-side in the output directory.",
    )
    parser.add_argument("--group", help="Optional extra directory name to group output of multiple calls under.")
    add_common_options(parser)


def main(args: Namespace):
    run(
        args.input,
        args.output,
        group=args.group,
        generators=[args.type],
        config=parse_config_from_cli(args),
    )


# pylint: disable-next=too-many-arguments,too-many-locals
def run(
    input_path: Path,
    output_path: Path,
    *,
    group: str | None = None,
    generators: list[str] | None = None,
    config: Config | None = None,
):
    # NB: We want to support merging namespace module directories, so
    # we actually descent down into all non-namespace modules when processing the input directory
    inp: Path = input_path.resolve()
    out: Path = output_path.resolve()

    validated = (config or Config()).validate()

    def get_out_sub(generator_name: str):
        out_sub = out / generator_name
        if group:
            out_sub = out_sub / group
        return out_sub

    # next to dubstub itself, we support other typestub generators for comparison
    selected_generators: dict[str, ModuleType] = {}
    for generator in generators or []:
        if generator == "all":
            for generator_name, generator_module in GENERATORS.items():
                selected_generators[generator_name] = generator_module
        else:
            selected_generators[generator] = GENERATORS[generator]

    # For each generator, generate type stubs for each discovered input child directory
    for generator_name, generator_module in selected_generators.items():
        print(f"Generate typestubs with {generator_name}")

        # determine the exact output directory for this generator
        out_sub = get_out_sub(generator_name)

        # actually generate the type stubs
        generator_module.generate(inp, out_sub, validated)
        print()

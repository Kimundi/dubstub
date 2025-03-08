from argparse import ArgumentParser, Namespace, RawTextHelpFormatter
from pathlib import Path
from typing import Callable

from ..cli.common import add_common_options, parse_config_from_cli
from ..util import extra_guard
from .fs import generate_stubs


def register_args(make_parser: Callable[..., ArgumentParser]):
    parser = make_parser("gen", formatter_class=RawTextHelpFormatter)
    parser.set_defaults(entrypoint=main)
    parser.add_argument("--input", type=Path, required=True, help="Input file or directory tree")
    parser.add_argument("--output", type=Path, required=True, help="Output file or directory tree")
    add_common_options(parser)


def main(args: Namespace):
    with extra_guard("def_fmt", executables=["black", "isort"]):
        generate_stubs(
            args.input,
            args.output,
            config=parse_config_from_cli(args),
        )

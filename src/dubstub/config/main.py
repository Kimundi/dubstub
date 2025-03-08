from argparse import SUPPRESS, ArgumentParser, Namespace, RawTextHelpFormatter
from pathlib import Path
from typing import Callable

from ..cli.common import add_common_options, parse_config_from_cli


def register_args(make_parser: Callable[..., ArgumentParser]):
    parser = make_parser("config", formatter_class=RawTextHelpFormatter)
    parser.set_defaults(entrypoint=main)
    parser.add_argument("--show", action="store_true", help="show effective config")
    parser.add_argument("--show-format", default="plain", choices=["plain", "json", "toml"])
    parser.add_argument("--gen-docs", type=Path, help=SUPPRESS)
    add_common_options(parser)


def main(args: Namespace):
    config = parse_config_from_cli(args)

    if args.gen_docs:
        from .gen_docs import generate_docs  # pylint:disable=import-outside-toplevel

        generate_docs(args.gen_docs)
    elif args.show or args.show_format:
        from .show import fmt_config  # pylint:disable=import-outside-toplevel

        validated = config.validate()
        print(fmt_config(validated, args.show_format))

from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Callable


def register_args(make_parser: Callable[..., ArgumentParser]):
    parser = make_parser("diff")
    parser.add_argument(
        "--eval",
        type=Path,
        required=True,
        help="""
            Path to output of the `dubstub eval` command
        """,
    )
    parser.add_argument(
        "--left",
        default="pyright",
        help="""
            What to display on the left side of the diff.
        """,
    )
    parser.add_argument(
        "--right",
        default="dubstub",
        help="""
            What to display on the right side of the diff.
        """,
    )
    parser.add_argument(
        "--width",
        default=160,
        type=int,
        help="""
            Total width of tables
        """,
    )
    parser.add_argument(
        "--hide-missing",
        action="store_true",
        help="""
            Do not show diff if one of the files is entirely missing
        """,
    )
    parser.add_argument(
        "--filter",
        help="""
            Regular expression filter for the files that should be diffed
        """,
    )
    parser.set_defaults(entrypoint=main)


def main(args: Namespace):
    from .impl import run  # pylint:disable=import-outside-toplevel

    run(
        eval_path=args.eval,
        left=args.left,
        right=args.right,
        width=args.width,
        hide_missing=args.hide_missing,
        filter_re=args.filter,
    )

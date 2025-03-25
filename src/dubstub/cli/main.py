from argparse import ArgumentParser

from ..config import main as config
from ..diff import main as diff
from ..evaluate import main as evaluate
from ..generate import main as generate
from ..util import extra_guard


def main():
    parser = ArgumentParser()

    subparsers = parser.add_subparsers(required=True)
    generate.register_args(subparsers.add_parser)
    evaluate.register_args(subparsers.add_parser)
    diff.register_args(subparsers.add_parser)
    config.register_args(subparsers.add_parser)

    args = parser.parse_args()

    with (
        extra_guard("def_fmt", executables=["black", "isort"]),
        extra_guard("eval", modules=["rich"], executables=["pyright", "stubgen"]),
    ):
        args.entrypoint(args)

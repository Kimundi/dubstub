from argparse import ArgumentParser, Namespace
from pathlib import Path

from ..config import Config
from ..config.pattern import Pattern


def add_common_options(parser: ArgumentParser):
    parser.add_argument("--config", type=Path, help="Path to a config file")
    group = parser.add_argument_group("config options")
    for field_name, field in Config.get_fields().items():
        if field.validated_ty.ty is str or field.validated_ty.ty is Pattern:
            group.add_argument(
                f"--{field_name}",
                help=field.description,
            )
        elif field.validated_ty.ty is list:
            # NB: not currently settable via CLI
            pass
        else:
            raise AssertionError("unhandled type in Config")


def parse_config_from_cli(args: Namespace) -> Config:
    config = Config()

    if args.config:
        config = Config.parse_config(path=args.config)

    for field_name, field in Config.get_fields().items():
        args_val = getattr(args, field_name, None)
        if args_val:
            if field.validated_ty.ty is Pattern:
                config.set(field_name, args_val)
            elif field.validated_ty.ty is str:
                config.set(field_name, args_val)
            else:
                raise AssertionError("unhandled type in Config")

    return config

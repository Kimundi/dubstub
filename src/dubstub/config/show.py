import json
from textwrap import dedent

from .. import toml
from ..util import Json
from . import Config
from .pattern import Pattern


def fmt_config_dict(config: Config, show_format: str) -> dict[str, Json]:
    re_parse = show_format != "toml"

    out: dict[str, Json] = {}
    for field_name, field in Config.get_fields().items():
        val = config.get(field_name)
        if val is None:
            continue

        if field.validated_ty.ty is Pattern:
            raw = val
            if isinstance(raw, bool):
                pass
            elif raw == "True":
                raw = True
            elif raw == "False":
                raw = False
            else:
                assert isinstance(raw, str)
                if not re_parse:
                    raw = dedent(raw).strip()
                    lines = raw.splitlines()
                    raw = "".join(f"    {line}\n" for line in lines)
        elif isinstance(val, list):
            assert field.validated_ty.generic_string() == "list[FormatterCmd]"
            raw = [
                {
                    "name": command.name,
                    "cmdline": command.cmdline,
                }
                for command in val
            ]
        else:
            raw = val

        out[field_name] = raw

    return out


def fmt_config(config: Config, show_format: str) -> str:
    out = fmt_config_dict(config, show_format)

    ret = ""
    if show_format == "plain":
        for field, raw in out.items():
            ret += f"{field}={raw}\n"
    elif show_format == "json":
        out_with_header = {"tool": {"dubstub": out}}
        ret = json.dumps(out_with_header, indent=4)
    elif show_format == "toml":
        out_with_header = {"tool": {"dubstub": out}}
        ret = toml.dumps(out_with_header, indent=4, multiline_strings=True)

    return ret.strip()

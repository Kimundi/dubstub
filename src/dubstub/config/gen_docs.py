from pathlib import Path
from textwrap import dedent

from pycmarkgfm import gfm_to_html, options  # type: ignore

from . import PROFILES, Config
from .show import fmt_config


def render(gfm: str) -> str:
    return gfm_to_html(dedent(gfm), options.github_pre_lang)  # type: ignore


class MarkdownTableRender:
    cols: list[str]
    rows: list[list[str]]

    def __init__(self, *cols: str):
        self.cols = list(cols)
        self.rows = []

    def add_row(self, *cells: str):
        self.rows.append(list(cells))

    def render(self) -> str:
        lookup: dict[str, str] = {}

        # first render the table to html
        ret = ""
        ret += f"| { ' | ' .join(self.cols) } |\n"
        ret += "|" + (" --- |" * len(self.cols)) + "\n"

        for row in self.rows:
            ret += "|"
            for cell in row:
                key = f"CELL[{len(lookup)}]"
                rendered = render(cell)
                lookup[key] = rendered
                ret += f" {key} |"
            ret += "\n"

        ret = render(ret)

        # then insert the rendered cells into it
        for key, val in lookup.items():
            ret = ret.replace(key, val)

        return ret.rstrip()


def generate_config_docs(content: str) -> str:
    table = MarkdownTableRender("Config Setting", "Description")
    for field_name, field in Config.get_fields().items():
        table.add_row(
            f"`{field_name}`\n\ntype: `{field.validated_ty.generic_string()}`",
            field.description,
        )

    start_marker = "<!-- CONFIG_START -->\n"
    start_pos = content.find(start_marker)
    assert start_pos >= 0
    start_pos += len(start_marker)

    end_marker = "\n<!-- CONFIG_END -->"
    end_pos = content.find(end_marker)
    assert end_pos >= 0

    rendered = table.render()
    return content[:start_pos] + rendered + content[end_pos:]


def generate_profile_docs(content: str) -> str:
    rendered = ""
    for profile_name, profile_data in PROFILES.items():
        description = dedent(profile_data.description).strip()

        rendered += f"#### Profile `{profile_name}`\n"
        rendered += "\n"
        rendered += description.rstrip() + "\n"
        rendered += "\n"
        rendered += "Exact config settings set by the profile:\n"
        rendered += "\n"
        rendered += "```toml\n" + fmt_config(profile_data.fields, "toml") + "\n```\n"

    start_marker = "<!-- PROFILE_START -->\n"
    start_pos = content.find(start_marker)
    assert start_pos >= 0
    start_pos += len(start_marker)

    end_marker = "\n<!-- PROFILE_END -->"
    end_pos = content.find(end_marker)
    assert end_pos >= 0

    return content[:start_pos] + rendered + content[end_pos:]


def generate_docs(out: Path):
    if not out.exists():
        out.write_text(
            dedent(
                """
                    # debug config
                    <!-- CONFIG_START -->
                    <!-- CONFIG_END -->

                    # debug profiles
                    <!-- PROFILE_START -->
                    <!-- PROFILE_END -->
                """
            )
        )

    content = out.read_text()
    content = generate_config_docs(content)
    content = generate_profile_docs(content)
    out.write_text(content)

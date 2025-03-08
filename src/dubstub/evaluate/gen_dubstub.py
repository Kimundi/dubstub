from pathlib import Path

from ..config import ValidatedConfig
from ..generate.fs import generate_stubs


def generate(inp: Path, out: Path, config: ValidatedConfig):
    generate_stubs(inp, out, config)

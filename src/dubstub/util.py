import re
import sys
from contextlib import contextmanager
from typing import Mapping, Sequence, TypeAlias

Json: TypeAlias = Mapping[str, "Json"] | Sequence["Json"] | str | int | float | bool | None


def regex_match(pattern: str, strings: str | list[str]) -> bool:
    if isinstance(strings, str):
        strings = [strings]

    for string in strings:
        if re.fullmatch(pattern, string):
            return True

    return False


@contextmanager
def extra_guard(extra: str, *, modules: list[str] | None = None, executables: list[str] | None = None):
    try:
        yield
    except ModuleNotFoundError as exc:
        if exc.name in (modules or []):
            print(f"The `{extra}` extra seems to not be installed (module `{exc.name}` not found)")
            sys.exit(1)
        raise
    except FileNotFoundError as exc:
        if exc.filename is None:
            raise

        if isinstance(exc.filename, bytes):
            filename = exc.filename.decode()
        else:
            filename = exc.filename

        if filename in (executables or []):
            print(f"The executable `{filename}` was not found (can be installed with `{extra}` extra)")
            sys.exit(1)

        raise

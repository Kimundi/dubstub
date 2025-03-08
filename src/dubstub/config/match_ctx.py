from dataclasses import dataclass
from enum import Enum


class Tag(Enum):
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    IMPORT = "import"
    TYPE_ALIAS = "type_alias"
    VARIABLE = "variable"
    ANNOTATED = "annotated"
    ASSIGNED = "assigned"
    IF = "if"
    DOCSTRING = "docstring"
    ELLIPSIS = "ellipsis"
    SPACER = "spacer"


@dataclass
class MatchContext:
    parent_tags: set[Tag]
    tags: set[Tag]
    file_path: str
    name: str | None = None
    annotation: str | None = None
    value: str | None = None
    child_tags: set[Tag] | None = None

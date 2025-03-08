import sys
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from types import NoneType, UnionType
from typing import Annotated, Any, TypeAlias, get_args, get_origin, get_type_hints

from .. import toml
from .pattern import Pattern


@dataclass
class FormatterCmd:
    name: str
    cmdline: list[str]


RawConfigType: TypeAlias = str | bool | list[FormatterCmd]
ValidatedConfigType: TypeAlias = str | Pattern | list[FormatterCmd]


@dataclass
class TypeModel:
    ty: type
    args: list["TypeModel"]

    @staticmethod
    def parse_annotation(annotation: Any) -> "TypeModel":
        origin = get_origin(annotation)
        if origin is None:
            return TypeModel(annotation, [])

        args = get_args(annotation)
        return TypeModel(origin, [TypeModel.parse_annotation(arg) for arg in args])

    def generic_string(self) -> str:
        ret = self.ty.__name__
        if self.args:
            ret += f"[{', '.join(arg.generic_string() for arg in self.args)}]"
        return ret

    def args_of(self, ty: Any) -> list["TypeModel"]:
        assert self.ty is ty
        return self.args


@dataclass
class Field:
    raw_tys: list[TypeModel]
    validated_ty: TypeModel
    description: str

    @staticmethod
    def parse_annotation(annotation: Any) -> "Field":
        model = TypeModel.parse_annotation(annotation)

        # assert that we got an Annotation and get their args
        raw_union_ty, validated_ty, description_ = model.args_of(Annotated)

        # get description and reformat it
        description = description_.ty
        assert isinstance(description, str)
        description = dedent(description).strip()

        # assert that we got an Union and get their args
        raw_tys = [raw_ty for raw_ty in raw_union_ty.args_of(UnionType) if raw_ty.ty is not NoneType]
        return Field(raw_tys, validated_ty, description)


@dataclass
class Config:
    # pylint: disable=too-many-instance-attributes

    profile: Annotated[
        str | None,
        str,
        """
        Base profile to use for config settings.

        Any explicitly set config values will overwrite those defined by the profile.
        """,
    ] = None

    python_version: Annotated[
        str | None,
        str,
        """
        Version of python syntax to target.

        Valid forms are `"X.Y"` and `"auto"`, the latter of which derives
        the version from the current python interpreter.
        """,
    ] = None

    keep_definitions: Annotated[
        str | bool | None,
        Pattern,
        """
        Whether to keep a class, function, or variable definition during type stubbing.

        This can be used to remove private elements (ie, those starting with a single `_`).
        """,
    ] = None

    keep_trailing_docstrings: Annotated[
        str | bool | None,
        Pattern,
        '''
        Whether to keep a trailing docstring for an element.

        A trailing docstring is defined as a string literal that is not the first
        statement in a module, class or function block.

        These kinds of docstrings are supported by some documentation generators and IDE
        plugins.

        Example:
        ```python
        class foo:
            """normal docstring"""
            x: y = z
            """trailing docstring"""
        ```
        ''',
    ] = None

    add_implicit_none_return: Annotated[
        str | bool | None,
        Pattern,
        """
        Whether to add a `-> None` return type to a function that has not specified a
        return type annotation.
        """,
    ] = None

    keep_if_statements: Annotated[
        str | bool | None,
        Pattern,
        """
        Whether to keep an `if` statement.

        If an `if` statement is kept, its condition expression will be kept fully,
        and its body will be recursively stubbed.
        """,
    ] = None

    flatten_if: Annotated[
        str | bool | None,
        Pattern,
        """
        Whether to flatten the first body of an `if` into the surrounding scope.

        This setting combines with `keep_if_statements`: If an `if` statement is matched
        by both, the first body of the kept `if` will be empty.

        This does not apply to `elif` cases of an `if`.
        """,
    ] = None

    add_redundant_ellipsis: Annotated[
        str | bool | None,
        Pattern,
        """
        Whether to add redundant ellipsis (`...`) statements to bodies of statements that are not empty after stubbing.

        Example:
        ```python
        class foo:
            ... # always added
        class bar:
            x = y
            ... # redundant
        ```
        """,
    ] = None

    keep_variable_value: Annotated[
        str | bool | None,
        Pattern,
        """
        Whether to keep the assignment value of a variable definition.
        If the value is not kept, it is replaced with an ellipsis (`...`).

        Example:
        ```python
        foo = 42        # value kept
        foo: bar = 42   # value kept
        foo = ...       # value not kept
        foo: bar = ...  # value not kept
        ```
        """,
    ] = None

    keep_unused_imports: Annotated[
        str | bool | None,
        Pattern,
        """
        Whether to keep import statements that seem to not be used anywhere
        in the module.

        Note that this is a heuristic based on searching for the imported name,
        it can have false positives, which erroneously consider an import used.

        Both normal python code, as well the contents of `__all__` list strings will be considered.

        Certain imports will be interpreted as re-exports, and always considered used.

        For example, given this code:
        ```python
        x: Foo
        ```
        Then imports would be considered like this:
        ```python
        from foo import Foo   # considered used
        from bar import Bar   # considered not used
        import X as X         # considered used (always)
        import a.b.X as X     # considered not used
        from Y import X as X  # considered used (always)
        from Y import *       # considered used (always)
        ```

        See also https://typing.readthedocs.io/en/latest/spec/distributing.html#import-conventions
        """,
    ] = None

    format: Annotated[
        str | bool | None,
        Pattern,
        """
        Enable autoformatting of the generated typestub code.

        The default output of this tool follows no consistent formatting style:
        Individual lines either contain a single large statement, or are copy-pasted from the original source verbatim.

        If enabled, the generated or copied `.pyi` files will be passed to the commands specified by `formatter_cmds`.
        """,
    ] = None

    formatter_cmds: Annotated[
        list[FormatterCmd] | None,
        list[FormatterCmd],
        """
        List of formatter cmds that will be executed on generated and copied `.pyi` files.

        Each `FormatterCmd` is an object with an arbitrary `name`, and a `cmdline` list
        that defines how to execute the command:

        ```toml
        [[tool.dubstub.formatter_cmds]]
        name = "<cmd name>"
        cmdline = [
            "<cmd>",
            "<arg1>",
            "<arg2>",
            ...
        ]
        ```

        There are a number of variable substitutions supported for the `cmdline` arguments:

        - `${dubstub_py_major}` will be replaced by the major version of python selected
           with the `python_version` config setting.
        - `${dubstub_py_minor}` will be replaced by the minor version of python selected
           with the `python_version` config setting.
        - `${dubstub_py_exe}` will be replaced by the path to the current python executable (`sys.executable`).
        - `${dubstub_file_arg}` will be replaced with the path to a file that should be formatted in-place.
        - `${dubstub_file_args}` will be replaced with the path to a file that should be formatted in-place,
          and will also cause the argument to expand into multiple arguments, one for each file.

        The commands will be executed in series, with the output of one feeding into the next one.
        The difference between the last two substitution options is that `dubstub_file_arg` will call the command
        once for every single file, while `dubstub_file_args` will batch multiple files into a single command call.

        Examples:

        - `cmdline = ["black", "${dubstub_file_arg}"]`
          will cause these command calls:
          ```bash
          black file1.pyi
          black file2.pyi
          black file3.pyi
          ...
          ```
        - `cmdline = ["black", "${dubstub_file_args}"]`
          will cause these command calls:
          ```bash
          black file1.pyi file2.pyi file3.pyi ...
          ```
        """,
    ] = None

    @staticmethod
    def get_fields() -> dict[str, Field]:
        """
        Returns a mapping of field name to field type and description text.
        """

        ret: dict[str, Any] = {}

        for field_name, annotation in get_type_hints(Config, include_extras=True).items():
            if get_origin(annotation) is Annotated:
                ret[field_name] = Field.parse_annotation(annotation)

        return ret

    @staticmethod
    def _check_name(name: str):
        if name not in Config.get_fields():
            raise ValueError(f"unknown config setting {name}")

    def get(self, name: str) -> RawConfigType | None:
        """Get the value of the field with the give name"""

        self._check_name(name)
        return getattr(self, name)

    def set(self, name: str, value: RawConfigType | None):
        """Set the value of the field with the give name"""

        self._check_name(name)
        fields = self.get_fields()

        is_raw_ty = any(isinstance(value, raw_ty.ty) for raw_ty in fields[name].raw_tys)

        if not (value is None or is_raw_ty):
            raise ValueError(f"wrong type for config setting {name} (got {type(value).__name__})")

        setattr(self, name, value)

    @staticmethod
    def parse_config(
        path: Path | None = None,
        raw: str | None = None,
        obj: dict[str, Any] | None = None,
    ) -> "Config":
        """
        Parse a config from one of these sources:
        - a path to a `.toml` file with `tool.dubstub` keys.
        - a raw toml string representation with `tool.dubstub` keys.
        - a dictionary with `tool.dubstub` keys.
        """

        config = Config()

        if obj is None:
            if raw is None:
                if path is None:
                    raise ValueError("one of the function arguments needs to be set")
                raw = path.read_text()
            obj = toml.loads(raw)

        raw_config = obj.get("tool", {}).get("dubstub", {})
        for field, val in raw_config.items():
            if field not in Config.get_fields():
                raise ValueError(f"unknown config key {field}")
            config.set(field, val)

        return config

    def validate(self) -> "ValidatedConfig":
        """
        Validate the Config, which involves additional checks,
        and filling in all missing data with default values from the selected
        profile.
        """

        validated = ValidatedConfig()
        validated.profile = self.profile or "default"

        for field, meta in self.get_fields().items():
            if field == "profile":
                continue

            value = self.get(field)
            if value is None:
                value = PROFILES[validated.profile].fields.get(field)
            if value is None:
                value = PROFILES["default"].fields.get(field)
            assert value is not None, "value not found in default profile"

            validated.set(field, value)

            if meta.validated_ty.ty is Pattern:
                assert isinstance(value, (bool, str))
                validated.pattern[value] = Pattern(value)

        # check that we did not forget about any field
        for field in validated.get_fields():
            assert validated.get(field) is not None

        # check that the python version has a valid format
        validated.get_python_version()

        return validated


class ValidatedConfig(Config):
    pattern: dict[str | bool, Pattern]

    def __init__(self):
        super().__init__()
        self.pattern = {}

    def get_pattern(self, raw: str | bool | None) -> Pattern:
        """get a compiled pattern by its raw value"""

        assert raw is not None
        return self.pattern[raw]

    def get_python_version(self) -> tuple[int, int]:
        """return the parsed python version"""

        assert self.python_version is not None

        if self.python_version == "auto":
            return sys.version_info[0:2]

        parts = self.python_version.split(".")
        assert len(parts) == 2

        return (int(parts[0]), int(parts[1]))

    def get_formatting(self) -> tuple[Pattern, list[FormatterCmd]]:
        """return formatting configs"""

        assert self.formatter_cmds is not None
        return self.get_pattern(self.format), self.formatter_cmds


@dataclass
class Profile:
    fields: Config
    description: str


PROFILES: dict[str, Profile] = {
    "default": Profile(
        Config(
            python_version="auto",
            keep_definitions=r"""
                not name_is('_[^_].*')
            """,
            keep_trailing_docstrings=r"""
                node_is('variable')
            """,
            add_implicit_none_return=r"""
                parent_node_is('class') and name_is('__init__')
            """,
            keep_if_statements=True,
            flatten_if=r"""
                value_is('TYPE_CHECKING')
            """,
            add_redundant_ellipsis=False,
            keep_variable_value=r"""
                annotation_is('TypeAlias|([tT]ype(\\[.*\\])?)')
                or value_is('(TypeVar|TypeVarTuple|ParamSpec)\\(.*\\)')
                or value_is('(NamedTuple|NewType|TypedDict)\\(.*\\)')
                or (parent_node_is('module') and name_is('__all__'))
                or (parent_node_is('class') and name_is('__model__'))
            """,
            keep_unused_imports=False,
            format=False,
            formatter_cmds=[
                FormatterCmd(
                    name="isort",
                    cmdline=[
                        # "${dubstub_py_exe}",
                        # "-m",
                        "isort",
                        "--py",
                        "${dubstub_py_major}${dubstub_py_minor}",
                        "--profile",
                        "black",
                        "--settings",
                        "/dev/null",
                        "${dubstub_file_args}",
                    ],
                ),
                FormatterCmd(
                    name="black",
                    cmdline=[
                        # "${dubstub_py_exe}",
                        # "-m",
                        "black",
                        "--pyi",
                        "--target-version",
                        "py${dubstub_py_major}${dubstub_py_minor}",
                        "--skip-magic-trailing-comma",
                        "--fast",
                        "--config",
                        "/dev/null",
                        "${dubstub_file_args}",
                    ],
                ),
            ],
        ),
        """
        The default profile tries to have sensible defaults that match
        the official recommendations:

        - Private definitions are removed, and identified by exactly one leading `_`.
        - Trailing docstrings are kept for variables.
        - We add a `-> None` return type on functions that should have them.
        - `if` statements are kept, but `TYPE_CHECKING` guards are merged into the surrounding scope.
        - Variable values are kept if they define types according to the `typing` module.
        - Unused imports are remove.
        - Autoformatting is disabled, but will use isort and black with default settings if enabled.
        """,
    ),
    "no_privacy": Profile(
        Config(
            keep_definitions=True,
            keep_unused_imports=True,
        ),
        """
        This profile is the same as `default`, but with privacy disabled:

        - No definitions with "private" names are filtered out.
        - No unused imports are filtered out.
        """,
    ),
    "pyright": Profile(
        Config(
            keep_definitions=r"""
                not (node_is('function') and name_is('_[^_].*'))
            """,
            add_redundant_ellipsis=r"""
                not any_child_node_is('function|assigned|class')
            """,
            keep_trailing_docstrings=False,
        ),
        """
        This profiles tries to approximate `pyright`s stubgen behavior better:

        - Only private functions are removed.
        - Redundant ellipsis are added to a few locations.
        - Trailing docstrings are removed.
        """,
    ),
}

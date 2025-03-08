import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Type

from ..config import ValidatedConfig
from ..config.match_ctx import MatchContext, Tag
from ..source import AstConfig, Source

CONSTANT_TYPES: list[Type[Any]] = [
    str,
    bytes,
    bool,
    int,
    float,
    complex,
    type(...),
    type(None),
]


@dataclass
class Node:
    lines: list[str] = field(default_factory=list)
    """
    Usually a node is a single line, but with annotations and
    block constructs you can end up with more than one
    """

    children: list["Node"] = field(default_factory=list)
    """
    If this node can contain sub nodes, the are collected in this list.
    These children may or may not be indented when output, depending on group tag.
    """

    tags: set[Tag] = field(default_factory=set)
    """
    Tags to identify this node
    """

    def add_child(self, *tags: Tag) -> "Node":
        node = Node(tags=set(tags))
        self.children.append(node)
        return node

    def add_line(self, line: str, allow_multiline: bool = False):
        if not allow_multiline:
            assert "\n" not in line, line
        self.lines.append(line)

    def add_tag(self, tag: Tag):
        self.tags.add(tag)


class Logger:
    debug: bool = False

    def ignore_unhandled(self, msg: str):
        """syntax was ignored because we can not handle it yet"""

        print("Unexpected syntax ignored:", msg)

    def ignore_disabled(self, msg: str):
        """syntax was ignored because we have a config that disabled it"""

        if self.debug:
            print(msg)

    def ignore_intentional(self, msg: str):
        """syntax was intentionally ignored because it has no influence on type stubs"""

        if self.debug:
            print("Expected syntax ignored:", msg)


# pylint: disable-next=too-many-public-methods
class Stubber:
    source: Source
    config: ValidatedConfig
    used_names: set[str] | None
    logger: Logger

    def __init__(self, source: Source, config: ValidatedConfig, used_names: set[str] | None = None):
        self.source = source
        self.config = config
        self.used_names = used_names
        self.logger = Logger()

    def output(self, ast_module: ast.Module) -> str:
        # to get a more homogenous code structure, we pretend there is a parent for
        # a module ast node
        out = Node()
        self.stub(out, ast_module)
        assert len(out.children) == 1

        # fully stubbed module
        out = out.children[0]

        # render everything to a flat list of lines
        lines: list[str] = []

        def collect_lines(node: Node, indent: int):
            prefix = "    " * indent
            for l in node.lines:
                lines.append((prefix + l).rstrip())

            # remove trailing spacers
            children = node.children[:]
            while children and Tag.SPACER in children[-1].tags:
                children.pop()

            for child in children:
                if Tag.MODULE in node.tags:
                    nested_indent = indent
                else:
                    nested_indent = indent + 1
                collect_lines(child, nested_indent)

        collect_lines(out, 0)

        ret = "\n".join(lines) + "\n"
        return ret

    def stub(self, parent: Node, obj: ast.AST):
        match obj:
            # module entrypoint
            case ast.Module():
                self.stub_module(parent, obj)

            # imports
            case ast.Import() | ast.ImportFrom():
                self.stub_import(parent, obj)

            # assignments (eg constant definitions)
            case ast.Assign() | ast.AnnAssign():
                self.stub_assign(parent, obj)

            # class definition
            case ast.ClassDef():
                self.stub_class(parent, obj)

            # function definitions
            case ast.FunctionDef() | ast.AsyncFunctionDef():
                self.stub_func(parent, obj)

            # expressions (eg doc comments)
            case ast.Expr():
                self.stub_expr(parent, obj)

            # if
            case ast.If():
                self.stub_if(parent, obj)

            # try
            case ast.Try():
                self.stub_try(parent, obj)
            # pylint: disable-next=no-member
            case _ if sys.version_info >= (3, 11) and isinstance(obj, ast.TryStar):
                self.stub_try_star(parent, obj)

            # try
            case ast.With():
                self.stub_with(parent, obj)

            # type alias
            # pylint: disable-next=no-member
            case _ if sys.version_info >= (3, 12) and isinstance(obj, ast.TypeAlias):
                self.stub_type_alias(parent, obj)

            # intentionally ignored
            case (
                ast.Pass()
                | ast.For()
                | ast.Call()
                | ast.Assert()
                | ast.Delete()
                | ast.Raise()
                | ast.AugAssign()
                | ast.While()
                | ast.Match()
            ):
                self.log_stub_ignore(obj)

            # fallback
            case _:
                self.logger.ignore_unhandled(f"{type(obj).__name__} statement (`{self.unparse(obj)}`)")

    def stub_module(self, parent: Node, obj: ast.Module):
        body = obj.body
        type_ignores = obj.type_ignores
        if type_ignores:
            self.logger.ignore_unhandled("Type comment on module")

        this = parent.add_child(Tag.MODULE)
        for node in body:
            self.stub(this, node)

    @staticmethod
    def import_is_export(name: ast.alias) -> bool:
        if name.name == "*":
            return True

        if name.asname is None:
            return False

        return name.name == name.asname

    @staticmethod
    def get_imported_name(name: ast.alias) -> str:
        if name.asname is not None:
            return name.asname

        if "." not in name.name:
            return name.name

        return name.name.split(".")[0]

    def stub_import(self, parent: Node, obj: ast.Import | ast.ImportFrom):
        tags = {Tag.IMPORT}

        keep_unused_import = self.is_match(self.config.keep_unused_imports, parent, tags)
        if not keep_unused_import and self.used_names is not None:
            used_names = self.used_names

            new_names: list[ast.alias] = []
            for alias_name in obj.names:
                name = self.get_imported_name(alias_name)

                keep_import = name == "*" or name in used_names or self.import_is_export(alias_name)
                if keep_import:
                    new_names.append(alias_name)

            # everything got filtered out, drop the import statement
            if not new_names:
                return

            # modify import to remove the unused names
            obj.names.clear()
            obj.names.extend(new_names)

        line = self.unparse(obj)
        this = Node()
        this.add_tag(*tags)
        this.add_line(line)
        insert_pos = len(parent.children)

        parent.children.insert(insert_pos, this)

    # pylint: disable-next=too-many-locals
    def stub_assign(self, parent: Node, obj: ast.Assign | ast.AnnAssign):
        targets: list[ast.expr] | ast.Name | ast.Attribute | ast.Subscript
        value: ast.expr | None
        type_comment: str | None
        annotation: ast.expr | None
        simple: int | None
        tags = {Tag.VARIABLE}

        # normalize both cases into one
        match obj:
            case ast.Assign(targets, value, type_comment):
                annotation = None
                simple = None
            case ast.AnnAssign(target, annotation, value, simple):
                targets = target
                type_comment = None

        if type_comment:
            self.logger.ignore_unhandled("Type comment on variable")

        targets_unparsed = self.unparse_assign_target(targets, simple)
        if "." in targets_unparsed:
            # If we have an assignment of the form `x.y = ...`, then we interpret this
            # as a modification, not a definition, and
            # do not output this
            return

        # determine name of this variable.
        name = targets_unparsed.split("=")[0].strip()

        # node for this assignment
        this = Node(tags=tags)

        # annotation
        annotation_fragment = ""
        annotation_pattern = None
        if annotation is not None:
            annotation_unparsed = self.unparse_type_expr(annotation)
            annotation_fragment = ": " + annotation_unparsed
            this.add_tag(Tag.ANNOTATED)
            annotation_pattern = annotation_unparsed

        # value
        value_fragment = ""
        value_pattern = None
        if value is not None:
            value_unparsed = self.unparse(value)
            value_fragment = " = " + value_unparsed
            this.add_tag(Tag.ASSIGNED)
            value_pattern = value_unparsed

        keep_variable_value = self.is_match(
            self.config.keep_variable_value,
            parent,
            tags,
            name=name,
            annotation=annotation_pattern,
            value=value_pattern,
        )

        if not keep_variable_value and value_fragment != "":
            self.logger.ignore_disabled(f"Pruning value of variable {name}")
            value_fragment = " = ..."

        line = targets_unparsed + annotation_fragment + value_fragment
        this.add_line(line)

        keep_definitions = self.is_match(
            self.config.keep_definitions,
            parent,
            tags,
            name=name,
            annotation=annotation_pattern,
            value=value_pattern,
        )
        if not keep_definitions:
            self.logger.ignore_disabled(f"Pruning variable {name}")
            return

        parent.children.append(this)

    # pylint: disable-next=too-many-locals
    def stub_class(self, parent: Node, obj: ast.ClassDef):
        name = obj.name
        bases = obj.bases
        keywords = obj.keywords
        body = obj.body
        decorator_list = obj.decorator_list
        tags = {Tag.CLASS}

        if not self.is_match(self.config.keep_definitions, parent, tags, name=name):
            self.logger.ignore_disabled(f"Pruning class {name}")
            return

        this = parent.add_child(*tags)

        # decorators
        decorators_unparsed = [self.unparse(decorator) for decorator in decorator_list]
        for decorator in decorators_unparsed:
            this.add_line(f"@{decorator}")

        # generics
        generics = ""
        if sys.version_info >= (3, 12):
            generics = self.unparse_type_params(obj.type_params)

        # bases and keywords
        bases_unparsed = [self.unparse(base) for base in bases]
        for keyword in keywords:
            assert keyword.arg is not None
            bases_unparsed.append(f"{keyword.arg} = {self.unparse(keyword.value)}")

        sig_bases = ""
        if bases_unparsed:
            sig_bases = f"({', '.join(bases_unparsed)})"

        # signature
        this.add_line(f"class {name}{generics}{sig_bases}:")

        # recursively stub class contents
        for child_node in body:
            self.stub(this, child_node)

        # if we wrote no line, we need to add ...
        self.check_body_ellipsis(parent, this, name=name)

        # we add an empty line as a spacer after every function
        parent.add_child(Tag.SPACER).add_line("")

    # pylint: disable-next=too-many-locals
    def stub_func(self, parent: Node, obj: ast.FunctionDef | ast.AsyncFunctionDef):
        name: str = obj.name
        args: ast.arguments = obj.args
        body: list[ast.stmt] = obj.body
        decorator_list: list[ast.expr] = obj.decorator_list
        returns: ast.expr | None = obj.returns
        type_comment: str | None = obj.type_comment
        is_async_func: bool = isinstance(obj, ast.AsyncFunctionDef)
        tags = {Tag.FUNCTION}

        if not self.is_match(self.config.keep_definitions, parent, tags, name=name):
            self.logger.ignore_disabled(f"Pruning function {name}")
            return

        # commit to emitting a function
        this = parent.add_child(*tags)

        if type_comment:
            self.logger.ignore_unhandled("Type comment on function")

        # decorators
        decorators_unparsed = [self.unparse(decorator) for decorator in decorator_list]
        for decorator in decorators_unparsed:
            this.add_line(f"@{decorator}")

        # generics
        generics = ""
        if sys.version_info >= (3, 12):
            generics = self.unparse_type_params(obj.type_params)

        # signature
        args_unparsed = self.unparse_arguments(args)

        if returns is not None:
            returns_unparsed = " -> " + self.unparse_type_expr(returns)
        elif self.is_match(self.config.add_implicit_none_return, parent, tags, name=name):
            returns_unparsed = " -> None"
        else:
            returns_unparsed = ""

        signature = f"def {name}{generics}({args_unparsed}){returns_unparsed}:"
        if is_async_func:
            signature = "async " + signature
        this.add_line(signature)

        # check if we have a doc string in the body to keep
        if body and self.as_string_constant(body[0]) is not None:
            self.stub(this, body[0])

        # make sure we have dots if there is nothing else
        self.check_body_ellipsis(parent, this, name=name)

        # we add an empty line as a spacer after every function
        parent.add_child(Tag.SPACER).add_line("")

    def stub_expr(self, parent: Node, obj: ast.Expr):
        match obj.value:
            case ast.Constant() if self.as_string_constant(obj.value) is not None:
                keep_docstring = False

                if not parent.children:
                    # regular docstring
                    keep_docstring = True
                else:
                    # potential inner docstring
                    preceding = parent.children[-1]
                    if self.is_match(self.config.keep_trailing_docstrings, parent, preceding.tags):
                        keep_docstring = True

                if keep_docstring:
                    raw_lit = self.source.unparse_original_source(obj)
                    parent.add_child(Tag.DOCSTRING).add_line(raw_lit, allow_multiline=True)
            case ast.Constant() if any(isinstance(obj.value.value, t) for t in CONSTANT_TYPES):
                self.log_stub_ignore(obj)
            case _:
                self.log_stub_ignore(obj)

    def stub_if(self, parent: Node, obj: ast.If):
        # we handle some ifs specially
        test = obj.test
        test_unparsed = self.unparse(test)

        tags = {Tag.IF}

        # lines guarded by "TYPE_CHECKING" are treated transparently
        skip_first_body = False
        if self.is_match(self.config.flatten_if, parent, tags, value=test_unparsed):
            # merge the if contents to the outside scope
            for child in obj.body:
                self.stub(parent, child)
            skip_first_body = True

        # we then emit the if itself with removed bodies
        if self.is_match(self.config.keep_if_statements, parent, tags=tags):
            this = parent.add_child(*tags)
            this.add_line(f"if {test_unparsed}:")

            if not skip_first_body:
                for child in obj.body:
                    self.stub(this, child)
            self.check_body_ellipsis(parent, this)

            orelse = obj.orelse

            # handle any intermediate elif cases
            while len(orelse) == 1 and isinstance(orelse[0], ast.If):
                test = orelse[0].test
                test_unparsed = self.unparse(test)

                this = parent.add_child(*tags)
                this.add_line(f"elif {test_unparsed}:")

                for child in orelse[0].body:
                    self.stub(this, child)
                self.check_body_ellipsis(parent, this)

                orelse = orelse[0].orelse

            # handle any final else
            if orelse:
                this = parent.add_child(*tags)
                this.add_line("else:")
                for child in orelse:
                    self.stub(this, child)
                self.check_body_ellipsis(parent, this)

    def stub_try(self, parent: Node, obj: ast.Try):
        # for try statements we just flatten the body into the parent
        for child in obj.body:
            self.stub(parent, child)

    if sys.version_info >= (3, 11):
        # pylint: disable-next=no-member
        def stub_try_star(self, parent: Node, obj: ast.TryStar):
            # for try statements we just flatten the body into the parent
            for child in obj.body:
                self.stub(parent, child)

    def stub_with(self, parent: Node, obj: ast.With):
        # for with statements we just flatten the body into the parent
        for child in obj.body:
            self.stub(parent, child)

    if sys.version_info >= (3, 12):
        # pylint: disable-next=no-member
        def stub_type_alias(self, parent: Node, obj: ast.TypeAlias):
            generics = self.unparse_type_params(obj.type_params)
            unparsed = f"type {obj.name.id}{generics} = {self.unparse_type_expr(obj.value)}"
            parent.add_child(Tag.TYPE_ALIAS).add_line(unparsed)

    def check_body_ellipsis(self, parent: Node, this: Node, name: str | None = None):
        if not this.children:
            this.add_child(Tag.ELLIPSIS).add_line("...")
        elif self.is_match(self.config.add_redundant_ellipsis, parent, this.tags, children=this.children, name=name):
            this.add_child(Tag.ELLIPSIS).add_line("...")

    def log_stub_ignore(self, obj: ast.AST):
        self.logger.ignore_intentional(f"{type(obj).__name__} statement")

    def as_string_constant(self, obj: ast.AST) -> str | None:
        if isinstance(obj, ast.Expr):
            obj = obj.value
        if isinstance(obj, ast.Constant) and isinstance(obj.value, str):
            return obj.value
        return None

    def unparse(self, obj: ast.AST) -> str:
        return self.source.unparse(obj)

    # pylint: disable-next=too-many-return-statements
    def unparse_type_expr(self, expr: ast.expr) -> str:
        """
        Convert an expression that is used in type annotation position
        to syntax appropriate for a typestub.

        Mostly this means identify string literals and replacing them with their content.
        """

        match expr:
            case ast.Subscript(value, slc, ast.Load()):
                prefix = self.unparse(value)
                if prefix == "Literal":
                    return self.source.unparse_original_source(expr)

                if isinstance(slc, ast.Tuple):
                    args = slc.elts
                else:
                    args = [slc]

                slc_unparsed_parts: list[str] = []
                for i, arg in enumerate(args):
                    if i > 0 and prefix == "Annotated":
                        slc_unparsed_parts.append(self.unparse(arg))
                    else:
                        slc_unparsed_parts.append(self.unparse_type_expr(arg))

                slc_unparsed = ", ".join(slc_unparsed_parts)
                return f"{prefix}[{slc_unparsed}]"
            case ast.Tuple(elts, ast.Load()):
                return "(" + ", ".join(self.unparse_type_expr(elt) for elt in elts) + ")"
            case ast.List(elts, ast.Load()):
                return "[" + ", ".join(self.unparse_type_expr(elt) for elt in elts) + "]"
            case ast.BinOp(left, ast.BitOr(), right):
                return self.unparse_type_expr(left) + " | " + self.unparse_type_expr(right)
            case ast.Constant(value) if isinstance(value, str):
                # check if we can parse the string as expression,
                # then return the unparsed expression
                try:
                    return self.unparse(self.source.parse_expr(value))
                except SyntaxError:
                    return self.unparse(expr)
            case _:
                # return unchanged
                return self.unparse(expr)

    def unparse_assign_target(
        self,
        targets: list[ast.expr] | ast.Name | ast.Attribute | ast.Subscript,
        simple: int | None,
    ) -> str:
        # target(s)
        if isinstance(targets, list):
            targets_unparsed = " = ".join([self.unparse(target) for target in targets])
        else:
            targets_unparsed = self.unparse(targets)
            if simple is not None and not simple:
                targets_unparsed = f"({targets_unparsed})"

        return targets_unparsed

    def unparse_arg(self, arg: ast.arg, val: None | ast.expr, keep_val: bool = False) -> str:
        if arg.type_comment:
            self.logger.ignore_unhandled("Type comment on function arg")

        ret = f"{arg.arg}"

        if arg.annotation is not None:
            ret += ": " + self.unparse_type_expr(arg.annotation)

        if val is not None:
            if keep_val:
                ret += " = " + self.unparse(val)
            else:
                ret += " = ..."

        return ret

    # pylint: disable-next=too-many-locals
    def unparse_arguments(self, ast_args: ast.arguments) -> str:
        posonlyargs = ast_args.posonlyargs
        args = ast_args.args
        vararg = ast_args.vararg
        kwonlyargs = ast_args.kwonlyargs
        kw_defaults = ast_args.kw_defaults
        kwarg = ast_args.kwarg
        defaults = ast_args.defaults

        def_counter = 0
        kw_def_counter = 0

        # the defaults variables contains the last N defaults, but for convenience
        # we compute an list where the initial skipped values are mapped to None
        aligned_defaults: list[None | ast.expr] = [None] * (len(posonlyargs) + len(args))
        gap = len(aligned_defaults) - len(defaults)
        aligned_defaults[gap:] = defaults

        unparsed_args: list[str] = []
        if posonlyargs:
            for arg in posonlyargs:
                val: ast.expr | None = None
                val = aligned_defaults[def_counter]
                def_counter += 1

                unparsed_args.append(self.unparse_arg(arg, val))
            unparsed_args.append("/")

        for arg in args:
            val: ast.expr | None = None
            val = aligned_defaults[def_counter]
            def_counter += 1

            unparsed_args.append(self.unparse_arg(arg, val))

        kwonlyargs_started = False

        if vararg is not None:
            unparsed_args.append("*" + self.unparse_arg(vararg, None))
            kwonlyargs_started = True

        if kwonlyargs:
            if not kwonlyargs_started:
                unparsed_args.append("*")
            for arg in kwonlyargs:
                val: ast.expr | None = None
                val = kw_defaults[kw_def_counter]
                kw_def_counter += 1

                unparsed_args.append(self.unparse_arg(arg, val))

        if kwarg is not None:
            unparsed_args.append("**" + self.unparse_arg(kwarg, None))

        ret = ", ".join(unparsed_args)
        return ret

    if sys.version_info >= (3, 12):
        # pylint: disable-next=no-member
        def unparse_type_params(self, type_params: ast.type_param) -> str:
            generics = ""
            if sys.version_info >= (3, 12):
                type_params_unparsed = []
                for type_param in type_params:
                    name = ""
                    bounds = ""
                    default = ""

                    match type_param:
                        # pylint: disable-next=no-member
                        case ast.TypeVar():
                            name = f"{type_param.name}"
                            if type_param.bound is not None:
                                bounds = f": {self.unparse_type_expr(type_param.bound)}"
                        # pylint: disable-next=no-member
                        case ast.TypeVarTuple():
                            name = f"*{type_param.name}"
                        # pylint: disable-next=no-member
                        case ast.ParamSpec():
                            name = f"**{type_param.name}"

                    if sys.version_info >= (3, 13) and type_param.default_value is not None:
                        default = f" = {self.unparse_type_expr(type_param.default_value)}"

                    type_params_unparsed.append(f"{name}{bounds}{default}")

                if type_params_unparsed:
                    generics = f"[{', '.join(type_params_unparsed)}]"
            return generics

    def _get_or_init_used_names(self) -> set[str]:
        if self.used_names is None:
            self.used_names = set()
        return self.used_names

    def discover_module_names(self, module: ast.Module):
        # discover all surviving names not brought into scope by imports
        for obj in module.body:
            match obj:
                case ast.Import() | ast.ImportFrom():
                    pass
                case ast.Assign() | ast.AnnAssign():
                    self.discover_any_names(obj)
                    self.discover_special_assign_names(obj)
                case _:
                    self.discover_any_names(obj)

    def discover_any_names(self, obj: ast.AST):
        names = self._get_or_init_used_names()

        for node in ast.walk(obj):
            if isinstance(node, ast.Name):
                names.add(node.id)

    def discover_special_assign_names(self, obj: ast.Assign | ast.AnnAssign):
        names = self._get_or_init_used_names()
        targets: list[ast.expr] | ast.Name | ast.Attribute | ast.Subscript
        value: ast.expr | None
        simple: int | None
        annotation: ast.expr | None

        # normalize both cases into one
        match obj:
            case ast.Assign(targets, value, _):
                simple = None
                annotation = None
            case ast.AnnAssign(target, annotation, value, simple):
                targets = target

        # check if we need to analyze the assignment value as a type
        if annotation is not None and value is not None:
            unparsed_annotation = self.unparse(annotation)
            if unparsed_annotation == "TypeAlias":
                re_parsed = self.source.parse_expr(self.unparse_type_expr(value))
                self.discover_any_names(re_parsed)

        # check if we need to analyze the assignment value as a list of types
        targets_unparsed = self.unparse_assign_target(targets, simple)
        if targets_unparsed == "__all__":
            match value:
                case ast.List(elts) | ast.Tuple(elts):
                    for elt in elts:
                        name = self.as_string_constant(elt)
                        if name is not None:
                            names.add(name)
                        else:
                            self.logger.ignore_unhandled(f"`__all__` list value {self.unparse(elt)} ({elt})")
                case _:
                    self.logger.ignore_unhandled(f"`__all__` value {self.unparse(value) if value else ''} ({value})")

    # pylint: disable-next=too-many-arguments
    def is_match(
        self,
        pattern: str | bool | None,
        parent: Node,
        tags: set[Tag],
        *,
        name: str | None = None,
        annotation: str | None = None,
        value: str | None = None,
        children: list[Node] | None = None,
    ) -> bool:

        child_tags: set[Tag] | None = None
        if children:
            child_tags = set()
            for child in children:
                child_tags.update(child.tags)

        ctx = MatchContext(
            parent_tags=parent.tags,
            tags=tags,
            file_path=str(self.source.relative_path),
            name=name,
            annotation=annotation,
            value=value,
            child_tags=child_tags,
        )
        return self.config.get_pattern(pattern).is_match(ctx)


def _stub_content(inp: str, relative_path: Path, config: ValidatedConfig, discover_imports: bool = False) -> str:
    source = Source(inp, relative_path, AstConfig(feature_version=config.get_python_version()))
    ast_module = source.parse_module()
    stubber = Stubber(source, config)
    if discover_imports:
        stubber.discover_module_names(ast_module)
    return stubber.output(ast_module)


def stubgen_single_file_src(inp: str, relative_path: Path, config: ValidatedConfig) -> str:
    # first generate the initial stub file
    stubbed = _stub_content(inp, relative_path, config)

    # then we re-stub the stub file, so that we can optionally analyze
    # imports and make sure we are idempotent
    stubbed = _stub_content(
        stubbed,
        relative_path,
        config,
        discover_imports=not config.get_pattern(config.keep_unused_imports).is_match(
            MatchContext(
                parent_tags={Tag.MODULE},
                tags={Tag.IMPORT},
                file_path=str(relative_path),
            )
        ),
    )

    return stubbed

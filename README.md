# dubstub

A simple "dumb" python type stub generator.

## Overview

Dubstub is a tool that takes a python codebase as an input (mix of `.py` and `.pyi` files),
and generates a matching set of `.pyi` files.

It does this purely based on a simple syntactic transformation of an input file,
with some hardcoded heuristics and customizable configs. It is designed that way to
avoid the following complications:

- It does not require running any kind of type inference or other semantic analysis of the python code,
  which might have performance overhead and have unpredictable output over time.
- It does not require following references to other files, so source files can be converted in isolation.
- It does not require the python code to be runnable, importable, or even be semantically correct.

It is intended to be simple and stable enough to use for automated use cases, without
requiring manual review and adjustment of its output. Naturally this will only
work well for python code with fairly "static" APIs without dynamically generated members,
though you can always mix it with manually defined `.pyi` files.

## Installation

This tool can be installed from PYPI or from source:

```bash
pip install dubstub
```

### Optional features (Package Extras):

- `def_fmt`: Installs `isort` and `black` in a known good version, so that they can be
  used by the default commands if formatting of generated `.pyi` files is enabled (it is off per default).
  ```bash
  pip install dubstub[def_fmt]
  ```
- `eval`: Installs dependencies needed for the `dubstub eval` and `dubstub diff` commands, which are not
  necessary for normal operation of the tool.
  ```bash
  pip install dubstub[eval]
  ```

## Development

To work on this tool itself, you can set up your environment like this:

- Create a venv and activate it.
- Run `pip install -e .[dev]` to install all dev dependencies and the package itself in editable mode.
- Run `dev/check.py` to run all style checks and pytest tests, including those for different python versions (using `uv`).

## Maintenance Status

This project is provided as-is. You may open issues and PRs, but I can not promise that I will react to them.

## Usage

### CLI

For details see `dubstub --help`. As a quick overview:

- `dubstub gen` generates type stubs for a provided file or directory tree. Example:
  ```sh
  dubstub gen --input ./src --output ./out
  ```
- `dubstub config` allows checking which config settings apply. Example:
  ```sh
  dubstub config --show-format toml --profile pyright
  ```
- `dubstub eval` allows evaluating the typestub generation of multiple tools, by generating stubs with all of them. Example:
  ```sh
  dubstub eval --input ./src --output ./out --format True --profile pyright
  ```
- `dubstub diff` can show the differences of the output of `dubstub eval` in a compact way. Example:
  ```sh
  dubstub diff --eval ./out | less -R
  ```

### From code

The tool can also be directly invoked from python code:

#### Wrapping main function

```python
from dubstub import main

if __name__ == "__main__":
    main()
```

#### Generating stubs

```python
from pathlib import Path
from dubstub import generate_stubs

# stub single file
generate_stubs(Path("input.py"), Path("output.pyi"))

# stub entire directory tree
generate_stubs(Path("input_dir/"), Path("output_dir/"))
```

#### Custom configs

```python
from pathlib import Path
from dubstub import Config, generate_stubs

# Loading config from file
config = Config.parse_config(path=Path("pyproject.toml"))
generate_stubs(Path("input2.py"), Path("output2.pyi"), config=config)

# Constructing config
config = Config(
    profile="no_privacy",
    keep_unused_imports=False,
)
generate_stubs(Path("input1.py"), Path("output1.pyi"), config=config)
```

## Config

This tool has a number of config settings that can be configured in a number of ways.

In general, for any individual setting, the following precedence applies:

- If the setting is explicit set on the commandline or in code, use it.
- If the setting is explicitly set in a config file that has been loaded, use it.
- If a config profile is selected that defines the setting, use the setting from the profile.
- As a final fallback, use the setting from the `default` profile.

The usage of config files is optional. If one is used, it has to have the `toml`
format, and define all config settings under the `tool.dubstub` key. The filename
is arbitrary, so you can store the settings either in a `pyproject.toml`,
or in a separate file.

### Config Settings

<!-- CONFIG_START -->
<table>
<thead>
<tr>
<th>Config Setting</th>
<th>Description</th>
</tr>
</thead>
<tbody>
<tr>
<td><p><code>profile</code></p>
<p>type: <code>str</code></p>
</td>
<td><p>Base profile to use for config settings.</p>
<p>Any explicitly set config values will overwrite those defined by the profile.</p>
</td>
</tr>
<tr>
<td><p><code>python_version</code></p>
<p>type: <code>str</code></p>
</td>
<td><p>Version of python syntax to target.</p>
<p>Valid forms are <code>&quot;X.Y&quot;</code> and <code>&quot;auto&quot;</code>, the latter of which derives
the version from the current python interpreter.</p>
</td>
</tr>
<tr>
<td><p><code>keep_definitions</code></p>
<p>type: <code>Pattern</code></p>
</td>
<td><p>Whether to keep a class, function, or variable definition during type stubbing.</p>
<p>This can be used to remove private elements (ie, those starting with a single <code>_</code>).</p>
</td>
</tr>
<tr>
<td><p><code>keep_trailing_docstrings</code></p>
<p>type: <code>Pattern</code></p>
</td>
<td><p>Whether to keep a trailing docstring for an element.</p>
<p>A trailing docstring is defined as a string literal that is not the first
statement in a module, class or function block.</p>
<p>These kinds of docstrings are supported by some documentation generators and IDE
plugins.</p>
<p>Example:</p>
<pre lang="python"><code>class foo:
    &quot;&quot;&quot;normal docstring&quot;&quot;&quot;
    x: y = z
    &quot;&quot;&quot;trailing docstring&quot;&quot;&quot;
</code></pre>
</td>
</tr>
<tr>
<td><p><code>add_implicit_none_return</code></p>
<p>type: <code>Pattern</code></p>
</td>
<td><p>Whether to add a <code>-&gt; None</code> return type to a function that has not specified a
return type annotation.</p>
</td>
</tr>
<tr>
<td><p><code>keep_if_statements</code></p>
<p>type: <code>Pattern</code></p>
</td>
<td><p>Whether to keep an <code>if</code> statement.</p>
<p>If an <code>if</code> statement is kept, its condition expression will be kept fully,
and its body will be recursively stubbed.</p>
</td>
</tr>
<tr>
<td><p><code>flatten_if</code></p>
<p>type: <code>Pattern</code></p>
</td>
<td><p>Whether to flatten the first body of an <code>if</code> into the surrounding scope.</p>
<p>This setting combines with <code>keep_if_statements</code>: If an <code>if</code> statement is matched
by both, the first body of the kept <code>if</code> will be empty.</p>
<p>This does not apply to <code>elif</code> cases of an <code>if</code>.</p>
</td>
</tr>
<tr>
<td><p><code>add_redundant_ellipsis</code></p>
<p>type: <code>Pattern</code></p>
</td>
<td><p>Whether to add redundant ellipsis (<code>...</code>) statements to bodies of statements that are not empty after stubbing.</p>
<p>Example:</p>
<pre lang="python"><code>class foo:
    ... # always added
class bar:
    x = y
    ... # redundant
</code></pre>
</td>
</tr>
<tr>
<td><p><code>keep_variable_value</code></p>
<p>type: <code>Pattern</code></p>
</td>
<td><p>Whether to keep the assignment value of a variable definition.
If the value is not kept, it is replaced with an ellipsis (<code>...</code>).</p>
<p>Example:</p>
<pre lang="python"><code>foo = 42        # value kept
foo: bar = 42   # value kept
foo = ...       # value not kept
foo: bar = ...  # value not kept
</code></pre>
</td>
</tr>
<tr>
<td><p><code>keep_unused_imports</code></p>
<p>type: <code>Pattern</code></p>
</td>
<td><p>Whether to keep import statements that seem to not be used anywhere
in the module.</p>
<p>Note that this is a heuristic based on searching for the imported name,
it can have false positives, which erroneously consider an import used.</p>
<p>Both normal python code, as well the contents of <code>__all__</code> list strings will be considered.</p>
<p>Certain imports will be interpreted as re-exports, and always considered used.</p>
<p>For example, given this code:</p>
<pre lang="python"><code>x: Foo
</code></pre>
<p>Then imports would be considered like this:</p>
<pre lang="python"><code>from foo import Foo   # considered used
from bar import Bar   # considered not used
import X as X         # considered used (always)
import a.b.X as X     # considered not used
from Y import X as X  # considered used (always)
from Y import *       # considered used (always)
</code></pre>
<p>See also <a href="https://typing.readthedocs.io/en/latest/spec/distributing.html#import-conventions">https://typing.readthedocs.io/en/latest/spec/distributing.html#import-conventions</a></p>
</td>
</tr>
<tr>
<td><p><code>add_class_attributes_from_init</code></p>
<p>type: <code>Pattern</code></p>
</td>
<td><p>Whether to class attribute type annotations from <code>self.&lt;name&gt;: T</code> annotations
in <code>__init__()</code> methods.</p>
</td>
</tr>
<tr>
<td><p><code>format</code></p>
<p>type: <code>Pattern</code></p>
</td>
<td><p>Enable autoformatting of the generated typestub code.</p>
<p>The default output of this tool follows no consistent formatting style:
Individual lines either contain a single large statement, or are copy-pasted from the original source verbatim.</p>
<p>If enabled, the generated or copied <code>.pyi</code> files will be passed to the commands specified by <code>formatter_cmds</code>.</p>
</td>
</tr>
<tr>
<td><p><code>formatter_cmds</code></p>
<p>type: <code>list[FormatterCmd]</code></p>
</td>
<td><p>List of formatter cmds that will be executed on generated and copied <code>.pyi</code> files.</p>
<p>Each <code>FormatterCmd</code> is an object with an arbitrary <code>name</code>, and a <code>cmdline</code> list
that defines how to execute the command:</p>
<pre lang="toml"><code>[[tool.dubstub.formatter_cmds]]
name = &quot;&lt;cmd name&gt;&quot;
cmdline = [
    &quot;&lt;cmd&gt;&quot;,
    &quot;&lt;arg1&gt;&quot;,
    &quot;&lt;arg2&gt;&quot;,
    ...
]
</code></pre>
<p>There are a number of variable substitutions supported for the <code>cmdline</code> arguments:</p>
<ul>
<li><code>${dubstub_py_major}</code> will be replaced by the major version of python selected
with the <code>python_version</code> config setting.</li>
<li><code>${dubstub_py_minor}</code> will be replaced by the minor version of python selected
with the <code>python_version</code> config setting.</li>
<li><code>${dubstub_py_exe}</code> will be replaced by the path to the current python executable (<code>sys.executable</code>).</li>
<li><code>${dubstub_file_arg}</code> will be replaced with the path to a file that should be formatted in-place.</li>
<li><code>${dubstub_file_args}</code> will be replaced with the path to a file that should be formatted in-place,
and will also cause the argument to expand into multiple arguments, one for each file.</li>
</ul>
<p>The commands will be executed in series, with the output of one feeding into the next one.
The difference between the last two substitution options is that <code>dubstub_file_arg</code> will call the command
once for every single file, while <code>dubstub_file_args</code> will batch multiple files into a single command call.</p>
<p>Examples:</p>
<ul>
<li><code>cmdline = [&quot;black&quot;, &quot;${dubstub_file_arg}&quot;]</code>
will cause these command calls:
<pre lang="bash"><code>black file1.pyi
black file2.pyi
black file3.pyi
...
</code></pre>
</li>
<li><code>cmdline = [&quot;black&quot;, &quot;${dubstub_file_args}&quot;]</code>
will cause these command calls:
<pre lang="bash"><code>black file1.pyi file2.pyi file3.pyi ...
</code></pre>
</li>
</ul>
</td>
</tr>
</tbody>
</table>
<!-- CONFIG_END -->

### Patterns

Most of the config settings are patterns that get evaluated against a node in the
AST of the stubbed file to decide if the config should apply to the node.

A `Pattern` can be specified in two ways:

- As a boolean.
- As a string that contains a python expression that evaluates to a boolean.

The python expression is allowed to make use of parenthesis, `and`, `or` and `not`, and of special function calls
to check properties of the current node. The expression may also contain line breaks.

Currently all provided functions take a single string literal as argument,
which is interpreted as a regular expression that is matched against the full value
(`re.fullmatch` semantic).

#### Functions

| Function Name       | Description |
| ------------------- | ----------- |
| `parent_node_is`    | Match against the tags of the parent AST node. |
| `node_is`           | Match against the tags of the AST node. |
| `file_path_is`      | Match against the path to the current source file, relative to the path the stub generator was started with. |
| `name_is`           | Match against the name of the AST node, if it has one. |
| `annotation_is`     | Match against the stringified annotation expression of an AST node, if it has one. |
| `value_is`          | Match against the stringified assignment or condition expression of an AST node, if it has one. |
| `any_child_node_is` | Match against the tags of all child AST nodes. |

#### Tags

| Tag value | Description |
| --------- | ----------- |
| `module`     | Module |
| `class`      | Class definition (`class ...`) |
| `function`   | Function definition (`def ...`) |
| `import`     | Import statement |
| `type_alias` | Explicit type alias statement (`type Foo = ...`) |
| `variable`   | Variable definition (`x: y`, `x: y = z` or `x = z`) |
| `annotated`  | Variable with type annotation (`x: y` or `x: y = z`) |
| `assigned`   | Variable with value assignment (`x = z` or `x: y = z`) |
| `if`         | If statement |
| `docstring`  | Docstring expression statement |
| `ellipsis`   | Ellipsis expression statement (`...`) |

### Profiles

<!-- PROFILE_START -->
#### Profile `default`

The default profile tries to have sensible defaults that match
the official recommendations:

- Private definitions are removed, and identified by exactly one leading `_`.
- Trailing docstrings are kept for variables.
- We add a `-> None` return type on functions that should have them.
- `if` statements are kept, but `TYPE_CHECKING` guards are merged into the surrounding scope.
- Variable values are kept if they define types according to the `typing` module.
- Class attributes are also looked for in `__init__()` method assignments.
- Unused imports are remove.
- Autoformatting is disabled, but will use isort and black with default settings if enabled.

Exact config settings set by the profile:

```toml
[tool.dubstub]
python_version = "auto"
keep_definitions = """
    not name_is('_[^_].*')
"""
keep_trailing_docstrings = """
    node_is('variable')
"""
add_implicit_none_return = """
    parent_node_is('class') and name_is('__init__')
"""
keep_if_statements = true
flatten_if = """
    value_is('TYPE_CHECKING')
"""
add_redundant_ellipsis = false
keep_variable_value = """
    annotation_is('TypeAlias|([tT]ype(\\\\[.*\\\\])?)')
    or value_is('(TypeVar|TypeVarTuple|ParamSpec)\\\\(.*\\\\)')
    or value_is('(NamedTuple|NewType|TypedDict)\\\\(.*\\\\)')
    or (parent_node_is('module') and name_is('__all__'))
    or (parent_node_is('class') and name_is('__model__'))
"""
keep_unused_imports = false
add_class_attributes_from_init = true
format = false

[[tool.dubstub.formatter_cmds]]
name = "isort"
cmdline = [
    "isort",
    "--py",
    "${dubstub_py_major}${dubstub_py_minor}",
    "--profile",
    "black",
    "--settings",
    "/dev/null",
    "${dubstub_file_args}",
]

[[tool.dubstub.formatter_cmds]]
name = "black"
cmdline = [
    "black",
    "--pyi",
    "--target-version",
    "py${dubstub_py_major}${dubstub_py_minor}",
    "--skip-magic-trailing-comma",
    "--fast",
    "--config",
    "/dev/null",
    "${dubstub_file_args}",
]
```
#### Profile `no_privacy`

This profile is the same as `default`, but with privacy disabled:

- No definitions with "private" names are filtered out.
- No unused imports are filtered out.

Exact config settings set by the profile:

```toml
[tool.dubstub]
keep_definitions = true
keep_unused_imports = true
```
#### Profile `pyright`

This profiles tries to approximate `pyright`s stubgen behavior better:

- Only private functions are removed.
- Redundant ellipsis are added to a few locations.
- Trailing docstrings are removed.

Exact config settings set by the profile:

```toml
[tool.dubstub]
keep_definitions = """
    not (node_is('function') and name_is('_[^_].*'))
"""
keep_trailing_docstrings = false
add_redundant_ellipsis = """
    not any_child_node_is('function|assigned|class')
"""
```

<!-- PROFILE_END -->

## Specification

### Filesystem traversal

The `gen` and `eval` commands can either process a single file, or a whole directory tree:

- `.py` files will be stubbed to `.pyi` files and optionally formatted.
- `.pyi` files will be copied as-is and optionally formatted.
- `py.typed` files will be copied as-is.
- If there is both a `.py` and `.pyi` file for the same module, the `.py`
  file will be ignored in favour of th `.pyi` file.
- Other files will be ignored.
- Directories will be recursively traversed.

The `--input` and `--output` options accept the following combination of of arguments:

- If the input path is a file, and the output path either does not exist or is a file,
  then the output will be written to the output path (even if the file name does not match the input).
- If the input path is a directory, and the output path either does not exist or is a directory,
  the same relative directory structure found in input will be created in output, and
  any files in it recursively processed.
- If the input path is a file, and the output path is an existing directory, then
  the output file will be written to the directory.

Any output directory that would be created as part of this processed will be
cleaned out if they already exist beforehand, to prevent polluting the output with old files.

This cleanup process skips over directories without python files (eg as found in namespace packages),
so that only directories that contain python files will get replaced.

This allows the type stubs of different namespace packages to be written into the same shared output directory
without them overwriting each other.

### Stubbing

At its most basic, this tool takes type-annotated python code, and removes any code
not relevant for type checkers.

There is a link to the official specification of what that should entail at the end of the readme,
and this tool tries to follow that, but it will also do some simplifications due to its
syntax-only nature.

We define the tools behavior mostly in terms of what it keeps of the original source code,
and what it removes, though there are also some explicit transformations of code involved.

The process is recursive, and mostly works the same for the body of the module, a class, or a control flow statement. Starting with a source file, the following logic applies:

- For a module, all statements in it are recursively converted to type stubs.
- Imports statements (`import ...` or `from ... import ...`) will get filtered or entirely removed.
  - Relevant config settings:
    - `keep_trailing_docstrings`
    - `keep_unused_imports`
- "Variable definitions" in the form of assignments like `x [: y] [= z]` will get simplified or removed.
  - Assignment that do not target a variable directly are ignored (eg, `obj.field = 42`).
  - The `y` expression will be interpreted and rewritten as a "type expression" (see below).
  - Relevant config settings:
    - `keep_definitions`
    - `keep_trailing_docstrings`
    - `keep_variable_value`
- Class definitions will get simplified or removed.
  - Class decorators are kept as they are.
  - Class bases and keyword arguments are kept as they are.
  - All statements in the class body are recursively converted to type stubs.
  - Classes that would be left empty will contain an ellipsis (`...`).
  - Relevant config settings:
    - `add_redundant_ellipsis`
    - `keep_definitions`
    - `keep_trailing_docstrings`
- Function definitions will get simplified or removed.
  - Function decorators are kept as they are.
  - The function signature is stubbed:
    - Argument type annotations will be interpreted and rewritten as a "type expression" (see below).
    - Any return type annotation will be interpreted and rewritten as a "type expression" (see below).
    - Default value assignments are replaced by an ellipsis (`...`).
  - All statements in the function body are removed.
  - Relevant config settings:
    - `add_implicit_none_return`
    - `add_redundant_ellipsis`
    - `keep_definitions`
    - `keep_trailing_docstrings`
- (Doc)String expressions are kept as they are or removed.
  - If the docstring is the first statement in the body of an outer statement, it is kept.
  - Otherwise the `keep_trailing_docstrings` config of the preceding statement applies.
  - Any other expression statement is not kept.
- If statements are either kept, removed, or flattened into the outer scope.
  - If they are kept, their bodies will be recursively converted to type stubs.
  - Keeping if statements supports conditional code that checks `sys.platform`, for example.
  - `if`/`elif`/`else` bodies that would be left empty will contain an ellipsis (`...`).
  - Relevant config settings:
    - `add_redundant_ellipsis`
    - `flatten_if`
    - `keep_if_statements`
    - `keep_trailing_docstrings`
- Try and With statements are flattened into the outer scope.
- Any other statement type is ignored, and not kept.
  - Some statements are explicitly ignored, like `pass`, `del`, `for`, `assert`, `raise`, function calls, etc.
  - Other statement will also be ignored, but trigger a warning if encountered, to indicate that this tool is
    lacking explicit support for them for now.

### Type expressions

We define a "type expression" as a python expression that has to be evaluated as a type, eg because it was written at type annotation position in the code. The [official docs](https://typing.readthedocs.io/en/latest/spec/annotations.html#annotation-expression) define this term as well, and draw a distinction between an "annotated expression" and a "type expression".

We mainly care about this because types in a type expression can be quoted to avoid cyclic references during normal evaluation of code. Eg all these expressions have the same meaning: `Optional[MyType]`, `"Optional[MyType]"`, `Optional["MyType"]`. During type stubbing, we want to remove these superfluous quotes, as `.pyi` files are allowed to have cycling references for type annotations.

Due to the constraints of this tool, we are a less precise with following the official definitions. The issue here is that we do not actually have a semantic type analysis of the code, so we can only evaluate type expressions based on their raw syntax and some heuristics.

Converting to unquoted from is again a recursive process:

- String expressions are replaced by their content: `"Foo" -> Foo`.
- `Literal[...]` is kept as it is.
- For `Annotated[ty, ...]`, the first index operator argument is recursively converted.
- For any other `Foo[..., ...]`, the index operator arguments are recursively converted (we assume its a generic).
- Likewise, lists `[..., ...]` are recursively converted (which handles cases like `Callable[[T], U]`).
- Chains of the bitor/union operator `... | ...` are recursively converted.
- Any other case has not been relevant for me so far, and is not handled yet. Generally unhandled syntax is kept as it is.

### Syntax Limitations

- The tool currently ignores `# type` comments entirely
- The tool does not currently support all syntax of the language, including future syntax of newer versions.

## Useful links

- [Official spec for stub files](https://typing.readthedocs.io/en/latest/spec/distributing.html#stub-files)
- [Original PEP484](https://peps.python.org/pep-0484/)

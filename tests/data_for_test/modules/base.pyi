"""
hello world

weird " \" ' \' stuff
"""
"single line"
'single line'
'''
multi line
'''
import x
import x.y.z as z
import a, b, c
import a as x, b as y, c as z
from x import y
from x import y as z
from . import y
from . import y as z
from ..a.b.c import y as z
def args(a, b: int = ...) -> None:
    ...

def foo() -> int:
    ...

def bar() -> int:
    """hello"""

def baz() -> None:
    """
    hello
    """

@decorated1
@decorated2
def tree() -> None:
    ...

BAZ = ...
BAR = ...
"""nice constant"""
FOO: int = ...
"""nice constant"""
class Foo:
    ...

@decorated
class Bar(Enum, foo = 42):
    x: int
    y = ...
    z: int = ...
    def foo(self, a, b: bool) -> int:
        ...

"""

"heh
""heheh
\"""heheheh
\"\"""heheheheh

"""
def params_no_default(pre1, pre2: int, /, mind1, mid2: int, *, post1, post2: int) -> None:
    ...

def params_default(pre1 = ..., pre2: int = ..., /, mid1 = ..., mid2: int = ..., *, post1 = ..., post2: int = ...) -> None:
    ...

def params_var(a, /, *args, b, **kwargs) -> None:
    ...

def params_var_annot(a, /, b, *args: int, c, **kwargs: int) -> None:
    ...

def params_mixed_default_1(pre1 = ..., /, mid1 = ..., *, post1 = ...) -> None:
    ...

def params_mixed_default_2(pre1, /, mid1 = ..., *, post1 = ...) -> None:
    ...

def params_mixed_default_3(pre1, /, mid1, *, post1 = ...) -> None:
    ...

def params_mixed_default_4(pre1, /, mid1, *, post1) -> None:
    ...

def params_mixed_default_5(pre1 = ..., /, mid1 = ..., *, post1) -> None:
    ...

def params_mixed_default_6(pre1 = ..., /, mid1 = ..., *args, post1, **kwargs) -> None:
    ...

def params_mixed_default_7(pre1 = ..., /, mid1 = ..., post1 = ..., **kwargs) -> None:
    ...

"hi"
def weird_ret() -> (Foo[Bar], None):
    ...

X: tuple[int, str]
X: foo.bar[int, str]
X: Callable[[Foo, Bar], Baz]
X: Literal[ "  x  " ]
def flatten_list(in_list: List[T] | List[List[T]] | X) -> List[T] | list[T]:
    ...

import bar
if TYPE_CHECKING:
    ...
else:
    import baz
if TYPE_CHECKING:
    ...
elif TYPE_CHECKING:
    ...
elif TYPE_CHECKING:
    ...
else:
    ...
import might_be_missing
__all__ = ['a', 'b']
__all__ = ('a', 'b')
__model__ = ...
Foo: TypeAlias = Callable[['Bar'], 'Baz']
if FOO:
    VAR = ...
    A = ...
elif BAR:
    VAR = ...
    B = ...
else:
    VAR = ...
    C = ...
a = ...
class Foo:
    __all__ = ...
    __all__ = ...
    __model__ = Foo

class foo:
    field: Annotated[str | None, '\n        text 1\n\n        text 2\n        '] = ...
    field: Annotated[str | None, 'text 1'] = ...
    field: Annotated[str | None, 'text'] = ...

import bar

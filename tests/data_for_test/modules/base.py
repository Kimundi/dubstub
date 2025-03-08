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

def args(a, b: int = 42):
    pass


def foo() -> int:
    return 0

def bar() -> int:
    """hello"""

    return 0

def baz():
    """
    hello
    """

    return 0

@decorated1
@decorated2
def tree():
    return 0

BAZ = 42

BAR = 42
"""nice constant"""

FOO: int = 42
"""nice constant"""

class Foo:
    pass

@decorated
class Bar(Enum, foo=42):
    x: int
    y = 42
    z: int = 42

    def foo(self, a, b: bool) -> int:
        pass

"""

"heh
""heheh
\"""heheheh
\"\"""heheheheh

"""

def params_no_default(pre1, pre2: int, /, mind1, mid2: int, *, post1, post2: int):
    pass

def params_default(pre1 = 1, pre2: int = 2, /, mid1 = 3, mid2: int = 4, *, post1 = 5, post2: int = 6):
    pass

def params_var(a, /, *args, b, **kwargs):
    pass

def params_var_annot(a, /, b, *args: int, c, **kwargs: int):
    pass

def params_mixed_default_1(pre1 = 1, /, mid1 = 2, *, post1 = 3):
    pass

def params_mixed_default_2(pre1, /, mid1 = 2, *, post1 = 3):
    pass

def params_mixed_default_3(pre1, /, mid1, *, post1 = 3):
    pass

def params_mixed_default_4(pre1, /, mid1, *, post1):
    pass

def params_mixed_default_5(pre1 = 1, /, mid1 = 2, *, post1):
    pass

def params_mixed_default_6(pre1 = 1, /, mid1 = 2, *args, post1, **kwargs):
    pass

def params_mixed_default_7(pre1 = 1, /, mid1 = 2, post1 = 3, **kwargs):
    pass

"hi"
b"hi"

def weird_ret() -> (Foo["Bar"], None):
    pass
X: tuple[int, str]
X: foo.bar[int, str]
X: Callable[["Foo", "Bar"], "Baz"]
X: Literal[ "  x  " ]
def flatten_list(in_list: List["T"] | List[List["T"]] | X) -> List[T] | list[T]:
    ...

if TYPE_CHECKING:
    import bar
else:
    import baz

if TYPE_CHECKING:
    pass
elif TYPE_CHECKING:
    pass
elif TYPE_CHECKING:
    pass
else:
    pass
try:
    import might_be_missing
except ImportError:
    pass
finally:
    pass
some.foo.bar.call(hahaha)
__all__ = ["a", "b"]
__all__ = ("a", "b")
__model__ = Foo
a
Foo: TypeAlias = Callable[["Bar"], "Baz"]
if FOO:
    VAR = 1
    A = a
elif BAR:
    VAR = 2
    B = b
else:
    VAR = 3
    C = c
a = 42
a.b.c = 42
class Foo:
    __all__ = ["a", "b"]
    __all__ = ("a", "b")
    __model__ = Foo
class foo:
    field: Annotated[
        str | None,
        """
        text 1

        text 2
        """,
    ] = None
    field: Annotated[
        str | None,
        "text 1",
    ] = None
    field: Annotated[
        str | None,
        "text",
    ] = None
with foo:
    import bar

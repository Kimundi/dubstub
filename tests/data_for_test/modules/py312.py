type MyList[T: int, U] = list[T]
type MyList[T: "int", U] = "list[T]"
type MyList[T: (int, float), U] = list[T]
type MyList[T: ("int", "float"), U] = "list[T]"

type MyTuple[*T] = tuple[*T]
# TODO: Parser behaves weird here, it generates `tuple[*T,]` for the value.
# type MyTuple[*T] = "tuple[*T]"

type Alias[**P] = Callable[P, int]
type Alias[**P] = "Callable[P, int]"

def f1[T: int, U](x: T):
    pass

async def f2[T: "int", U](x: T):
    pass

class Foo[T: int, U]:
    pass

class Foo[T: "int", U]:
    pass

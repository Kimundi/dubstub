type MyList[T: int, U] = list[T]
type MyList[T: int, U] = list[T]
type MyList[T: (int, float), U] = list[T]
type MyList[T: (int, float), U] = list[T]
type MyTuple[*T] = tuple[*T]
type Alias[**P] = Callable[P, int]
type Alias[**P] = Callable[P, int]
def f1[T: int, U](x: T) -> None:
    ...

async def f2[T: int, U](x: T) -> None:
    ...

class Foo[T: int, U]:
    ...

class Foo[T: int, U]:
    ...

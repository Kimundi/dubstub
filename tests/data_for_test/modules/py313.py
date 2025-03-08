type MyList[T = int] = list[T]
type MyList[T = "int"] = list[T]

def f1[T = int](x: T):
    pass

async def f2[T = "int"](x: T):
    pass

class Foo[T = int]:
    pass

class Bar[T = "int"]:
    pass

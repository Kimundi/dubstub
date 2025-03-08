from contextlib import contextmanager


value_int = 42
value_str = "hi"
value_dict = {}
value_list = [42, 312]
value_bool = True


def func(*args, **kwargs):
    pass


class klass:
    @staticmethod
    def func(*args, **kwargs):
        pass

    value = 42


class Error(Exception):
    pass


class Error2(Exception):
    pass


@contextmanager
def mgr():
    yield


def deco(func):
    def func(*args, **kwargs):
        pass

    return func


def class_deco(klass):
    return klass


class Base:
    pass


class Meta(type):
    def __new__(cls, name, bases, dct, **kwargs):
        x = super().__new__(cls, name, bases, dct)
        return x

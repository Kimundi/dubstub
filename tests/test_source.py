from pathlib import Path

from dubstub.source import AstConfig, Source

SOURCE = """

def a():
    pass

@dec1
@dec2
def b():
    pass

class c:
    pass

@dec1
@dec2
class d:
    pass

'''
hello world
'''

"""

SOURCE_SPLIT = [
    """def a():
    pass""",
    """@dec1
@dec2
def b():
    pass""",
    """class c:
    pass""",
    """@dec1
@dec2
class d:
    pass""",
    """'''
hello world
'''""",
]


def test_source():
    source = Source(SOURCE, Path("file.py"), AstConfig())
    module = source.parse_module()

    stmts: list[str] = []

    for stmt in module.body:
        stmts.append(source.unparse_original_source(stmt))

    assert stmts == SOURCE_SPLIT


def test_parse_expr():
    source = Source(SOURCE, Path("file.py"), AstConfig())
    source.parse_expr("42 < 14 and True != False")

from dubstub import toml

DATA = {
    "a": 42,
    "b": {
        "data": [
            {
                "foo": True,
            },
            {
                "bar": "hi",
            },
        ]
    },
}

TOML = """\
a = 42

[b]
data = [
    { foo = true },
    { bar = "hi" },
]
"""


def test_dumps():
    assert toml.dumps(DATA) == TOML


def test_loads():
    assert toml.loads(TOML) == DATA

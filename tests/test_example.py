# pylint: disable=import-outside-toplevel


def example1():
    from dubstub import main

    if __name__ == "__main__":
        main()


def example2():
    from pathlib import Path

    from dubstub import generate_stubs

    # stub single file
    generate_stubs(Path("input.py"), Path("output.pyi"))

    # stub entire directory tree
    generate_stubs(Path("input_dir/"), Path("output_dir/"))


def example3():
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

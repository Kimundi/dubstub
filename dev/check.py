#!/usr/bin/env python3

import os
import shlex
import shutil
import subprocess
import sys
from argparse import ArgumentParser
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]

DEV_CACHE = Path("dev/.cache")


def walk_tree(path: Path) -> Iterable[Path]:
    for dirname, _, filenames in os.walk(path):
        yield Path(dirname)
        for filename in filenames:
            yield Path(dirname) / filename


def walk_modules(root: Path) -> list[Path]:
    if root.is_file() and root.suffix == ".py":
        return [root]
    if root.is_dir():
        if (root / "__init__.py").exists():
            return [root]

        tmp: list[Path] = []
        for child in root.iterdir():
            tmp.extend(walk_modules(child))
        return tmp

    return []


def cmd(*args: str | Path, hidden: bool = True, expect_fail: str | None = None, env: dict[str, str] | None = None):
    cmd_args = [str(arg) for arg in args]

    print(f"* {shlex.join(cmd_args)}")

    if env is not None:
        env = {**os.environ.copy(), **env}

    if hidden:
        out = subprocess.run(
            cmd_args,
            check=False,
            encoding="utf-8",
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    else:
        out = subprocess.run(
            cmd_args,
            check=False,
            encoding="utf-8",
            env=env,
        )

    if expect_fail is None:
        if out.returncode != 0:
            if hidden:
                print(out.stdout)
            sys.exit(out.returncode)
    else:
        assert hidden
        if out.returncode == 0:
            print("! CMD did not fail")
            print(out.stdout)
            sys.exit(1)
        if expect_fail not in out.stdout:
            print(f"! CMD output did not contain {expect_fail}")
            print(out.stdout)
            sys.exit(1)


WHICH_MODE = os.F_OK | os.X_OK


def hide_path(executables: list[str]) -> str:
    env_path_raw_list = os.environ["PATH"].split(":")

    new_env_path_list_raw: list[str] = []
    for env_path_raw in env_path_raw_list:
        env_path = Path(env_path_raw)

        found_names: list[str] = []
        for executable in sorted(executables):
            path_raw = shutil.which(executable, mode=WHICH_MODE, path=env_path_raw)
            if path_raw:
                path = Path(path_raw)
                if path.parent == env_path:
                    found_names.append(path.name)

        if found_names:
            key = f"{env_path}, {found_names}"
            key = sha256(key.encode()).hexdigest()[:16]

            path_cache = (DEV_CACHE / f"PATH-{key}").resolve()

            if not path_cache.exists():
                path_cache.mkdir()
                for entry in env_path.iterdir():
                    if entry.name in found_names:
                        continue

                    if os.access(entry, WHICH_MODE):
                        (path_cache / entry.name).symlink_to(entry)

            assert path_cache.is_dir()
            env_path = path_cache

        new_env_path_list_raw.append(str(env_path))

    final_path = ":".join(new_env_path_list_raw)

    for executable in sorted(executables):
        assert shutil.which(executable, mode=WHICH_MODE, path=final_path) is None

    return final_path


def check_style(verbose: bool):
    paths: list[str] = [
        str(path)
        for root in ["src", "tests", "dev"]
        for path in walk_modules(Path(root))
        if "data_for_test" not in path.parts and ".cache" not in path.parts
    ]

    verbose_arg: list[str] = []
    if verbose:
        verbose_arg.append("--verbose")

    print("[Check/Fix formatting style]")
    # TODO: "check" mode vs "fix" mode
    cmd("isort", *verbose_arg, *paths)
    cmd("black", *verbose_arg, *paths)
    print()

    print("[Check types and lints]")
    cmd("pyright", *verbose_arg, *paths)
    cmd("pylint", *verbose_arg, *paths)
    print()


def check_doc():
    print("[Check README]")
    # copy2("README.md", f"{DEV_CACHE}/tmp.md")
    # cmd("diff", "--side-by-side", "--suppress-common-lines", "README.md", f"{DEV_CACHE}/tmp.md")
    cmd("dubstub", "config", "--gen-docs", "README.md")
    print()


@contextmanager
def cli_venv(extras: list[str], hidden_executables: list[str]):
    print(f"[Test CLI with extras {extras}]")
    venv_bin = dubstub_venv("3.10", extras)
    # hide all executables provided by extras
    hidden_paths = hide_path(sorted(set(["dubstub", *hidden_executables])))
    env = {
        "PATH": f"{venv_bin}:{hidden_paths}",
    }

    found = shutil.which("dubstub", path=env["PATH"])
    assert found is not None
    assert Path(found) == venv_bin / "dubstub"

    def dubstub_cmd(*args: str | Path, **kwargs: Any):
        cmd("dubstub", *args, **kwargs, env=env)

    yield dubstub_cmd

    print()


def check_cli():
    inp_path = DEV_CACHE / "input"
    inp_path.mkdir(exist_ok=True)
    out_path = DEV_CACHE / "output"
    out_path.mkdir(exist_ok=True)
    (inp_path / "file.py").touch()

    gen_ = ["gen", "--input", inp_path, "--output", out_path]
    eval_ = ["eval", "--input", inp_path, "--output", out_path]
    diff_ = ["diff", "--eval", out_path]

    with cli_venv([], ["pyright", "black", "isort", "stubgen"]) as dubstub:
        dubstub("--help")
        dubstub("gen", "--help")
        dubstub("eval", "--help")
        dubstub("diff", "--help")
        dubstub("config", "--help")
        dubstub("config")

        dubstub(*gen_)
        dubstub(*gen_, "--format=True", expect_fail="can be installed with `def_fmt` extra")

        dubstub(*eval_, "--format=True", expect_fail="can be installed with `def_fmt` extra")
        dubstub(*eval_, expect_fail="can be installed with `eval` extra")

        dubstub(*diff_, expect_fail="The `eval` extra seems to not be installed")

    with cli_venv(["def_fmt"], ["pyright", "stubgen"]) as dubstub:
        dubstub(*gen_, "--format=True")
        dubstub(*eval_, "--format=True", expect_fail="can be installed with `eval` extra")

    with cli_venv(["eval"], ["black", "isort"]) as dubstub:
        dubstub(*eval_)
        dubstub(*eval_, "--format=True", expect_fail="can be installed with `def_fmt` extra")
        dubstub(*diff_)

    with cli_venv(["eval", "def_fmt"], []) as dubstub:
        dubstub(*eval_, "--format=True")
        dubstub(*diff_)


def check_test(py_version: str | None, test_args: str | None):
    versions = [
        "3.10",
        "3.11",
        "3.12",
        "3.13",
    ]

    hidden = True
    if py_version:
        hidden = False
        versions = [py_version]

    if test_args:
        args = shlex.split(test_args)
    else:
        args = []

    for version in versions:
        print(f"[Test with python {version}]")
        venv_bin = dubstub_venv(version, ["dev"])
        cmd(
            venv_bin / "pytest",
            "--color=yes" if sys.stdout.isatty() else "--color=auto",
            "-vv",
            "tests",
            *args,
            hidden=hidden,
        )
        print()


def main():
    parser = ArgumentParser()
    parser.add_argument("--no-test", action="store_true")
    parser.add_argument("--no-style", action="store_true")
    parser.add_argument("--no-doc", action="store_true")
    parser.add_argument("--no-cli", action="store_true")
    parser.add_argument("--py-version")
    parser.add_argument("--test-args")
    parser.add_argument("--tool-verbose", action="store_true")
    args = parser.parse_args()

    os.chdir(ROOT)
    DEV_CACHE.mkdir(exist_ok=True, parents=True)

    if not args.no_style:
        check_style(args.tool_verbose)

    if not args.no_doc:
        check_doc()

    if not args.no_cli:
        check_cli()

    if not args.no_test:
        check_test(args.py_version, args.test_args)


def dubstub_venv(version: str, extras: list[str]) -> Path:
    if not extras:
        venv_suffix = "none"
        extra_suffix = ""
    else:
        venv_suffix = "-".join(sorted(extras))
        extra_suffix = f"[{','.join(extras)}]"

    venv_path = DEV_CACHE / f"venv-{version}-{venv_suffix}"
    venv_bin = venv_path / "bin"
    # rmtree(venv_path, ignore_errors=True)

    cmd("uv", "venv", "--python", version, venv_path)
    cmd("uv", "pip", "install", f".{extra_suffix}", "--refresh-package", "dubstub", "--python", venv_bin / "python")
    return venv_bin


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)

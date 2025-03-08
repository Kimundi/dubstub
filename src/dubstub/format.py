import shlex
import subprocess
import sys
from pathlib import Path

from .config import FormatterCmd, ValidatedConfig
from .config.match_ctx import MatchContext, Tag
from .fs import Walker


def _generate_jobs(command: FormatterCmd, py_major: int, py_minor: int, paths: set[Path]) -> list[FormatterCmd]:
    jobs: list[FormatterCmd] = []

    has_dubstub_file_arg = any("${dubstub_file_arg}" in arg for arg in command.cmdline)
    has_dubstub_file_args = any("${dubstub_file_args}" in arg for arg in command.cmdline)
    assert (
        has_dubstub_file_arg != has_dubstub_file_args
    ), "exactly one of `${dubstub_file_arg}` or `${dubstub_file_args}` needs to be used in the cmdline"

    def common_replace(arg: str) -> str:
        arg = arg.replace("${dubstub_py_major}", str(py_major))
        arg = arg.replace("${dubstub_py_minor}", str(py_minor))
        arg = arg.replace("${dubstub_py_exe}", sys.executable)
        return arg

    if has_dubstub_file_arg:
        for path in sorted(paths):
            cmd: list[str] = []
            for arg in command.cmdline:
                arg = common_replace(arg)
                arg = arg.replace("${dubstub_file_arg}", str(path))
                cmd.append(arg)
            jobs.append(FormatterCmd(name=command.name, cmdline=cmd))
    else:
        cmd: list[str] = []
        for arg in command.cmdline:
            arg = common_replace(arg)
            if "${dubstub_file_args}" in arg:
                for path in sorted(paths):
                    arg_instance = arg.replace("${dubstub_file_args}", str(path))
                    cmd.append(arg_instance)
            else:
                cmd.append(arg)
        jobs.append(FormatterCmd(name=command.name, cmdline=cmd))

    return jobs


def format_pyi_tree(walker: Walker, config: ValidatedConfig):
    format_, formatter_cmds = config.get_formatting()
    py_major, py_minor = config.get_python_version()

    # discover the paths of all pyi files we need to process
    paths: set[Path] = set()

    for event in walker.walk():
        path = event.out_path

        if path in paths:
            continue

        if path.suffix != ".pyi":
            continue

        if not path.is_file():
            continue

        ctx = MatchContext(
            set(),
            {Tag.MODULE},
            event.out_rel_pattern,
        )

        if not format_.is_match(ctx):
            continue

        paths.add(path)

    if not paths:
        return

    print(f"Run formatter commands on {len(paths)} files")
    failed = False

    jobs: list[FormatterCmd] = []
    for command in formatter_cmds:
        jobs.extend(_generate_jobs(command, py_major, py_minor, paths))

    for command in jobs:
        result = subprocess.run(
            command.cmdline,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            check=False,
        )

        if result.returncode != 0:
            print(f"{command.name} command failed:")
            print(shlex.join(command.cmdline))
            print("- output ---")
            print(result.stdout)
            print("------------")
            failed = True
            break

    assert not failed, "formatter failed"

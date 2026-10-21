"""Load a selected dotenv file for one CLI invocation, never during import."""

import argparse
import os
from contextlib import contextmanager
from pathlib import Path


def add_environment_options(parser):
    group = parser.add_argument_group("Environment")
    selection = group.add_mutually_exclusive_group()
    selection.add_argument(
        "--env-file",
        type=Path,
        metavar="PATH",
        help="Read this env file instead of .env in the current directory",
    )
    selection.add_argument(
        "--no-env",
        action="store_true",
        help="Use shell variables without an env file",
    )


@contextmanager
def cli_environment(argv: list[str], *, prog: str):
    # Parse these before constructing model defaults; flags work on either side
    # of a command. parse_known_args preserves command-specific arguments and --.
    parser = argparse.ArgumentParser(prog=prog, add_help=False, allow_abbrev=False)
    add_environment_options(parser)
    settings, remaining = parser.parse_known_args(argv)
    option_tokens = (
        remaining[: remaining.index("--")] if "--" in remaining else remaining
    )
    if (
        settings.no_env
        or not remaining
        or any(flag in option_tokens for flag in ("-h", "--help", "-V", "--version"))
    ):
        yield remaining
        return
    path = settings.env_file if settings.env_file is not None else Path(".env")
    if settings.env_file is None and not path.exists():
        yield remaining
        return

    from dotenv import load_dotenv

    original_keys = set(os.environ)
    added_keys: set[str] = set()
    try:
        try:
            with path.open(encoding="utf-8") as stream:
                try:
                    load_dotenv(stream=stream, override=False)
                finally:
                    added_keys = set(os.environ) - original_keys
        except (OSError, UnicodeError, ValueError):
            parser.error(
                f"Cannot read env file {path}; use valid UTF-8 dotenv assignments"
            )
        yield remaining
    finally:
        for key in added_keys:
            os.environ.pop(key, None)

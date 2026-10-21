"""Consistent help and environment controls for every command."""

import argparse

from pragyantra.cli.environment import add_environment_options


class CLIParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("formatter_class", argparse.RawDescriptionHelpFormatter)
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)
        self._optionals.title = "Options"
        add_environment_options(self)

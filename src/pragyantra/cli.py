"""CLI and composition root for the application.

Wire concrete inputs, outputs, and providers here as behaviors are implemented.
"""

import argparse
from importlib.metadata import version


def main() -> None:
    """Describe the scaffold without initializing devices or model providers."""
    parser = argparse.ArgumentParser(
        prog="pragyantra",
        description="PragYantra: a modular foundation for an embodied assistant.",
        epilog=(
            "This is the modernization scaffold. "
            "Device integrations and assistant behavior are not implemented yet. "
            "The original prototype is archived in legacy/."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {version('pragyantra')}"
    )
    parser.parse_args()
    parser.print_help()

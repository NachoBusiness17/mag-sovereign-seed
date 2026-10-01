"""Mag CLI command groups.

Each group module exposes:
    add_parser(sub) -> None      # register sub-parsers on the argparse subparsers object
    dispatch(args) -> int        # handle its commands, return process exit code

main.py is a thin registry that iterates GROUPS to build the parser and route
dispatch. This keeps the 48-command surface discoverable and each domain
self-contained.
"""
from __future__ import annotations

from . import companion, core, improve, lab, ops, records, state

# Order matters: it defines the order commands appear in --help.
GROUPS = [
    core,
    companion,
    records,
    state,
    ops,
    improve,
    lab,
]

__all__ = ["GROUPS"]

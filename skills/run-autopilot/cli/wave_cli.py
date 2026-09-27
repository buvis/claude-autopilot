"""cli/wave_cli.py - the `autopilot wave` verbs: parser shape and dispatch
(PRD 00214).

`run` takes the already-resolved repo and wave.json paths; resolving them from
`--state` stays in `cli/__main__.py`, like every other subcommand.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from cli import wave, wave_assemble, wave_launch


def add(subparsers) -> None:
    p = subparsers.add_parser("wave")
    verbs = p.add_subparsers(dest="verb", required=True)
    plan = verbs.add_parser("plan")
    plan.add_argument("--state")
    plan.add_argument("--max-lanes", type=int, default=3)
    for verb in ("launch", "status", "abort"):
        verbs.add_parser(verb).add_argument("--state")
    verbs.add_parser("assemble").add_argument("--state")


def run(args: argparse.Namespace, repo: Path, wave_path: Path) -> int:
    if args.verb == "plan":
        return wave.plan(repo, wave_path, args.max_lanes)
    if args.verb == "assemble":
        try:
            return wave_assemble.assemble(repo, wave_path)
        except subprocess.CalledProcessError as err:
            print(f"autopilot: {err}", file=sys.stderr)
            return 1
        except wave.WaveCorruptError as err:
            print(f"autopilot: {wave.corrupt_message(err)}", file=sys.stderr)
            return 1
    # Read once for the two friendly early messages only: `launch` reloads
    # wave.json under its own lock and never sees this copy.
    try:
        loaded = wave.load(wave_path)
    except wave.WaveCorruptError as err:
        print(f"autopilot: {wave.corrupt_message(err)}", file=sys.stderr)
        return 1
    if loaded is None:
        print(f"autopilot: {wave.missing_message(wave_path)}", file=sys.stderr)
        return 1
    if args.verb == "launch":
        try:
            return wave_launch.launch(repo, wave_path)
        except subprocess.CalledProcessError as err:
            print(f"autopilot: {err}", file=sys.stderr)
            return 1
    if args.verb == "status":
        print(wave_launch.status(repo, loaded))
        return 0
    # `abort` is the last verb the parser accepts, and it reloads wave.json under
    # its own lock too.
    try:
        return wave_launch.abort(repo, wave_path)
    except subprocess.CalledProcessError as err:
        print(f"autopilot: {err}", file=sys.stderr)
        return 1

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

from cli import wave, wave_assemble, wave_launch, wave_review, wave_run


def add(subparsers) -> None:
    p = subparsers.add_parser("wave")
    verbs = p.add_subparsers(dest="verb", required=True)
    plan = verbs.add_parser("plan")
    plan.add_argument("--state")
    plan.add_argument("--max-lanes", type=int, default=3)
    for verb in ("launch", "status", "abort"):
        verbs.add_parser(verb).add_argument("--state")
    verbs.add_parser("assemble").add_argument("--state")
    verbs.add_parser("review").add_argument("--state")
    verbs.add_parser("land").add_argument("--state")
    run_p = verbs.add_parser("run")
    run_p.add_argument("--state")
    run_p.add_argument("--max-lanes", type=int, default=3)
    run_p.add_argument("--review-slots", type=int, default=3)
    run_p.add_argument("--yes", action="store_true")


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
    if args.verb == "run":
        return wave_run.run(
            repo,
            max_lanes=args.max_lanes,
            review_slots=args.review_slots,
            yes=args.yes,
        )
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
    if args.verb == "review":
        outcome = wave_review.review(repo, loaded)
        print(outcome)
        return 4 if outcome == "review_failed" else 0
    if args.verb == "land":
        return wave_review.land(repo, loaded)
    # `abort` is the last verb the parser accepts, and it reloads wave.json under
    # its own lock too.
    try:
        return wave_launch.abort(repo, wave_path)
    except subprocess.CalledProcessError as err:
        print(f"autopilot: {err}", file=sys.stderr)
        return 1

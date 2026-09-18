"""Command-line helpers that can run before a training GPU is available."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from .validation import load_json, make_train_list, validate_results


def _validate_results_command(args: argparse.Namespace) -> int:
    errors = validate_results(load_json(args.path), template=args.template)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.template:
        print(
            "Template structure is valid: 50 tasks, two settings, zero attempts. "
            "This is not submission-ready."
        )
    else:
        print(
            "Result structure/counts are valid: 50 tasks, two settings, 100 attempts per task. "
            "Reported outcomes are not independently verified."
        )
    return 0


def _make_train_list_command(args: argparse.Namespace) -> int:
    lines, unverified = make_train_list(
        args.data_root, args.output, allow_missing=args.allow_missing
    )
    print(f"Wrote {len(lines)} Aloha-AgileX clean-only entries to {args.output}")
    if unverified:
        print(
            f"WARNING: {len(unverified)} datasets are unverified (未校验); "
            "this list is for planning only.",
            file=sys.stderr,
        )
        for dataset in unverified:
            print(f"UNVERIFIED: {dataset}", file=sys.stderr)
    else:
        print(
            "All meta/info.json files report exactly 50 episodes; "
            "episode contents were not inspected."
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="banana-peels", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser(
        "validate-results", help="check official results JSON structure and counts"
    )
    validate.add_argument("path", help="path to results.json")
    validate.add_argument(
        "--template",
        action="store_true",
        help="check an unfilled zero-attempt template, allowing the team placeholder",
    )
    validate.set_defaults(handler=_validate_results_command)
    training = subparsers.add_parser(
        "make-train-list", help="write a verified 50-task clean-only training list"
    )
    training.add_argument(
        "--data-root", required=True, help="parent directory of the converted LeRobot task datasets"
    )
    training.add_argument("--output", required=True, help="output training list path")
    training.add_argument(
        "--allow-missing",
        action="store_true",
        help="write a planning list even when datasets/metadata are absent",
    )
    training.set_defaults(handler=_make_train_list_command)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Standalone CLI for the VTS Meeting Analytics Engine."""

from __future__ import annotations

import argparse
import os
from typing import Optional

from vts_analytics_engine import VTSAnalyticsEngine, create_sample_meeting


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run VTS meeting transcript analytics.")
    parser.add_argument("csv_path", nargs="?", help="Path to transcript CSV.")
    parser.add_argument(
        "--output",
        "-o",
        help="Path to save JSON results. Defaults to <csv_name>_analytics.json.",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Run the bundled multilingual sample instead of loading a CSV.",
    )
    parser.add_argument(
        "--write-sample",
        metavar="PATH",
        help="Write the bundled multilingual sample transcript to PATH and exit.",
    )
    return parser.parse_args()


def default_output_path(csv_path: Optional[str]) -> str:
    if not csv_path:
        return "sample_meeting_analytics.json"
    base, _ = os.path.splitext(csv_path)
    return f"{base}_analytics.json"


def main() -> None:
    args = parse_args()

    if args.write_sample:
        create_sample_meeting().to_csv(args.write_sample, index=False)
        print(f"Sample transcript saved to: {args.write_sample}")
        return

    if args.sample:
        df = create_sample_meeting()
        engine = VTSAnalyticsEngine(df)
        csv_path = None
    else:
        if not args.csv_path:
            raise SystemExit("Provide a CSV path or use --sample.")
        engine = VTSAnalyticsEngine.from_csv(args.csv_path)
        csv_path = args.csv_path

    results = engine.full_analysis()
    engine.print_report(results)

    output_path = args.output or default_output_path(csv_path)
    engine.save_json(output_path, results)
    print(f"Saved JSON results to: {output_path}")


if __name__ == "__main__":
    main()

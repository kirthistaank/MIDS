"""
main.py
-------
Command-line entry point for the Berkeley Bike Safety Route Planner.

Usage
-----
    # Find the safest route between two addresses
    python main.py --from "2521 Channing Way" --to "Downtown Berkeley BART"

    # Force re-download of the OSM graph
    python main.py --from "..." --to "..." --rebuild-graph

    # Skip the AI explanation (useful if ANTHROPIC_API_KEY is not set)
    python main.py --from "..." --to "..." --no-ai

    # Build the crash heatmap only (no route)
    python main.py --heatmap-only

    # Interactive chat mode after computing the route
    python main.py --from "..." --to "..." --chat

Pipeline
--------
    1. Load (or rebuild) the Berkeley OSM bike graph          [graph_builder]
    2. Load SWITRS crash data and score graph edges           [crash_scorer]
    3. Find the safest route via Dijkstra                     [router]
    4. Print route summary and export GeoJSON                 [router]
    5. Generate interactive HTML maps                         [visualiser]
    6. Request AI explanation from Claude                     [ai_explainer]
    7. (Optional) Enter interactive follow-up chat loop       [ai_explainer]

Crash data (CSV)
----------------
SWITRS bicycle crashes are read from (in order of default resolution):

    1. ``data/switrs_query_results.csv`` — if this file exists (typical query export name)
    2. ``data/switrs_berkeley_bike.csv`` — canonical name from the project README

Override with ``--crash-csv /path/to/file.csv``. Column expectations: ``config.py``.
"""

import argparse
import sys
from pathlib import Path

from config import SWITRS_CSV, SWITRS_QUERY_RESULTS_CSV
from logger import get_logger

log = get_logger(__name__)


def _default_crash_csv() -> Path:
    """Use query export CSV when present, otherwise the packaged default path."""
    if SWITRS_QUERY_RESULTS_CSV.exists():
        return SWITRS_QUERY_RESULTS_CSV
    return SWITRS_CSV


def parse_args() -> argparse.Namespace:
    """Define and parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="bike_safety",
        description="Berkeley Bike Safety Route Planner — powered by SWITRS + OSM + Claude AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--from", dest="origin",
        help="Origin address in Berkeley (e.g. '2521 Channing Way')",
    )
    parser.add_argument(
        "--to", dest="destination",
        help="Destination address in Berkeley (e.g. 'Downtown Berkeley BART')",
    )
    parser.add_argument(
        "--rebuild-graph", action="store_true",
        help="Force re-download of the OSM street network (ignores cache)",
    )
    parser.add_argument(
        "--no-ai", action="store_true",
        help="Skip the Claude AI route explanation",
    )
    parser.add_argument(
        "--heatmap-only", action="store_true",
        help="Only generate the crash heatmap; do not compute a route",
    )
    parser.add_argument(
        "--chat", action="store_true",
        help="After the initial explanation, enter an interactive Q&A loop",
    )
    parser.add_argument(
        "--export-scores", action="store_true",
        help="Export per-edge safety scores to output/edge_safety_scores.csv",
    )
    parser.add_argument(
        "--crash-csv",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "SWITRS crash CSV (default: data/switrs_query_results.csv if it exists, "
            "else data/switrs_berkeley_bike.csv)"
        ),
    )

    return parser.parse_args()


def main() -> int:
    """
    Orchestrate the full pipeline.

    Returns
    -------
    int
        Exit code: 0 = success, 1 = error.
    """
    args = parse_args()

    log.info("╔══════════════════════════════════════════╗")
    log.info("║  Berkeley Bike Safety Route Planner      ║")
    log.info("╚══════════════════════════════════════════╝")

    # ── Step 1: Load the bike graph ───────────────────────────────────────────
    log.info("Step 1/6 — Loading OSM bike graph")
    try:
        from graph_builder import load_graph
        G = load_graph(force_rebuild=args.rebuild_graph)
    except Exception as err:
        log.error("Failed to load graph: %s", err)
        return 1

    # ── Step 2: Load and score crash data ─────────────────────────────────────
    log.info("Step 2/6 — Loading SWITRS crash data and scoring edges")
    try:
        from crash_scorer import load_crashes, score_edges
        crash_csv = args.crash_csv if args.crash_csv is not None else _default_crash_csv()
        log.info("Crash CSV: %s", crash_csv)
        crashes = load_crashes(crash_csv)
        G = score_edges(G, crashes)
    except Exception as err:
        log.error("Crash scoring failed: %s", err)
        return 1

    # ── Optional: export edge scores CSV ──────────────────────────────────────
    if args.export_scores:
        from visualiser import export_safety_scores
        export_safety_scores(G)

    # ── Optional: heatmap only mode ───────────────────────────────────────────
    if args.heatmap_only:
        log.info("Heatmap-only mode: building crash heatmap")
        from visualiser import build_crash_heatmap
        build_crash_heatmap(crashes)
        log.info("Done. Open output/crash_heatmap.html in your browser.")
        return 0

    # ── Validate required arguments ───────────────────────────────────────────
    if not args.origin or not args.destination:
        log.error("Please provide --from and --to addresses (or use --heatmap-only)")
        return 1

    # ── Step 3: Find safest route ─────────────────────────────────────────────
    log.info("Step 3/6 — Finding safest route")
    try:
        from router import find_safest_route, print_route_summary
        route = find_safest_route(G, args.origin, args.destination)
    except ValueError as err:
        log.error("Routing failed: %s", err)
        return 1
    except Exception as err:
        log.error("Unexpected routing error: %s", err)
        return 1

    # ── Step 4: Print route summary ───────────────────────────────────────────
    log.info("Step 4/6 — Route summary")
    print_route_summary(route)

    # ── Step 5: Generate maps ─────────────────────────────────────────────────
    log.info("Step 5/6 — Generating interactive maps")
    try:
        from visualiser import build_crash_heatmap, build_route_map
        build_crash_heatmap(crashes)
        map_path = build_route_map(G, route)
        if map_path:
            log.info("Open the route map: %s", map_path)
    except Exception as err:
        log.warning("Visualisation failed (non-fatal): %s", err)

    # ── Step 6: AI explanation ────────────────────────────────────────────────
    if not args.no_ai:
        log.info("Step 6/6 — Requesting AI route explanation from Claude")
        try:
            from ai_explainer import RouteExplainer

            GREEN = "\033[32m"
            BOLD  = "\033[1m"
            RESET = "\033[0m"

            explainer = RouteExplainer(route)
            explanation = explainer.explain()

            print(f"\n{GREEN}{'─'*52}{RESET}")
            print(f"{BOLD}  BikeSafe AI — Route Analysis{RESET}")
            print(f"{GREEN}{'─'*52}{RESET}")
            print(explanation)
            print(f"{GREEN}{'─'*52}{RESET}\n")

            # ── Optional interactive chat loop ────────────────────────────────
            if args.chat:
                print("Ask follow-up questions (type 'quit' to exit):\n")
                while True:
                    try:
                        question = input(f"{GREEN}You >{RESET} ").strip()
                    except (EOFError, KeyboardInterrupt):
                        print("\nGoodbye! Ride safe.")
                        break

                    if question.lower() in ("quit", "exit", "q"):
                        print("Goodbye! Ride safe.")
                        break

                    if not question:
                        continue

                    answer = explainer.ask(question)
                    print(f"\n{GREEN}BikeSafe AI >{RESET}\n{answer}\n")

        except Exception as err:
            log.warning("AI explanation failed (non-fatal): %s", err)
    else:
        log.info("Step 6/6 — AI explanation skipped (--no-ai flag)")

    log.info("Pipeline complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
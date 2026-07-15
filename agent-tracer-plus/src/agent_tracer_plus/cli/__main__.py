"""Main CLI entrypoint for Agent Tracer Plus."""

import argparse
import sys

from agent_tracer_plus.utils.logger import get_logger

logger = get_logger("cli")


def main():
    parser = argparse.ArgumentParser(
        prog="agent-tracer-plus",
        description="Agent Tracer Plus — auto-capture tracing for AI agents",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. run — wrap any command with auto-tracing
    run_parser = subparsers.add_parser("run", help="Run an arbitrary command with auto-tracing enabled")
    run_parser.add_argument("--service-name", type=str, default="auto", help="Service name for traces")
    run_parser.add_argument("--storage", type=str, default=None, help="Storage backend URI")
    run_parser.add_argument("target_command", nargs=argparse.REMAINDER, help="Command to run (e.g. 'python script.py' or 'celery worker')")

    # 2. tail — live stream traces to terminal
    tail_parser = subparsers.add_parser("tail", help="Live stream traces to the terminal")
    tail_parser.add_argument("--service", type=str, help="Service name filter")
    tail_parser.add_argument("--filter", type=str, dest="filter_str", help="Basic filter (e.g., status=ERROR)")
    tail_parser.add_argument("--storage", type=str, default=None, help="Storage backend URI (default: sqlite)")

    # 3. export — export traces to file
    export_parser = subparsers.add_parser("export", help="Export traces to a file")
    export_parser.add_argument("--backend", type=str, default="sqlite://./agent_traces.db", help="Storage backend URI")
    export_parser.add_argument("--format", type=str, choices=["jsonl", "csv", "parquet"], default="jsonl", help="Export format")
    export_parser.add_argument("--output", type=str, required=True, help="Output file path")
    export_parser.add_argument("--limit", type=int, default=1000, help="Max traces to export")

    # 4. regression — run trace regression tests
    reg_parser = subparsers.add_parser("regression", help="Run trace regression tests")
    reg_parser.add_argument("path", nargs="?", default="tests", help="Path to tests (default: 'tests')")
    reg_parser.add_argument("--update-baselines", action="store_true", help="Update existing golden baselines")

    # 5. eval — run dataset evaluation
    eval_parser = subparsers.add_parser("eval", help="Run a batch dataset evaluation against a prompt")
    eval_parser.add_argument("--name", type=str, required=True, help="Name of the evaluation run")
    eval_parser.add_argument("--dataset", type=str, required=True, help="Dataset ID")
    eval_parser.add_argument("--prompt", type=str, required=True, help="Prompt ID or Name")
    eval_parser.add_argument("--host", type=str, default="http://localhost:3000", help="Platform API Host")

    # 6. ui — launch local dashboard
    ui_parser = subparsers.add_parser("ui", help="Launch the local trace dashboard")
    ui_parser.add_argument("--port", type=int, default=8000, help="Port to run the UI server on")
    ui_parser.add_argument("--storage", type=str, default="sqlite://./agent_traces.db", help="Storage backend URI")

    # 'diff' command
    parser_diff = subparsers.add_parser("diff", help="Deep diff two traces")
    parser_diff.add_argument("trace_a", type=str, help="Base trace ID")
    parser_diff.add_argument("trace_b", type=str, help="Comparison trace ID")
    parser_diff.add_argument("--storage", type=str, default="sqlite://agent_traces.db", help="Storage backend URI")

    # 'anomalies' command
    parser_anomalies = subparsers.add_parser("anomalies", help="Detect anomalies in a trace")
    parser_anomalies.add_argument("trace_id", type=str, help="Trace ID to analyze")
    parser_anomalies.add_argument("--storage", type=str, default="sqlite://agent_traces.db", help="Storage backend URI")
    parser_anomalies.add_argument("--window", type=int, default=100, help="Sliding window size")

    # 'hallucination' command
    parser_hallu = subparsers.add_parser("hallucination", help="Detect hallucinations in a trace")
    parser_hallu.add_argument("trace_id", type=str, help="Trace ID to analyze")
    parser_hallu.add_argument("--storage", type=str, default="sqlite://agent_traces.db", help="Storage backend URI")
    parser_hallu.add_argument("--engine", type=str, choices=["llm", "cross-encoder"], default="llm", help="Scoring engine to use")

    # 'generate-tests' command
    parser_gentest = subparsers.add_parser("generate-tests", help="Generate pytest files from a trace")
    parser_gentest.add_argument("trace_id", type=str, help="Trace ID to generate test for")
    parser_gentest.add_argument("--storage", type=str, default="sqlite://agent_traces.db", help="Storage backend URI")
    parser_gentest.add_argument("--output", type=str, default="tests/generated", help="Output directory")

    args = parser.parse_args()

    if args.command == "run":
        from agent_tracer_plus.cli.run import run_command
        run_command(
            target_command=args.target_command,
            service_name=args.service_name,
            storage=args.storage,
        )

    elif args.command == "tail":
        from agent_tracer_plus.cli.tail import run_tail
        run_tail(args.service, args.filter_str)

    elif args.command == "export":
        from agent_tracer_plus.cli.export import export_traces
        export_traces(args.backend, args.format, args.output, args.limit)

    elif args.command == "diff":
        from agent_tracer_plus.cli.diff import run_diff
        run_diff(args)

    elif args.command == "anomalies":
        from agent_tracer_plus.cli.anomalies import run_anomalies
        run_anomalies(args)

    elif args.command == "hallucination":
        from agent_tracer_plus.cli.hallucination import run_hallucination
        run_hallucination(args)
        
    elif args.command == "generate-tests":
        from agent_tracer_plus.cli.generate_tests import run_generate_tests
        run_generate_tests(args)

    elif args.command == "regression":
        from agent_tracer_plus.testing.pytest_plugin import run_pytest_regression
        pytest_args = [args.path, "--atp-regression", args.path]
        if args.update_baselines:
            pytest_args.append("--update-baselines")
        sys.exit(run_pytest_regression(pytest_args))

    elif args.command == "eval":
        from agent_tracer_plus.cli.eval import run_eval
        run_eval(args.dataset, args.prompt, args.name, args.host)

    elif args.command == "ui":
        from agent_tracer_plus.cli.ui import run_ui
        run_ui(port=args.port, storage_uri=args.storage)

if __name__ == "__main__":
    main()

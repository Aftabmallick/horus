"""CLI commands for docs generation."""

import argparse
import logging

logger = logging.getLogger(__name__)


def generate_docs(agent_name: str, format: str, output: str):
    """Generate documentation from traces."""
    print(f"Generating {format} documentation for agent '{agent_name}'...")
    # This is a stub that would integrate with the docs_gen module

    with open(output, "w") as f:
        if format == "markdown":
            f.write(f"# Agent Documentation: {agent_name}\n\nGenerated automatically from production traces.")
        elif format == "mermaid":
            f.write("graph TD;\n  Agent-->Tool;")
        else:
            f.write(f"Docs for {agent_name}")

    print(f"Documentation saved to {output}.")


def register_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register the docs CLI command."""
    parser = subparsers.add_parser("docs", help="Generate agent documentation from traces")
    parser.add_argument("--agent", type=str, required=True, help="Agent name to generate docs for")
    parser.add_argument("--format", type=str, choices=["markdown", "mermaid", "openapi"], default="markdown", help="Output format")
    parser.add_argument("--output", type=str, default="agent_docs.md", help="Output file path")
    parser.set_defaults(func=lambda args: generate_docs(args.agent, args.format, args.output))

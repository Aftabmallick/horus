"""CLI 'run' command — wraps any command with auto-tracing.

Uses POSIX process replacement (os.execvpe) to securely wrap the target
process without interfering with signal handling, exit codes, or standard streams.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def run_command(
    target_command: list[str],
    service_name: str = "auto",
    storage: str | None = None,
) -> None:
    """Run an arbitrary command with Agent Tracer Plus auto-instrumentation.

    This resolves the internal `bootstrap` directory and injects it into
    the `PYTHONPATH` before executing the target command via process replacement.

    Args:
        target_command: The command and its arguments (e.g. ['celery', 'worker'])
        service_name: Service name for traces.
        storage: Optional storage backend URI.
    """
    if not target_command:
        print("Usage: agent-tracer-plus run [options] <command> [args...]")
        print("Example: agent-tracer-plus run python script.py")
        print("Example: agent-tracer-plus run gunicorn app:app")
        sys.exit(1)

    # Some argument parsers (like `--` separation) might leave a `--` in the command
    if target_command[0] == "--":
        target_command.pop(0)
        if not target_command:
            print("Error: No command specified after '--'")
            sys.exit(1)

    executable = target_command[0]
    
    # Resolve the absolute path of the executable
    executable_path = shutil.which(executable)
    if not executable_path:
        print(f"Error: Command not found: {executable}")
        sys.exit(1)

    # Resolve our internal bootstrap directory
    # It is located at agent_tracer_plus/bootstrap
    current_dir = Path(__file__).parent
    bootstrap_dir = (current_dir.parent / "bootstrap").resolve()

    if not (bootstrap_dir / "sitecustomize.py").exists():
        print(f"Error: Bootstrap directory not found or corrupt: {bootstrap_dir}")
        sys.exit(1)

    # Set up environment variables for the tracer
    env = os.environ.copy()
    env["AGENT_TRACER_PLUS_ENABLED"] = "1"
    env["AGENT_TRACER_PLUS_AUTO_INIT"] = "1"
    
    svc = service_name if service_name != "auto" else Path(executable_path).stem
    env["AGENT_TRACER_PLUS_SERVICE_NAME"] = svc
    
    if storage:
        env["AGENT_TRACER_PLUS_STORAGE_URI"] = storage

    # Prepend our bootstrap directory to PYTHONPATH
    existing_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{bootstrap_dir}{os.pathsep}{existing_path}" if existing_path else str(bootstrap_dir)

    # Process replacement
    try:
        if hasattr(os, "execvpe"):
            # POSIX systems (Linux, macOS)
            os.execvpe(executable_path, target_command, env)
        else:
            # Windows fallback
            import subprocess
            result = subprocess.run(target_command, env=env)
            sys.exit(result.returncode)
    except OSError as e:
        print(f"Error executing {executable}: {e}")
        sys.exit(1)

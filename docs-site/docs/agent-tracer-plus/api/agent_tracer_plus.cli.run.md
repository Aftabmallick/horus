# Module: `agent_tracer_plus.cli.run`

CLI 'run' command — wraps any command with auto-tracing.

Uses POSIX process replacement (os.execvpe) to securely wrap the target
process without interfering with signal handling, exit codes, or standard streams.

## Function `run_command(target_command, service_name, storage)`
Run an arbitrary command with Agent Tracer Plus auto-instrumentation.

This resolves the internal `bootstrap` directory and injects it into
the `PYTHONPATH` before executing the target command via process replacement.

Args:
    target_command: The command and its arguments (e.g. ['celery', 'worker'])
    service_name: Service name for traces.
    storage: Optional storage backend URI.


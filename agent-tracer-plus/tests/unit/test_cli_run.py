import os
import sys
from unittest import mock
import pytest
from agent_tracer_plus.cli.run import run_command

@mock.patch("agent_tracer_plus.cli.run.shutil.which")
@mock.patch("agent_tracer_plus.cli.run.os.execvpe", create=True)
def test_cli_run_happy_path(mock_execvpe, mock_which):
    mock_which.return_value = "/usr/bin/celery"
    
    with mock.patch("agent_tracer_plus.cli.run.Path.exists", return_value=True):
        run_command(["celery", "worker"], service_name="background-jobs")
        
        mock_which.assert_called_once_with("celery")
        
        if hasattr(os, "execvpe"):
            mock_execvpe.assert_called_once()
            args, kwargs = mock_execvpe.call_args
            assert args[0] == "/usr/bin/celery"
            assert args[1] == ["celery", "worker"]
            assert args[2]["AGENT_TRACER_PLUS_AUTO_INIT"] == "1"
            assert args[2]["AGENT_TRACER_PLUS_SERVICE_NAME"] == "background-jobs"
            assert "bootstrap" in args[2]["PYTHONPATH"]

@mock.patch("agent_tracer_plus.cli.run.shutil.which")
def test_cli_run_command_not_found(mock_which, capsys):
    mock_which.return_value = None
    
    with pytest.raises(SystemExit) as exc_info:
        run_command(["nonexistent-command"])
        
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Command not found: nonexistent-command" in captured.out

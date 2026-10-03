"""Regression tests for the public CLI and workspace boundary."""

from pathlib import Path

from cli import main as cli_main
from src.core.tool_bridge import ToolBridge
from src.core.tools.apply_patch import apply_patch
from src.core.tools.web_fetch import WebFetchInput, web_fetch


def test_cli_help_is_a_stable_entrypoint(capsys):
    try:
        cli_main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0
    assert "NEMESIS" in capsys.readouterr().out


def test_cli_sets_workspace_before_agent_bootstrap(monkeypatch, tmp_path):
    received = []
    monkeypatch.setattr("cli.run_agent", lambda argv: received.append(argv) or 0)
    assert cli_main(["--workspace", str(tmp_path), "--debug"]) == 0
    assert received == [["--debug"]]


def test_read_file_paths_cannot_escape_workspace(tmp_path):
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    bridge = ToolBridge(workspace=str(tmp_path))
    result = list(bridge.execute_tool("read_file", {"paths": [str(outside)]}))[-1]
    assert result["success"] is False
    assert "outside workspace" in result["stdout"]


def test_edit_alias_uses_path_and_requires_prior_read(tmp_path):
    target = tmp_path / "sample.txt"
    target.write_text("before", encoding="utf-8")
    bridge = ToolBridge(workspace=str(tmp_path))
    denied = list(bridge.execute_tool("edit", {
        "path": "sample.txt", "old_string": "before", "new_string": "after"
    }))[-1]
    assert denied["success"] is False

    assert list(bridge.execute_tool("read_file", {"path": "sample.txt"}))[-1]["success"]
    changed = list(bridge.execute_tool("edit", {
        "path": "sample.txt", "old_string": "before", "new_string": "after"
    }))[-1]
    assert changed["success"] is True
    assert target.read_text(encoding="utf-8") == "after"


def test_patch_cannot_reference_a_file_outside_workspace(tmp_path):
    result = apply_patch(
        "--- a/../../outside.txt\n+++ b/../../outside.txt\n@@ -0,0 +1 @@\n+nope\n",
        str(tmp_path),
    )
    assert result.success is False
    assert "escapes the workspace" in result.message


def test_web_fetch_rejects_loopback_before_network_access():
    result = web_fetch(WebFetchInput("https://127.0.0.1/private"))
    assert result.success is False
    assert "not allowed" in result.error

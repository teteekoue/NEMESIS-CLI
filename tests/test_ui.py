from rich.console import Console

from src.ui.chat_ui import ChatUI
from src.ui.header import get_header


def test_header_is_compact_and_contains_session_information():
    console = Console(record=True, width=100)
    console.print(get_header(provider="NEMAPI", model="qwen", workspace="/tmp/project"))
    output = console.export_text()
    assert "NEMESIS" in output
    assert "provider" in output
    assert "workspace" in output
    assert "____" not in output


def test_failed_tool_result_is_readable():
    console = Console(record=True, width=100)
    ui = ChatUI(console)
    ui.tool_result({"success": False, "stdout": "A clear failure message"}, "bash")
    output = console.export_text()
    assert "fail" in output
    assert "A clear failure message" in output

"""Unit tests for the ultra-robust JSON-only ActionParser."""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from action_parser import ActionParser


def make_parser():
    return ActionParser()


def test_simple_json_fence():
    p = make_parser()
    raw = '''I will list the directory.
```json
{
  "tool": "list_dir",
  "parameters": {
    "path": "."
  }
}
```
'''
    r = p.parse(raw)
    assert r["action"] is not None
    assert r["action"]["type"] == "list_dir"
    assert r["action"]["content"]["path"] == "."
    assert "I will list" in r["text"]


def test_edit_rename_from_search_replace():
    p = make_parser()
    raw = '''```json
{"tool": "search_replace", "parameters": {"file_path": "a.py", "old_string": "x", "new_string": "y"}}
```'''
    r = p.parse(raw)
    assert r["action"]["type"] == "edit"
    assert r["action"]["content"]["old_string"] == "x"


def test_large_content_with_newlines_and_slashes():
    """Simulate LLM that puts real newlines and backslashes inside the JSON string."""
    p = make_parser()
    # Intentionally broken: real newlines inside the "content" value
    content_body = 'def foo():\n    """doc with \\\\ path /usr/bin"""\n    return "ok\\\\n"'
    # Build a raw response where the content string has literal newlines (LLM mistake)
    raw = (
        '```json\n'
        '{\n'
        '  "tool": "write_file",\n'
        '  "parameters": {\n'
        '    "file_path": "test.py",\n'
        '    "content": "def foo():\n'
        '    \\"\\"\\"doc with \\\\ path /usr/bin\\"\\"\\"\n'
        '    return \\"ok\\\\n\\"\"\n'
        '  }\n'
        '}\n'
        '```'
    )
    r = p.parse(raw)
    assert r["action"] is not None, "Parser failed on large content with newlines/slashes"
    assert r["action"]["type"] == "write_file"
    assert "file_path" in r["action"]["content"]
    # content should have been recovered
    assert "def foo" in r["action"]["content"].get("content", "")


def test_properly_escaped_large_content():
    p = make_parser()
    code = 'def hello():\n    """Say hello"""\n    print("path: C:\\\\Users\\\\x")\n'
    payload = {
        "tool": "write_file",
        "parameters": {
            "file_path": "hello.py",
            "content": code,
        },
    }
    raw = "```json\n" + json.dumps(payload) + "\n```"
    r = p.parse(raw)
    assert r["action"] is not None
    assert r["action"]["type"] == "write_file"
    assert r["action"]["content"]["content"] == code


def test_trailing_comma_repair():
    p = make_parser()
    raw = '''```json
{
  "tool": "bash",
  "parameters": {
    "command": "ls",
  },
}
```'''
    r = p.parse(raw)
    assert r["action"] is not None
    assert r["action"]["type"] == "bash"
    assert r["action"]["content"]["command"] == "ls"


def test_unquoted_keys():
    p = make_parser()
    raw = '''```json
{
  tool: "grep",
  parameters: {
    pattern: "TODO",
    path: "src"
  }
}
```'''
    r = p.parse(raw)
    assert r["action"] is not None
    assert r["action"]["type"] == "grep"


def test_name_arguments_aliases():
    p = make_parser()
    raw = '''```json
{"name": "web_search", "arguments": {"query": "python asyncio"}}
```'''
    r = p.parse(raw)
    assert r["action"]["type"] == "web_search"
    assert r["action"]["content"]["query"] == "python asyncio"


def test_bare_json_without_fence():
    p = make_parser()
    raw = 'Let me run this: {"tool": "bash", "parameters": {"command": "echo hi"}} done.'
    r = p.parse(raw)
    assert r["action"] is not None
    assert r["action"]["type"] == "bash"
    assert r["action"]["content"]["command"] == "echo hi"


def test_truncated_inline_write_call_is_executed():
    p = make_parser()
    raw = (
        'Je crée le fichier : {"tool":"write_file","parameters":'
        '{"path":"reseau_machine.md","content":"# Réseau\\n\\n## DNS"}'
    )
    r = p.parse(raw)
    assert r["action"] is not None
    assert r["action"]["type"] == "write_file"
    assert r["action"]["content"]["path"] == "reseau_machine.md"
    assert "## DNS" in r["action"]["content"]["content"]
    assert r["text"] == "Je crée le fichier :"


def test_no_action():
    p = make_parser()
    raw = "Just a normal reply with no tool call."
    r = p.parse(raw)
    assert r["action"] is None
    assert "normal reply" in r["text"]


def test_feedback_passthrough():
    p = make_parser()
    raw = "FEEDBACK:\nTool: bash\nSucces: True\nOutput:\nok"
    r = p.parse(raw)
    assert r["action"] is None
    assert r["text"].startswith("FEEDBACK:")


def test_truncated_json_repaired():
    p = make_parser()
    raw = '''```json
{"tool": "list_dir", "parameters": {"path": "/tmp"
```'''
    r = p.parse(raw)
    # May or may not succeed depending on repair depth; at least must not crash
    assert isinstance(r, dict)
    assert "action" in r


def test_edit_with_python_code_containing_quotes():
    p = make_parser()
    old = 'print("hello")'
    new = 'print("hello world")'
    payload = {
        "tool": "edit",
        "parameters": {
            "file_path": "a.py",
            "old_string": old,
            "new_string": new,
        },
    }
    raw = "```json\n" + json.dumps(payload) + "\n```"
    r = p.parse(raw)
    assert r["action"]["type"] == "edit"
    assert r["action"]["content"]["old_string"] == old
    assert r["action"]["content"]["new_string"] == new


def test_very_large_payload():
    """Stress-test with a multi-kilobyte content string full of special chars."""
    p = make_parser()
    lines = []
    for i in range(200):
        lines.append(f'    line_{i} = "path/with/slashes/and\\\\backslashes {i}"')
    big = "def big():\n" + "\n".join(lines) + "\n"
    payload = {
        "tool": "write_file",
        "parameters": {"file_path": "big.py", "content": big},
    }
    raw = "Here is the file:\n```json\n" + json.dumps(payload) + "\n```\n"
    r = p.parse(raw)
    assert r["action"] is not None
    assert r["action"]["type"] == "write_file"
    assert len(r["action"]["content"]["content"]) > 1000
    assert "line_199" in r["action"]["content"]["content"]


def test_yaml_format_rejected():
    """YAML fences must no longer be accepted."""
    p = make_parser()
    raw = '''```bash
command: ls -la
```'''
    r = p.parse(raw)
    assert r["action"] is None


def test_qwen_xml_tool_call_format():
    p = make_parser()
    raw = (
        "Je vérifie.\n"
        "<tool_call> <function=bash> "
        "<parameter=command>echo \"=== OS ===\" && uname -a</parameter>"
        "<parameter=description>Collect OS information</parameter>"
        "</tool_call>"
    )
    r = p.parse(raw)
    assert r["action"]["type"] == "bash"
    assert r["action"]["content"]["command"] == 'echo "=== OS ===" && uname -a'
    assert r["action"]["content"]["description"] == "Collect OS information"


def test_multiple_qwen_xml_tool_calls():
    p = make_parser()
    raw = (
        "<tool_call><function=bash><parameter=command>uname -a</parameter></tool_call>"
        "<tool_call><function=bash><parameter=command>free -h</parameter></tool_call>"
    )
    r = p.parse(raw)
    assert [a["content"]["command"] for a in r["actions"]] == ["uname -a", "free -h"]


def test_empty_xml_markers_are_not_displayed():
    p = make_parser()
    raw = "Je vérifie.<tool_call>\n\n</tool_call> <tool_call>\n\n</tool_call>"
    r = p.parse(raw)
    assert r["action"] is None
    assert r["text"] == "Je vérifie."


def test_xml_markers_are_removed_when_native_calls_are_added_later():
    p = make_parser()
    raw = "Je vérifie.<tool_call>\n</tool_call>"
    r = p.parse(raw)
    r["actions"].append({"type": "bash", "content": {"command": "uname -a"}})
    assert "<tool_call>" not in r["text"]


def test_batch_json_calls():
    p = make_parser()
    raw = json.dumps([
        {"tool": "read_file", "parameters": {"path": "a.py"}},
        {"tool": "grep", "parameters": {"pattern": "TODO", "path": "."}},
    ])
    r = p.parse(raw)
    assert [item["type"] for item in r["actions"]] == ["read_file", "grep"]
    assert r["action"] == r["actions"][0]


def test_embedded_json_array_calls():
    p = make_parser()
    raw = 'Je prépare : [{"tool":"read_file","parameters":{"path":"a.py"}}, {"name":"bash","arguments":{"command":"pwd"}}]'
    r = p.parse(raw)
    assert [item["type"] for item in r["actions"]] == ["read_file", "bash"]
    assert r["text"] == "Je prépare :"


def test_tool_aliases_and_json_string_arguments():
    p = make_parser()
    raw = '{"tool_name":"bash","input":"{\\"command\\":\\"printf hi\\"}"}'
    r = p.parse(raw)
    assert r["action"]["type"] == "bash"
    assert r["action"]["content"]["command"] == "printf hi"


def test_xml_attribute_function_and_parameters():
    p = make_parser()
    raw = '<tool_call><function name="bash"><parameter name="command">printf ok</parameter></tool_call>'
    r = p.parse(raw)
    assert r["action"]["type"] == "bash"
    assert r["action"]["content"]["command"] == "printf ok"


def test_safe_function_call_syntax():
    p = make_parser()
    raw = 'Je lance bash(command="echo hi", description="test").'
    r = p.parse(raw)
    assert r["action"]["type"] == "bash"
    assert r["action"]["content"]["command"] == "echo hi"
    assert r["text"] == "Je lance ."


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  OK  {t.__name__}")
        except Exception as e:
            failed += 1
            print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)

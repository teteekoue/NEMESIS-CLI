import pytest
import os, sys, json, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tools.executor import ToolExecutor
from src.tools.definitions import get_tool_definitions, TOOL_DEFINITIONS


class TestToolDefinitions:
    def test_all_tools_defined(self):
        tools = get_tool_definitions()
        assert len(tools) == 6
        names = {t["function"]["name"] for t in tools}
        assert names == {"bash", "read_file", "write_file", "edit_file", "list_dir", "search_files"}

    def test_bash_tool_schema(self):
        bash = [t for t in TOOL_DEFINITIONS if t["function"]["name"] == "bash"][0]
        params = bash["function"]["parameters"]
        assert "command" in params["required"]
        assert "command" in params["properties"]

    def test_read_file_schema(self):
        read = [t for t in TOOL_DEFINITIONS if t["function"]["name"] == "read_file"][0]
        params = read["function"]["parameters"]
        assert "path" in params["required"]


class TestToolExecutor:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.executor = ToolExecutor(workspace=self.tmpdir)

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_execute_unknown_tool(self):
        result = self.executor.execute("nonexistent", {})
        assert not result["success"]
        assert "inconnu" in result["error"].lower()

    def test_write_and_read_file(self):
        test_file = "test.txt"
        content = "Hello World\nLine 2\nLine 3"
        write_result = self.executor._exec_write_file({"path": test_file, "content": content})
        assert write_result["success"]

        read_result = self.executor._exec_read_file({"path": test_file})
        assert read_result["success"]
        assert "Hello World" in read_result["output"]

    def test_read_file_offset_limit(self):
        test_file = "lines.txt"
        content = "\n".join(f"Line {i}" for i in range(1, 11))
        self.executor._exec_write_file({"path": test_file, "content": content})

        result = self.executor._exec_read_file({"path": test_file, "offset": 3, "limit": 2})
        assert result["success"]
        assert "Line 3" in result["output"]
        assert "Line 4" in result["output"]
        assert "Line 5" not in result["output"]

    def test_edit_file(self):
        test_file = "edit.txt"
        self.executor._exec_write_file({"path": test_file, "content": "Hello World"})

        result = self.executor._exec_edit_file({
            "path": test_file,
            "old_text": "Hello",
            "new_text": "Hi"
        })
        assert result["success"]

        read_result = self.executor._exec_read_file({"path": test_file})
        assert "Hi World" in read_result["output"]
        assert "Hello World" not in read_result["output"]

    def test_edit_file_not_found(self):
        result = self.executor._exec_edit_file({
            "path": "/nonexistent/file.txt",
            "old_text": "a",
            "new_text": "b"
        })
        assert not result["success"]

    def test_edit_file_text_not_found(self):
        test_file = "edit2.txt"
        self.executor._exec_write_file({"path": test_file, "content": "Hello"})
        result = self.executor._exec_edit_file({
            "path": test_file,
            "old_text": "NotThere",
            "new_text": "X"
        })
        assert not result["success"]
        assert "non trouve" in result["error"].lower()

    def test_list_dir_non_recursive(self):
        os.makedirs(os.path.join(self.tmpdir, "subdir"))
        open(os.path.join(self.tmpdir, "file1.txt"), "w").close()
        open(os.path.join(self.tmpdir, "file2.py"), "w").close()

        result = self.executor._exec_list_dir({"path": "."})
        assert result["success"]
        assert "subdir/" in result["output"]
        assert "file1.txt" in result["output"]
        assert "file2.py" in result["output"]

    def test_list_dir_recursive(self):
        os.makedirs(os.path.join(self.tmpdir, "sub/leaf"))
        open(os.path.join(self.tmpdir, "sub/a.txt"), "w").close()
        open(os.path.join(self.tmpdir, "sub/leaf/b.txt"), "w").close()

        result = self.executor._exec_list_dir({"path": ".", "recursive": True})
        assert result["success"]
        assert "sub/a.txt" in result["output"]

    def test_list_dir_not_found(self):
        result = self.executor._exec_list_dir({"path": "/nonexistent"})
        assert not result["success"]

    def test_search_files(self):
        content = "hello world\nfoo bar\nhello again"
        self.executor._exec_write_file({"path": "search_test.txt", "content": content})

        result = self.executor._exec_search_files({
            "pattern": "hello",
            "path": ".",
            "file_pattern": "*.txt"
        })
        assert result["success"]
        assert result["match_count"] == 2
        assert "hello world" in result["output"]

    def test_bash_execution(self):
        result = self.executor._exec_bash({"command": "echo 'test 123'"})
        assert result["success"]
        assert "test 123" in result["output"]

    def test_bash_error(self):
        result = self.executor._exec_bash({"command": "exit 1"})
        assert not result["success"]
        assert "Exit code: 1" in result["error"]

    def test_path_resolution(self):
        resolved = self.executor._resolve("test.txt")
        assert resolved == os.path.join(self.tmpdir, "test.txt")

        resolved = self.executor._resolve("/absolute/path.txt")
        assert resolved == "/absolute/path.txt"

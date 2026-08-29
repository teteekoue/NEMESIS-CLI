"""Tests for the ToolKind taxonomy and TemplateRenderer."""
import pytest
from src.core.tool_kind import ToolKind, ToolNamespace, ToolDefinition, ToolIdentity
from src.core.template_renderer import TemplateRenderer


class TestToolKind:
    def test_enum_variants(self):
        assert len(list(ToolKind)) == 34

    def test_namespace_values(self):
        namespaces = [ToolNamespace.GROK_BUILD, ToolNamespace.OPENCODE, ToolNamespace.MCP]
        assert len(namespaces) == 3

    def test_presentation_name(self):
        assert ToolKind.READ.presentation_name() == "Read"
        assert ToolKind.WEB_SEARCH.presentation_name() == "Web Search"
        assert ToolKind.LIST_DIR.presentation_name() == "List Files"
        assert ToolKind.KILL_TASK_ACTION.presentation_name() == "Kill Task"

    def test_is_read_only(self):
        assert ToolKind.READ.is_read_only() is True
        assert ToolKind.WEB_SEARCH.is_read_only() is True
        assert ToolKind.EDIT.is_read_only() is False
        assert ToolKind.EXECUTE.is_read_only() is False
        assert ToolKind.WRITE.is_read_only() is False
        assert ToolKind.SEARCH.is_read_only() is True
        assert ToolKind.LIST_DIR.is_read_only() is True
        assert ToolKind.MEMORY_SEARCH.is_read_only() is True
        assert ToolKind.ASK_USER.is_read_only() is True

    def test_tool_identity(self):
        ident = ToolIdentity(tool_kind=ToolKind.READ, namespace=ToolNamespace.GROK_BUILD)
        assert ident.tool_kind == ToolKind.READ
        assert ident.namespace == ToolNamespace.GROK_BUILD

    def test_tool_definition(self):
        td = ToolDefinition(
            name="read",
            description="Read a file",
            kind=ToolKind.READ,
            namespace=ToolNamespace.OPENCODE,
            params_schema={"type": "object", "properties": {"path": {"type": "string"}}},
        )
        assert td.name == "read"
        assert td.kind == ToolKind.READ


class TestTemplateRenderer:
    def test_empty_template(self):
        r = TemplateRenderer({ToolKind.READ: "read_file"})
        assert r.render("") == ""

    def test_no_variables(self):
        r = TemplateRenderer({ToolKind.READ: "read_file"})
        assert r.render("Hello, world!") == "Hello, world!"

    def test_tool_resolution(self):
        r = TemplateRenderer({ToolKind.READ: "read_file", ToolKind.EDIT: "edit"})
        tpl = "Use ${{ tools.by_kind.read }} for reading and ${{ tools.by_kind.edit }} for editing."
        result = r.render(tpl)
        assert "read_file" in result
        assert "edit" in result
        assert "${{" not in result

    def test_param_resolution(self):
        r = TemplateRenderer(
            {ToolKind.EDIT: "edit"},
            {ToolKind.EDIT: {"old_string": "old_str", "new_string": "new_str"}},
        )
        tpl = "Use ${{ params.edit.old_string }} and ${{ params.edit.new_string }}."
        result = r.render(tpl)
        assert "old_str" in result
        assert "new_str" in result
        assert "${{" not in result

    def test_if_block_true(self):
        r = TemplateRenderer({ToolKind.READ: "read_file"})
        tpl = r"${% if tools.by_kind.read %}Has read tool${% endif %}"
        result = r.render(tpl)
        assert "Has read tool" in result

    def test_if_block_false(self):
        r = TemplateRenderer({ToolKind.READ: "read_file"})
        tpl = r"${% if tools.by_kind.search %}Has search${% endif %}"
        result = r.render(tpl)
        assert result.strip() == ""

    def test_if_negation(self):
        r = TemplateRenderer({ToolKind.READ: "read_file"})
        tpl = r"${% if not tools.by_kind.search %}No search tool${% endif %}"
        result = r.render(tpl)
        assert "No search tool" in result

    def test_tool_for_kind(self):
        r = TemplateRenderer({ToolKind.READ: "read_file"})
        assert r.tool_for_kind(ToolKind.READ) == "read_file"
        assert r.tool_for_kind(ToolKind.EDIT) is None

    def test_fast_path(self):
        r = TemplateRenderer({ToolKind.READ: "read_file"})
        text = "Plain text without any variables"
        assert r.render(text) is text  # same object for fast-path

    def test_render_schema_descriptions(self):
        r = TemplateRenderer({ToolKind.EDIT: "edit"},
                              {ToolKind.EDIT: {"old_string": "old_str"}})
        schema = {
            "type": "object",
            "properties": {
                "old_string": {
                    "type": "string",
                    "description": "Use ${{ params.edit.old_string }}",
                }
            }
        }
        r.render_schema_descriptions(schema)
        assert "old_str" in schema["properties"]["old_string"]["description"]
        assert "${{" not in schema["properties"]["old_string"]["description"]

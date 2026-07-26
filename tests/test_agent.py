import pytest
import os, sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agent.core import NemesisAgent
from src.agent.modes import PlanMode, DualModelMode
from src.providers.base import BaseProvider, ProviderResponse


class MockProvider(BaseProvider):
    def __init__(self, responses=None, **kwargs):
        super().__init__(**kwargs)
        self.responses = responses or []
        self.call_count = 0

    def chat(self, messages, tools=None):
        if self.call_count < len(self.responses):
            resp = self.responses[self.call_count]
            self.call_count += 1
            return resp
        return ProviderResponse(content="default response")

    def list_models(self):
        return ["mock-model"]

    def test_connection(self):
        return True


class TestNemesisAgent:
    def setup_method(self):
        self.provider = MockProvider(
            api_key="test",
            responses=[ProviderResponse(content="Hello, how can I help?")]
        )
        self.agent = NemesisAgent(
            self.provider,
            "You are a helpful assistant.",
            [],
            None
        )

    def test_initialization(self):
        assert len(self.agent.messages) == 1
        assert self.agent.messages[0]["role"] == "system"

    def test_simple_chat(self):
        result = self.agent.chat("Hi!")
        assert result["content"] == "Hello, how can I help?"
        assert result["iterations"] == 1
        assert "error" not in result

    def test_chat_history(self):
        self.agent.chat("Hi!")
        assert len(self.agent.messages) >= 3
        assert self.agent.messages[-2]["role"] == "user"
        assert self.agent.messages[-1]["role"] == "assistant"

    def test_clear_history(self):
        self.agent.chat("Hi!")
        self.agent.clear_history()
        assert len(self.agent.messages) == 1
        assert self.agent.messages[0]["role"] == "system"

    def test_token_usage(self):
        provider = MockProvider(
            api_key="test",
            responses=[
                ProviderResponse(
                    content="resp1",
                    usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
                ),
                ProviderResponse(
                    content="resp2",
                    usage={"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}
                ),
            ]
        )
        agent = NemesisAgent(provider, "system", [], None)
        result = agent.chat("msg")
        usage = agent.get_token_usage()
        assert usage["total_tokens"] == 15

    def test_tool_calling_loop(self):
        tool_calls = [
            ProviderResponse(
                content="",
                tool_calls=[{"id": "t1", "name": "bash", "arguments": '{"command": "ls"}'}]
            ),
            ProviderResponse(content="Done! Files listed."),
        ]
        provider = MockProvider(api_key="test", responses=tool_calls)

        class MockToolExecutor:
            def __init__(self):
                self.mcp_manager = None

            def execute(self, name, args):
                return {"success": True, "output": "file1.txt\nfile2.txt"}

        agent = NemesisAgent(provider, "system", [], MockToolExecutor())
        result = agent.chat("List files")
        assert result["content"] == "Done! Files listed."
        assert result["iterations"] > 1

    def test_max_iterations(self):
        tool_calls = [ProviderResponse(
            content="",
            tool_calls=[{"id": f"t{j}", "name": "bash", "arguments": '{"command": "ls"}'}]
        ) for j in range(200)]

        class MockToolExecutor:
            mcp_manager = None

            def execute(self, name, args):
                return {"success": True, "output": "ok"}

        provider = MockProvider(api_key="test", responses=tool_calls)
        agent = NemesisAgent(provider, "system", [], MockToolExecutor())
        agent.max_iterations = 5
        result = agent.chat("loop")
        assert "Max" in result.get("error", "") and "itérations" in result.get("error", "")

    def test_set_system_prompt(self):
        self.agent.set_system_prompt("New prompt")
        assert self.agent.system_prompt == "New prompt"
        assert self.agent.messages[0]["content"] == "New prompt"

    def test_compact_history(self):
        provider = MockProvider(api_key="test",
            responses=[ProviderResponse(content=f"msg{i}") for i in range(20)]
        )
        agent = NemesisAgent(provider, "system", [], None)
        for i in range(10):
            agent.chat(f"msg{i}")
        initial_len = len(agent.messages)
        agent.compact_history()
        assert len(agent.messages) <= initial_len

    def test_tools_with_mcp(self):
        class MockMCPManager:
            def get_all_tools(self):
                return [{"type": "function", "function": {"name": "mcp_tool"}}]

        class MockToolExecutor:
            def __init__(self):
                self.mcp_manager = MockMCPManager()

        provider = MockProvider(api_key="test",
            responses=[ProviderResponse(content="ok")]
        )
        agent = NemesisAgent(provider, "system", [{"type": "function", "function": {"name": "bash"}}], MockToolExecutor())

        tools = agent.tools()
        tool_names = [t["function"]["name"] for t in tools]
        assert "bash" in tool_names
        assert "mcp_tool" in tool_names


class TestPlanMode:
    def test_create_plan(self):
        provider = MockProvider(
            api_key="test",
            responses=[ProviderResponse(content=json.dumps({
                "plan": "Create a hello world script",
                "steps": [
                    {"id": 1, "description": "Create file", "done": False},
                    {"id": 2, "description": "Test script", "done": False},
                ]
            }))]
        )
        agent = NemesisAgent(provider, "system", [], None)
        pm = PlanMode(agent)
        plan = pm.create_plan("make a script")
        assert len(plan["steps"]) == 2

    def test_create_plan_markdown_json(self):
        provider = MockProvider(
            api_key="test",
            responses=[ProviderResponse(content="```json\n" + json.dumps({
                "plan": "test",
                "steps": [{"id": 1, "description": "step 1", "done": False}]
            }) + "\n```")]
        )
        agent = NemesisAgent(provider, "system", [], None)
        pm = PlanMode(agent)
        plan = pm.create_plan("do something")
        assert plan["plan"] == "test"

    def test_execute_step(self):
        provider = MockProvider(
            api_key="test",
            responses=[ProviderResponse(content="Step completed")]
        )
        agent = NemesisAgent(provider, "system", [], None)
        pm = PlanMode(agent)
        result = pm.execute_step({"id": 1, "description": "do it"})
        assert result["content"] == "Step completed"

    def test_execute_all(self):
        responses = [
            ProviderResponse(content="Step 1 done"),
            ProviderResponse(content="Step 2 done"),
        ]
        provider = MockProvider(api_key="test", responses=responses)
        agent = NemesisAgent(provider, "system", [], None)
        pm = PlanMode(agent)
        pm.current_plan = {
            "plan": "test",
            "steps": [
                {"id": 1, "description": "s1", "done": False},
                {"id": 2, "description": "s2", "done": False},
            ]
        }
        results = pm.execute_all()
        assert len(results) == 2


class TestDualModelMode:
    def test_execute_approved(self):
        prov_a = MockProvider(
            api_key="test",
            responses=[ProviderResponse(content="Here is the solution")]
        )
        prov_b = MockProvider(
            api_key="test2",
            responses=[ProviderResponse(content=json.dumps({"approved": True, "issues": []}))]
        )
        dm = DualModelMode(prov_a, prov_b, [], None, "system")
        result = dm.execute("solve this")
        assert result["status"] == "approved"
        assert result["rounds"] == 1

    def test_execute_rejected_then_approved(self):
        responses_a = [
            ProviderResponse(content="Initial solution"),
            ProviderResponse(content="Improved solution"),
        ]
        responses_b = [
            ProviderResponse(content=json.dumps({"approved": False, "issues": ["bug"], "feedback": "fix it"})),
            ProviderResponse(content=json.dumps({"approved": True, "issues": []})),
        ]
        prov_a = MockProvider(api_key="a", responses=responses_a)
        prov_b = MockProvider(api_key="b", responses=responses_b)
        dm = DualModelMode(prov_a, prov_b, [], None, "system")
        result = dm.execute("solve", max_rounds=3)
        assert result["status"] == "approved"
        assert result["rounds"] == 2

    def test_parse_review_approved_words(self):
        dm = DualModelMode(None, None, [], None, "system")
        review = dm._parse_review("This is good, approved!")
        assert review["approved"]

        review = dm._parse_review("This needs work")
        assert not review["approved"]

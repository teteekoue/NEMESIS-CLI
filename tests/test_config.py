import pytest
import os, sys, json, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import NemesisConfig, load_config, save_config, load_mcp_servers, save_mcp_servers, CONFIG_DIR, ensure_config_dir


class TestNemesisConfig:
    def test_default_values(self):
        cfg = NemesisConfig()
        assert cfg.active_provider == "groq"
        assert cfg.active_model == ""
        assert cfg.workspace == "./workspace"
        assert not cfg.auto_allow
        assert not cfg.debug
        assert cfg.max_iterations == 100
        assert cfg.providers == {}
        assert cfg.sub_agent_apis == []
        assert cfg.dual_model == {}

    def test_to_dict(self):
        cfg = NemesisConfig(active_provider="openrouter", active_model="claude")
        d = cfg.to_dict()
        assert d["active_provider"] == "openrouter"
        assert d["active_model"] == "claude"

    def test_from_dict_filtering(self):
        d = {"active_provider": "cohere", "active_model": "cmd-r", "unknown_field": "should_be_ignored"}
        cfg = NemesisConfig.from_dict(d)
        assert cfg.active_provider == "cohere"
        assert cfg.active_model == "cmd-r"
        assert not hasattr(cfg, "unknown_field")

    def test_from_dict_missing_fields(self):
        d = {"active_provider": "groq"}
        cfg = NemesisConfig.from_dict(d)
        assert cfg.workspace == "./workspace"

    def test_save_and_load(self, monkeypatch, tmp_path):
        import src.config as config_mod
        monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
        monkeypatch.setattr(config_mod, "CONFIG_FILE", tmp_path / "config.json")
        monkeypatch.setattr(config_mod, "MCP_CONFIG_FILE", tmp_path / "mcp_servers.json")

        cfg = NemesisConfig(active_provider="test_prov", active_model="test_model")
        save_config(cfg)

        loaded = load_config()
        assert loaded.active_provider == "test_prov"
        assert loaded.active_model == "test_model"

    def test_load_config_file_doesnt_exist(self, monkeypatch, tmp_path):
        import src.config as config_mod
        monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
        monkeypatch.setattr(config_mod, "CONFIG_FILE", tmp_path / "nonexistent.json")

        cfg = load_config()
        assert cfg.active_provider == "groq"

    def test_load_config_corrupted_file(self, monkeypatch, tmp_path):
        import src.config as config_mod
        monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
        monkeypatch.setattr(config_mod, "CONFIG_FILE", tmp_path / "config.json")

        (tmp_path / "config.json").write_text("{corrupted json!!!")

        cfg = load_config()
        assert cfg.active_provider == "groq"

    def test_mcp_servers_save_load(self, monkeypatch, tmp_path):
        import src.config as config_mod
        monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
        monkeypatch.setattr(config_mod, "CONFIG_FILE", tmp_path / "config.json")
        monkeypatch.setattr(config_mod, "MCP_CONFIG_FILE", tmp_path / "mcp_servers.json")

        servers = {"server1": {"command": "python test.py"}, "server2": {"command": "node test.js"}}
        save_mcp_servers(servers)

        loaded = load_mcp_servers()
        assert loaded == servers

    def test_mcp_load_nonexistent(self, monkeypatch, tmp_path):
        import src.config as config_mod
        monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
        monkeypatch.setattr(config_mod, "MCP_CONFIG_FILE", tmp_path / "nonexistent.json")

        assert load_mcp_servers() == {}

    def test_auto_allow_field(self):
        cfg = NemesisConfig(auto_allow=True)
        assert cfg.auto_allow
        cfg.auto_allow = False
        assert not cfg.auto_allow

    def test_dual_model_field(self):
        cfg = NemesisConfig(
            dual_model={
                "model_a_provider": "groq",
                "model_a_model": "llama",
                "model_b_provider": "cohere",
                "model_b_model": "command-r",
            }
        )
        assert "model_a_provider" in cfg.dual_model
        assert "model_b_model" in cfg.dual_model

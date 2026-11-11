#!/usr/bin/env python3
"""Tests für das smb-dlna-Plugin (Manifest, Registrierung, Dienststeuerung)."""

import json

import pytest

import smb_dlna_plugin as plugin_mod
import tools


def _manifest():
    try:
        import yaml
    except ImportError:  # pragma: no cover
        pytest.skip("PyYAML nicht installiert")
    return yaml.safe_load(open("plugin.yaml", encoding="utf-8"))


def test_manifest_declares_the_registered_tools():
    manifest = _manifest()
    assert set(manifest["provides_tools"]) == set(tools.TOOL_SCHEMAS)
    assert len(tools.TOOL_SCHEMAS) == 5
    assert manifest["name"] == "smb-dlna"
    assert manifest["version"] == plugin_mod.Smb_dlna_Plugin.version


class FakeCtx:
    def __init__(self):
        self.tools = []
        self.commands = []

    def register_tool(self, name, toolset, schema, handler, **kwargs):
        self.tools.append({"name": name, "toolset": toolset, "schema": schema,
                           "handler": handler, **kwargs})

    def register_cli_command(self, name, help, setup_fn, handler_fn=None, description=""):
        self.commands.append({"name": name, "setup_fn": setup_fn,
                              "handler_fn": handler_fn})

    def get_config(self, key, default=None):
        return default


def test_register_registers_tools_and_cli():
    ctx = FakeCtx()
    plugin_mod.register(ctx)
    assert [tool["name"] for tool in ctx.tools] == list(tools.TOOL_SCHEMAS)
    assert all(tool["toolset"] == "smb_dlna" for tool in ctx.tools)
    assert [cmd["name"] for cmd in ctx.commands] == ["services"]


def test_status_groups_services(monkeypatch):
    plugin = plugin_mod.create_plugin()
    monkeypatch.setattr(plugin, "_is_active", lambda unit: unit != "minidlna.service")
    monkeypatch.setattr(plugin, "_is_enabled", lambda unit: True)
    status = plugin.status()
    assert set(status["units"]) == {"smb.service", "nmb.service", "minidlna.service"}
    assert status["services"]["smb"]["active"] is True
    assert status["services"]["smb"]["enabled"] is True
    assert status["services"]["dlna"]["active"] is False
    assert status["services"]["dlna"]["units"]["minidlna.service"]["active"] is False


def test_start_stop_enable_disable(monkeypatch):
    plugin = plugin_mod.create_plugin()
    calls = []

    def fake_systemctl(action, unit, sudo=False):
        calls.append((action, unit, sudo))
        return True, "ok"

    monkeypatch.setattr(plugin, "_systemctl", fake_systemctl)

    result = plugin.start("smb")
    assert result["ok"] is True
    assert calls == [("start", "smb.service", True), ("start", "nmb.service", True)]

    calls.clear()
    plugin.stop("smb")
    assert [call[1] for call in calls] == ["nmb.service", "smb.service"]

    calls.clear()
    plugin.enable("all")
    assert [call[0] for call in calls] == ["enable", "enable", "enable"]

    calls.clear()
    plugin.disable("dlna")
    assert calls == [("disable", "minidlna.service", True)]


def test_invalid_service_is_rejected_without_calls(monkeypatch):
    plugin = plugin_mod.create_plugin()
    calls = []
    monkeypatch.setattr(plugin, "_systemctl", lambda *a, **k: (calls.append(a) or (True, "ok")))
    result = plugin.start("bogus")
    assert result["ok"] is False
    assert "Unbekannter Dienst" in result["error"]
    assert calls == []


def test_tool_handlers_return_json(monkeypatch):
    monkeypatch.setattr(tools, "create_plugin",
                        lambda: plugin_mod.Smb_dlna_Plugin())
    ctx = FakeCtx()
    handlers = tools.make_handlers(ctx)
    # Status gegen gemockte systemctl-Aufrufe
    plugin = plugin_mod.Smb_dlna_Plugin()
    monkeypatch.setattr(plugin, "_is_active", lambda unit: True)
    monkeypatch.setattr(plugin, "_is_enabled", lambda unit: False)
    monkeypatch.setattr(tools, "create_plugin", lambda: plugin)
    result = json.loads(handlers["services_status"]({}))
    assert result["services"]["smb"]["active"] is True
    assert result["services"]["smb"]["enabled"] is False

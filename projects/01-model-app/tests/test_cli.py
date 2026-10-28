from __future__ import annotations

import pytest

from signal_agent.cli import EXIT_CONFIG, main


def test_missing_key_exits_with_config_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path, capsys
) -> None:
    # chdir so a developer's real .env cannot make this test hit the network.
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("SIGNAL_OPENROUTER_API_KEY", raising=False)

    code = main(["ask", "hello"])

    assert code == EXIT_CONFIG
    err = capsys.readouterr().err
    assert "OPENROUTER_API_KEY" in err

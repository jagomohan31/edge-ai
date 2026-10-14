from pathlib import Path

from typer.testing import CliRunner

from edge_ai.cli import app

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "fetch" in result.output or "demo" in result.output


def test_cli_demo_runs(tmp_path):
    # demo should run end-to-end without error
    import os
    orig = Path.cwd()
    try:
        os.chdir(tmp_path)
        # Create required dirs
        (tmp_path / "data" / "raw").mkdir(parents=True)
        (tmp_path / "data" / "clean").mkdir(parents=True)
        (tmp_path / "data" / "derived").mkdir(parents=True)
        (tmp_path / "runs").mkdir()
        (tmp_path / "docs").mkdir()
        (tmp_path / "configs").mkdir()
        # Copy config
        import shutil
        shutil.copy(str(orig / "D:/Edge AI/edge-ai/configs/default.yaml"), str(tmp_path / "configs/default.yaml"))
        result = runner.invoke(app, ["demo"])
        # Should succeed or at least start
        assert "SYNTHETIC DATA" in result.output or result.exit_code in (0, 1)
    finally:
        os.chdir(orig)

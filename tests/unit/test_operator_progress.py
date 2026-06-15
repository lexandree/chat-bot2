from __future__ import annotations

from app.operator_progress import OperatorProgress


def test_non_tty_operator_progress_emits_bounded_milestones_to_stderr(capsys) -> None:
    progress = OperatorProgress(enabled=True, label="test-run")

    for processed in range(101):
        progress.update("write", processed, 100)
    progress.finish(status="completed", detail="records=100")

    lines = capsys.readouterr().err.splitlines()
    assert len(lines) == 12
    assert lines[0].startswith("test-run: stage=write 0/100")
    assert "test-run: stage=write 100/100" in lines[-2]
    assert lines[-1] == "test-run: status=completed | records=100"

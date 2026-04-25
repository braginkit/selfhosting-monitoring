from pathlib import Path

from monitoring.targets import load_targets


def test_load_targets_parses_yaml(tmp_path: Path) -> None:
    targets_file = tmp_path / "targets.yml"
    targets_file.write_text(
        "\n".join(
            [
                "targets:",
                "  - name: app",
                "    type: http",
                "    url: https://example.invalid/health",
                "    timeout_seconds: 15",
                "  - name: mail",
                "    type: smtp",
                "    host: smtp.example.invalid",
                "    port: 587",
            ]
        ),
        encoding="utf-8",
    )

    targets = load_targets(targets_file)

    assert len(targets) == 2
    assert targets[0].name == "app"
    assert targets[0].type == "http"
    assert targets[0].timeout_seconds == 15
    assert targets[1].name == "mail"
    assert targets[1].host == "smtp.example.invalid"

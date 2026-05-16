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


def test_load_empty_targets_file(tmp_path: Path) -> None:
    targets_file = tmp_path / "targets.yml"
    targets_file.write_text("targets: []\n", encoding="utf-8")

    assert load_targets(targets_file) == []


def test_load_test_fixture_matches_expected_services() -> None:
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "targets.test.yml"
    targets = load_targets(fixture)
    names = {target.name for target in targets}

    assert names == {"hoppscotch", "matrix", "mail_smtp", "local_dns"}


def test_load_production_example_has_no_placeholder_hosts() -> None:
    example = Path(__file__).resolve().parents[2] / "targets.yml.example"
    targets = load_targets(example)

    for target in targets:
        if target.url:
            assert "example.invalid" not in target.url
        if target.host:
            assert "example.invalid" not in target.host
        if target.query:
            assert "example.invalid" not in target.query

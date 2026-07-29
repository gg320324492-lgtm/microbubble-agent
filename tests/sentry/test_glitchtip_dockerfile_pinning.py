"""W87-B-1: GlitchTip compose presence, image pin, ports, and additive-only guard."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_REF = "1a3ebbea5"
IMAGE = "glitchtip/glitchtip:6.2.2"
COMPOSE_CASES = {
    "production": ("docker-compose.yml", "127.0.0.2:8000:8000", "db", "default"),
    "dev": ("docker-compose.dev.yml", "8001:8000", "db", "default"),
    "test": ("docker-compose.test.yml", "8002:8000", "pg-test", "mb-test-net"),
}
SEMVER_IMAGE_RE = re.compile(r"^glitchtip/glitchtip:v?\d+\.\d+\.\d+$")
SERVICE_HEADER_RE = re.compile(r"^  (?P<name>[A-Za-z0-9_-]+):\s*$", re.MULTILINE)


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def _compose(rel_path: str) -> dict:
    return yaml.safe_load(_read(rel_path).encode("utf-8", errors="replace").decode("utf-8"))


def _compose_with(text: str) -> dict:
    return yaml.safe_load(text)


def _git_show(ref: str, rel_path: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{ref}:{rel_path}"],
        cwd=REPO_ROOT,
        capture_output=True,
        timeout=30,
        check=False,
    )
    stderr = result.stderr.decode("utf-8", errors="replace")
    assert result.returncode == 0, stderr
    # Repository blobs predate a consistent Windows text encoding policy. All
    # service keys/values protected by this test are ASCII; replacement is only
    # relevant to comments and keeps semantic YAML comparison deterministic.
    return result.stdout.decode("utf-8", errors="replace")


def _raw_service_block(content: str, service_name: str) -> str:
    matches = list(SERVICE_HEADER_RE.finditer(content))
    for index, match in enumerate(matches):
        if match.group("name") == service_name:
            end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
            return content[match.start():end]
    return ""


@pytest.mark.parametrize("stack", COMPOSE_CASES)
def test_glitchtip_service_present(stack):
    rel_path, _, _, _ = COMPOSE_CASES[stack]
    services = _compose(rel_path)["services"]
    assert "glitchtip" in services


@pytest.mark.parametrize("stack", COMPOSE_CASES)
def test_glitchtip_image_is_patch_pinned(stack):
    rel_path, _, _, _ = COMPOSE_CASES[stack]
    image = _compose(rel_path)["services"]["glitchtip"]["image"]
    assert image == IMAGE
    assert SEMVER_IMAGE_RE.fullmatch(image), image
    assert not image.endswith(":latest")


@pytest.mark.parametrize("stack", COMPOSE_CASES)
def test_ports_and_dependencies_are_isolated(stack):
    rel_path, expected_port, expected_db, expected_network = COMPOSE_CASES[stack]
    service = _compose(rel_path)["services"]["glitchtip"]

    assert expected_port in service["ports"]
    assert expected_db in service["depends_on"]
    assert expected_network in service["networks"]
    assert service["environment"]["SERVER_ROLE"] == "all_in_one"
    assert service["environment"]["EMAIL_ENABLED"] == "False"


@pytest.mark.parametrize("stack", COMPOSE_CASES)
def test_only_glitchtip_service_was_added(stack):
    """Compare every pre-existing service's parsed configuration to the exact base."""
    rel_path, _, _, _ = COMPOSE_CASES[stack]
    before_text = _git_show(BASE_REF, rel_path)
    after_text = _read(rel_path)
    before_services = _compose_with(before_text)["services"]
    after_services = _compose_with(after_text)["services"]

    assert set(after_services) == {*before_services, "glitchtip"}
    for service_name, before_config in before_services.items():
        assert after_services[service_name] == before_config, (
            f"{rel_path}: pre-existing service {service_name!r} changed; "
            "W87-B-1 allows only adding glitchtip"
        )

    assert _raw_service_block(after_text, "glitchtip")


def test_three_host_ports_are_unique():
    container_ports = {case[1].rsplit(":", 1)[-1] for case in COMPOSE_CASES.values()}
    # 127.0.0.2:8000:8000 has two colons; rsplit(...,1) returns the container segment "8000".
    assert container_ports == {"8000"}, container_ports
    # Real isolation comes from bind addresses: production 127.0.0.2, dev/test 0.0.0.0
    # on 8001/8002, and the app service already owning 127.0.0.1:8000.
    production = _compose("docker-compose.yml")["services"]
    dev = _compose("docker-compose.dev.yml")["services"]
    test = _compose("docker-compose.test.yml")["services"]

    assert production["app"]["ports"][0] == "127.0.0.1:8000:8000"
    assert production["glitchtip"]["ports"][0] == "127.0.0.2:8000:8000"
    assert dev["glitchtip"]["ports"][0] == "8001:8000"
    assert test["glitchtip"]["ports"][0] == "8002:8000"

    bind_addresses = {production["glitchtip"]["ports"][0], dev["glitchtip"]["ports"][0], test["glitchtip"]["ports"][0]}
    assert bind_addresses == {"127.0.0.2:8000:8000", "8001:8000", "8002:8000"}

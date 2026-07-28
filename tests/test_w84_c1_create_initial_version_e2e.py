from pathlib import Path


def test_drive_upload_initial_version_is_injected_at_all_entrypoints():
    source = Path("app/services/drive_service.py").read_text()
    assert source.count("await create_initial_version(") >= 3
    assert "from app.services.drive_upload_service import create_initial_version" in source

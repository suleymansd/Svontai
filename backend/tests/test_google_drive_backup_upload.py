from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "upload_backup_to_google_drive.py"
SPEC = importlib.util.spec_from_file_location("upload_backup_to_google_drive", SCRIPT_PATH)
assert SPEC and SPEC.loader
drive_backup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(drive_backup)


def test_escape_query_handles_quotes_and_backslashes():
    assert drive_backup._escape_query("owner's\\folder") == "owner\\'s\\\\folder"


def test_required_env_rejects_missing_value(monkeypatch):
    monkeypatch.delenv("GOOGLE_DRIVE_BACKUP_CLIENT_ID", raising=False)

    with pytest.raises(drive_backup.DriveBackupError, match="GOOGLE_DRIVE_BACKUP_CLIENT_ID"):
        drive_backup._required_env("GOOGLE_DRIVE_BACKUP_CLIENT_ID")


def test_delete_expired_backups_only_deletes_query_results(monkeypatch):
    monkeypatch.setattr(
        drive_backup,
        "_list_files",
        lambda token, query: [
            {"id": "file-1", "name": "svontai-postgres-1.dump.gpg"},
            {"id": "file-2", "name": "svontai-postgres-2.dump.gpg"},
        ],
    )
    calls = []

    def fake_request(url, **kwargs):
        calls.append((url, kwargs))
        return {}, {}

    monkeypatch.setattr(drive_backup, "_request_json", fake_request)

    removed = drive_backup._delete_expired_backups("token", "folder-id", 30)

    assert removed == 2
    assert [call[0].rsplit("/", 1)[-1] for call in calls] == ["file-1", "file-2"]
    assert all(call[1]["method"] == "DELETE" for call in calls)


def test_main_requires_gpg_input(monkeypatch, tmp_path):
    plaintext = tmp_path / "backup.dump"
    plaintext.write_bytes(b"not encrypted")
    monkeypatch.setattr(
        "sys.argv",
        ["upload_backup_to_google_drive.py", str(plaintext), "--name", "backup.dump"],
    )

    with pytest.raises(drive_backup.DriveBackupError, match="Only GPG-encrypted"):
        drive_backup.main()

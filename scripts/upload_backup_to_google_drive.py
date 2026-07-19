#!/usr/bin/env python3
"""Upload an encrypted database backup to an app-owned Google Drive folder."""

from __future__ import annotations

import argparse
import http.client
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path


DRIVE_API = "https://www.googleapis.com/drive/v3"
DRIVE_UPLOAD_API = "https://www.googleapis.com/upload/drive/v3"
TOKEN_URL = "https://oauth2.googleapis.com/token"
DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"


class DriveBackupError(RuntimeError):
    pass


def _required_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise DriveBackupError(f"Missing required environment variable: {name}")
    return value


def _request_json(
    url: str,
    *,
    method: str = "GET",
    token: str | None = None,
    payload: dict | None = None,
) -> tuple[dict, dict[str, str]]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json; charset=UTF-8"

    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
            data = json.loads(raw.decode("utf-8")) if raw else {}
            return data, {key.lower(): value for key, value in response.headers.items()}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise DriveBackupError(f"Google Drive API returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise DriveBackupError(f"Google Drive API connection failed: {exc.reason}") from exc


def _refresh_access_token() -> str:
    form = urllib.parse.urlencode(
        {
            "client_id": _required_env("GOOGLE_DRIVE_BACKUP_CLIENT_ID"),
            "client_secret": _required_env("GOOGLE_DRIVE_BACKUP_CLIENT_SECRET"),
            "refresh_token": _required_env("GOOGLE_DRIVE_BACKUP_REFRESH_TOKEN"),
            "grant_type": "refresh_token",
            "scope": DRIVE_FILE_SCOPE,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        TOKEN_URL,
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise DriveBackupError(f"Google OAuth token refresh failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise DriveBackupError(f"Google OAuth token refresh connection failed: {exc.reason}") from exc

    token = str(payload.get("access_token") or "").strip()
    if not token:
        raise DriveBackupError("Google OAuth response did not contain an access token")
    return token


def _escape_query(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _list_files(token: str, query: str) -> list[dict]:
    files: list[dict] = []
    page_token = ""
    while True:
        params = {
            "q": query,
            "spaces": "drive",
            "fields": "nextPageToken,files(id,name,createdTime)",
            "pageSize": "1000",
        }
        if page_token:
            params["pageToken"] = page_token
        payload, _ = _request_json(
            f"{DRIVE_API}/files?{urllib.parse.urlencode(params)}",
            token=token,
        )
        files.extend(payload.get("files") or [])
        page_token = str(payload.get("nextPageToken") or "")
        if not page_token:
            return files


def _get_or_create_folder(token: str, folder_name: str) -> str:
    escaped_name = _escape_query(folder_name)
    query = (
        f"name = '{escaped_name}' and "
        "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    folders = _list_files(token, query)
    if folders:
        return str(folders[0]["id"])

    payload, _ = _request_json(
        f"{DRIVE_API}/files?fields=id,name",
        method="POST",
        token=token,
        payload={
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        },
    )
    folder_id = str(payload.get("id") or "")
    if not folder_id:
        raise DriveBackupError("Google Drive folder creation did not return an id")
    return folder_id


def _existing_backup(token: str, folder_id: str, backup_name: str) -> dict | None:
    query = (
        f"'{_escape_query(folder_id)}' in parents and "
        f"name = '{_escape_query(backup_name)}' and trashed = false"
    )
    files = _list_files(token, query)
    return files[0] if files else None


def _start_resumable_upload(
    token: str,
    folder_id: str,
    backup_name: str,
    file_size: int,
) -> str:
    request = urllib.request.Request(
        f"{DRIVE_UPLOAD_API}/files?uploadType=resumable&fields=id,name,createdTime",
        data=json.dumps({"name": backup_name, "parents": [folder_id]}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "application/octet-stream",
            "X-Upload-Content-Length": str(file_size),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            upload_url = str(response.headers.get("Location") or "")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise DriveBackupError(f"Google Drive upload session failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise DriveBackupError(f"Google Drive upload session connection failed: {exc.reason}") from exc
    if not upload_url:
        raise DriveBackupError("Google Drive did not return a resumable upload URL")
    return upload_url


def _stream_upload(token: str, upload_url: str, path: Path) -> dict:
    parsed = urllib.parse.urlparse(upload_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise DriveBackupError("Google Drive returned an invalid upload URL")

    target = parsed.path + (f"?{parsed.query}" if parsed.query else "")
    connection = http.client.HTTPSConnection(parsed.hostname, parsed.port, timeout=180)
    try:
        connection.putrequest("PUT", target)
        connection.putheader("Authorization", f"Bearer {token}")
        connection.putheader("Content-Type", "application/octet-stream")
        connection.putheader("Content-Length", str(path.stat().st_size))
        connection.endheaders()
        with path.open("rb") as handle:
            while chunk := handle.read(8 * 1024 * 1024):
                connection.send(chunk)
        response = connection.getresponse()
        raw = response.read()
        if response.status < 200 or response.status >= 300:
            detail = raw.decode("utf-8", errors="replace")[:500]
            raise DriveBackupError(f"Google Drive upload failed with HTTP {response.status}: {detail}")
        return json.loads(raw.decode("utf-8")) if raw else {}
    finally:
        connection.close()


def _delete_expired_backups(token: str, folder_id: str, retention_days: int) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    cutoff_value = cutoff.isoformat(timespec="seconds").replace("+00:00", "Z")
    query = (
        f"'{_escape_query(folder_id)}' in parents and "
        "name contains 'svontai-postgres-' and "
        f"createdTime < '{cutoff_value}' and trashed = false"
    )
    expired = _list_files(token, query)
    for item in expired:
        _request_json(
            f"{DRIVE_API}/files/{urllib.parse.quote(str(item['id']))}",
            method="DELETE",
            token=token,
        )
    return len(expired)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", type=Path)
    parser.add_argument("--name", required=True)
    parser.add_argument("--folder", default="SvontAI Backups")
    parser.add_argument("--retention-days", type=int, default=30)
    args = parser.parse_args()

    if not args.backup.is_file():
        raise DriveBackupError(f"Encrypted backup does not exist: {args.backup}")
    if args.backup.suffix != ".gpg":
        raise DriveBackupError("Only GPG-encrypted backup files may be uploaded")
    if args.retention_days < 7:
        raise DriveBackupError("Google Drive retention must be at least 7 days")

    token = _refresh_access_token()
    folder_id = _get_or_create_folder(token, args.folder)
    existing = _existing_backup(token, folder_id, args.name)
    if existing:
        print(f"Google Drive backup already exists: {existing.get('name')} ({existing.get('id')})")
        return 0

    upload_url = _start_resumable_upload(
        token,
        folder_id,
        args.name,
        args.backup.stat().st_size,
    )
    uploaded = _stream_upload(token, upload_url, args.backup)
    removed = _delete_expired_backups(token, folder_id, args.retention_days)
    print(f"Google Drive backup uploaded: {uploaded.get('name')} ({uploaded.get('id')}); expired removed: {removed}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DriveBackupError as exc:
        print(f"Drive backup failed: {exc}", file=sys.stderr)
        raise SystemExit(1)

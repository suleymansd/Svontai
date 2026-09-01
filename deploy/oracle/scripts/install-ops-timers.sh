#!/usr/bin/env bash
set -Eeuo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run with sudo: sudo ./scripts/install-ops-timers.sh" >&2
  exit 1
fi

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

cat >/etc/systemd/system/svontai-volume-backup.service <<EOF
[Unit]
Description=SvontAI encrypted application-volume backup
Requires=docker.service
After=docker.service network-online.target

[Service]
Type=oneshot
WorkingDirectory=$ROOT
ExecStart=$ROOT/scripts/backup-volumes.sh
Nice=10
IOSchedulingClass=best-effort
IOSchedulingPriority=7
EOF

cat >/etc/systemd/system/svontai-volume-backup.timer <<'EOF'
[Unit]
Description=Run SvontAI application-volume backup nightly

[Timer]
OnCalendar=*-*-* 03:35:00 Europe/Istanbul
RandomizedDelaySec=20m
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now svontai-volume-backup.timer
systemctl list-timers svontai-volume-backup.timer --no-pager

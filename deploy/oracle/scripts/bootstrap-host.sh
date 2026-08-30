#!/usr/bin/env bash
set -Eeuo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run with sudo: sudo ./scripts/bootstrap-host.sh" >&2
  exit 1
fi

if [[ $(uname -s) != "Linux" ]]; then
  echo "This bootstrap script only supports Ubuntu Linux." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates curl git gnupg jq openssl postgresql-client ufw unattended-upgrades

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

. /etc/os-release
cat >/etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${UBUNTU_CODENAME:-$VERSION_CODENAME}
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.gpg
EOF

apt-get update
apt-get install -y --no-install-recommends \
  docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable --now docker
systemctl enable --now unattended-upgrades

if [[ -n "${SUDO_USER:-}" && "$SUDO_USER" != "root" ]]; then
  usermod -aG docker "$SUDO_USER"
fi

ufw default deny incoming
ufw default allow outgoing
ufw allow 80/tcp
ufw allow 443/tcp

cat <<'EOF'

Docker and the host firewall are ready.

Sign out and reconnect once so your administrator account receives Docker group
membership before running docker compose commands.

SSH has intentionally not been changed. Before enabling UFW, allow SSH only
from your own public IP, for example:

  sudo ufw allow from YOUR.PUBLIC.IP.ADDRESS to any port 22 proto tcp
  sudo ufw enable

Also allow TCP 80/443 and your restricted SSH source in the Oracle VCN ingress
rules. Do not expose PostgreSQL, Redis, OpenWA, n8n broker, or container ports.
EOF

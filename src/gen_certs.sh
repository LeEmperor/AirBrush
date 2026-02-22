#!/usr/bin/env bash
set -euo pipefail

# Run from AirBrush/src (or it will write cert.pem/key.pem in the current dir)
# Requires: mkcert
# Optional (recommended): libnss3-tools for Chrome/Chromium trust integration

need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing '$1'. Install it first."; exit 1; }; }

need mkcert

# Detect primary IPv4 (best-effort). Override by: IP=192.168.x.y ./gen_certs.sh
IP="${IP:-$(ip route get 1.1.1.1 2>/dev/null | awk '/src/ {for(i=1;i<=NF;i++) if($i=="src"){print $(i+1); exit}}')}"

if [[ -z "${IP}" ]]; then
  echo "Could not auto-detect IPv4. Run: IP=YOUR_IPv4 ./gen_certs.sh"
  exit 1
fi

echo "Using IPv4: $IP"

# Ensure local CA is installed (safe to run repeatedly)
mkcert -install >/dev/null

# Generate cert for IP + localhost
mkcert "$IP" localhost 127.0.0.1 >/dev/null

# mkcert outputs files like: <name>+2.pem and <name>+2-key.pem (name may include dots)
CERT_SRC="${IP}+2.pem"
KEY_SRC="${IP}+2-key.pem"

# Fallback: find most recent pair if naming differs
if [[ ! -f "$CERT_SRC" || ! -f "$KEY_SRC" ]]; then
  CERT_SRC="$(ls -t ./*.pem 2>/dev/null | grep -v -- '-key\.pem$' | head -n1 || true)"
  KEY_SRC="${CERT_SRC%.pem}-key.pem"
fi

if [[ -z "${CERT_SRC}" || ! -f "$CERT_SRC" || ! -f "$KEY_SRC" ]]; then
  echo "Could not find generated mkcert files."
  exit 1
fi

cp -f "$CERT_SRC" cert.pem
cp -f "$KEY_SRC" key.pem

echo "Wrote:"
echo "  cert.pem"
echo "  key.pem"

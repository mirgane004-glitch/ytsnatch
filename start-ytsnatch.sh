#!/data/data/com.termux/files/usr/bin/bash
# YTSnatch - public launcher (run inside Termux, from this folder)
#
# Starts the website on this phone and opens a free Cloudflare tunnel,
# giving you a public https link that anyone can open. Downloads run on
# the phone's own connection, which YouTube does not block.
#
# The link changes every time you start the tunnel - that's normal for
# the free tunnel. Keep this session open while the site is in use.
# Press CTRL+C to shut the public site down.

cd "$(dirname "$0")" || exit 1

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "One-time setup needed. Run this first, then run this file again:"
  echo "    pkg install -y cloudflared"
  exit 1
fi

if curl -s http://localhost:5001 >/dev/null 2>&1; then
  echo "YTSnatch is already running on this phone (port 5001)."
else
  echo "Starting YTSnatch on this phone..."
  nohup python3 app.py > ~/ytsnatch-server.log 2>&1 &
  sleep 3
fi

echo ""
echo "Opening the public tunnel..."
echo "Your public link appears below (ends in .trycloudflare.com)."
echo "Share it with anyone. Keep this session open; CTRL+C stops it."
echo ""
cloudflared tunnel --url http://localhost:5001

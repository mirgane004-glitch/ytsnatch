---
title: YTSnatch
emoji: ⬇️
colorFrom: red
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
---

# YTSnatch

Paste a YouTube link, pick a quality (it remembers your usual choice),
and the server downloads the video and sends the file back to your device.

Flask + yt-dlp. Downloaded files are deleted from the server a few
minutes after delivery — nothing is stored.

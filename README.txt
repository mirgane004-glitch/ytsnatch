TubeFetch - YouTube downloader website (Muse edition)
======================================================

A local website: paste a YouTube link, see the video's title/thumbnail,
pick a quality (it remembers your choice for next time), download with a
live progress bar. Runs entirely on your phone in Termux.

ONE-TIME INSTALL (in Termux)
----------------------------
1. System packages (Python + ffmpeg for merging HD video and audio):

   pkg install -y python ffmpeg

2. Go into this folder (adjust the path to where you unzipped it), e.g.:

   cd ~/tubefetch

3. Install the Python packages:

   pip install -r requirements.txt

START THE WEBSITE
-----------------
   python3 app.py

Leave that session running, then open Chrome and go to:

   http://localhost:5001

(Port 5001, so it can run at the same time as TubeGrab on 5000 -
 handy for comparing the two.)

HOW IT WORKS
------------
- Paste a link and tap "Get video" (or press Enter). First fetch can
  take 10-30 seconds - a spinner shows while it works.
- Tap a quality card to choose it. Your choice is saved in the browser
  and pre-selected for the next video (marked "your usual").
- Tick "Always download in this quality without asking" and downloads
  start with one tap after fetching.
- Downloads land in the Downloads folder inside this project folder.
- The last 10 downloads are listed at the bottom of the page.

TROUBLESHOOTING
---------------
- Downloads failing on many videos? Update the downloader engine:
  pip install -U yt-dlp   (then restart python3 app.py)
- "Is python3 app.py still running?" - the page can only talk to the
  server while that Termux session is open.
- Stop the server with CTRL+C in its session.

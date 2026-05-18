<div align="center">

<img src="https://raw.githubusercontent.com/rhshourav/HydraCast/refs/heads/main/resources/HydraCast.svg" alt="HydraCast Logo" width="96"/>

# HydraCast

**Multi-Stream RTSP/HLS 24/7 Broadcast Scheduler**

[![License](https://img.shields.io/badge/License-HydraCast%20Software%20License-b87333.svg)](https://github.com/rhshourav/HydraCast/blob/main/LICENSE)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python&logoColor=white)](https://python.org)
[![GitHub](https://img.shields.io/badge/GitHub-rhshourav-333?logo=github)](https://github.com/rhshourav/HydraCast)

![HydraCast Dashboard](https://raw.githubusercontent.com/rhshourav/HydraCast/refs/heads/main/resources/repoHC.png)

</div>

---

HydraCast is a lightweight Python application that turns your media files into continuous 24/7 live RTSP and HLS broadcast streams. It manages multiple FFmpeg processes, integrates with MediaMTX for stream serving, and exposes a full-featured Web Dashboard for remote control — no manual FFmpeg wrangling required.

## ✨ Features

### 🎬 Multi-Stream Broadcasting
- Run any number of independent RTSP streams simultaneously, each on its own port
- HLS output for browser-compatible playback alongside RTSP
- Per-stream video and audio bitrate control
- Copy RTSP or HLS URLs to clipboard in one click
- Export all stream URLs to a CSV file (optionally include current playlist filenames)
- **Start All / Stop All** global controls in the top bar

### 📅 Weekly Scheduling
- Assign streams to run on specific weekdays (Mon–Sun, any combination, or all days)
- Streams automatically start and stop according to their day schedule

### 🎵 Playlist & Source Management
- **File playlist** — hand-pick an ordered list of media files per stream
- **Folder source** — point to a directory; HydraCast auto-scans and rebuilds the playlist whenever files change
- Day-tag detection in folder mode: filenames containing `_mon_`, `_tue_`, etc. are automatically assigned to the right weekday
- Shuffle mode for randomised playback order
- Loop count control per stream

### 📡 Compliance Mode (Broadcast Sync)
- Simulates a real linear broadcast: on start, HydraCast calculates the correct seek offset so viewers see exactly what a continuous broadcast running since a configured time today would show right now
- Optional loop calculation for content shorter than 24 hours

### 🗓️ One-Shot Event Scheduler
- Full monthly calendar UI to schedule one-off playback events
- **Multi-date selection** — pick several dates in one session and schedule the same event across all of them at once
- After-event behaviour per event: resume normal playlist, stop stream, or show a black screen
- 1-minute countdown alert notification before each event fires
- Event sidebar with the month's upcoming and played events
- Cancel a running event from the stream row to immediately resume normal operation
- Clear all played events in bulk; hide played events from the sidebar list

### 📁 Media File Manager
- Browse your media library folder tree from the browser
- Drag-and-drop or click-to-upload media files into any subfolder
- Create new folders and subfolders
- Rename, move, copy, and delete files and folders

### 📊 System Monitoring
- Live CPU and RAM usage shown in the top bar, updated on a configurable interval
- Disk usage visible in the Settings panel
- Per-stream progress, current file, loop count, and queue (next-up files) shown in the Streams table
- Real-time compliance alert banner when a stream falls out of sync

### 📧 Email Alerts
Three authentication modes, all configurable from the Settings panel:

| Mode | Use case |
|---|---|
| **Gmail (OAuth2)** | Google accounts — no password stored |
| **Microsoft (OAuth2)** | Outlook / Office 365 — device sign-in flow |
| **SMTP** | Yahoo Mail, Gmail App Password, or any custom SMTP server |

### 💾 Backup & Restore
Selective backup with individual checkboxes for:
- Stream configurations (`streams.json`)
- Scheduled events (`events.json`)
- Per-file resume positions (`resume_positions.json`)
- Application settings (holiday country, UI preferences, etc.)

Download as a `.hc` file and restore in one click from the Settings panel.

### 🌍 Holiday Calendar
- Fetch public holidays by country and optional subdivision
- Highlighted on the Events calendar so you can plan around them
- Add custom holidays manually
- Holiday data is cached and refreshable on demand

### 🎨 Web Dashboard
- Dark and light themes with a single toggle
- 7 tabs: **Streams**, **Viewer**, **Config**, **Logs**, **Media**, **Events**, **Settings**
- In-browser HLS video preview — click any stream card in the Viewer tab to watch live
- Interactive seek modal (enter seconds or `HH:MM:SS`, or drag a slider) for any live stream
- Configurable auto-refresh intervals for stream status, system stats, and logs
- Compact mode to fit more streams on screen
- Persistent UI preferences saved in `localStorage`

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- `ffmpeg` and `ffprobe` on your system PATH (or placed in the `bin/` directory)
- MediaMTX is downloaded automatically on first run

### Installation

```bash
git clone https://github.com/rhshourav/HydraCast.git
cd HydraCast
python hydracast.py
```

Dependencies (`rich`, `psutil`) are bootstrapped automatically on first run. The Web Dashboard is available at `http://localhost:8080` by default.

### Command-Line Arguments

| Argument | Default | Description |
|---|---|---|
| `--listen IP` | `0.0.0.0` | IP address for MediaMTX to bind on |
| `--web-port PORT` | `8080` | Web Dashboard port |
| `--no-web` | — | Disable the embedded Web Dashboard |
| `--no-firewall` | — | Skip automatic firewall port-opening (Windows/Linux) |
| `--list-ports` | — | Print ports that would be opened and exit |
| `--export-urls` | — | Generate `stream_urls.txt` at startup |

---

## ⚙️ Configuration

Streams are configured via `streams.csv`. If the file is missing, HydraCast generates a template on first run. You can edit it manually or use the built-in **Config tab** in the Web Dashboard — which provides a full form editor for every stream option including weekdays, compliance mode, folder source, bitrates, and more.

---

## 📄 License

Licensed under the [HydraCast Software License](https://github.com/rhshourav/HydraCast/blob/main/LICENSE).

---

<div align="center">

<img src="https://raw.githubusercontent.com/rhshourav/HydraCast/refs/heads/main/resources/HydraCast.svg" alt="HydraCast" width="20"/> **HydraCast** &nbsp;·&nbsp; made by [rhshourav](https://github.com/rhshourav)

</div>

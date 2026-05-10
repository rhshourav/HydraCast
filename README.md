# 🐉 HydraCast

![HydraCast Banner](https://via.placeholder.com/800x200?text=HydraCast+Banner)

**HydraCast** (v3.1.0) is a robust, lightweight Multi-Stream RTSP Weekly Scheduler. It allows you to broadcast multiple video and audio files as continuous 24/7 live RTSP and HLS streams. Built with Python, it manages FFmpeg processes and integrates seamlessly with MediaMTX, featuring both a rich Terminal UI (TUI) and a fully-featured Web Dashboard.

## ✨ Key Features
* **Multi-Stream Management**: Run multiple independent RTSP streams on custom ports.
* **HLS Support**: Easily enable HLS for web-compatible playback.
* **Smart Scheduling**: Schedule streams by specific weekdays or weekends.
* **Playlists & Seeking**: Support for multi-file playlists, looping, shuffling, and seamless seeking (via UI or timestamp offsets).
* **One-Shot Events**: Interrupt normal broadcasts to play a scheduled file at an exact time, with options to resume, stop, or show a black screen afterward.
* **Auto-Recovery**: Automatic FFmpeg process monitoring and restart on failure.
* **Dual Interfaces**: 
  * Beautiful CLI TUI using `rich`.
  * Comprehensive Web UI for remote management, log viewing, and media uploads.

## 🚀 Quick Start

### Prerequisites
* Python 3.8+
* `ffmpeg` and `ffprobe` installed and added to your system PATH (or placed in the `bin/` directory).
* *Note: HydraCast will automatically download the correct version of MediaMTX on its first run.*

### Installation
1. Clone the repository:
   ```bash
   git clone [https://github.com/rhshourav/HydraCast.git](https://github.com/rhshourav/HydraCast.git)
   cd HydraCast

```

2. Run the application (dependencies like `rich` and `psutil` will bootstrap automatically):
```bash
python hydracast.py

```



### Command-Line Arguments

* `--listen IP`: IP address for MediaMTX to bind on (default: `0.0.0.0`).
* `--web-port PORT`: Change the Web UI port (default: `8080`).
* `--no-web`: Disable the embedded Web UI.
* `--no-firewall`: Skip automatic firewall port-opening (Windows/Linux).
* `--list-ports`: Print ports that would be opened and exit.
* `--export-urls`: Generate a `stream_urls.txt` file at startup.

## 📖 Configuration

Streams are configured via `streams.csv`. If this file is missing, HydraCast will generate a template on startup. You can edit this file manually or use the built-in **Web UI Config Editor**.

## 📄 License

This project is licensed under the MIT License.

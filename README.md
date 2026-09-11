# YouTube Downloader — Vue + Flask + yt-dlp

A modern, responsive and self-hosted YouTube downloader with a **Vue.js frontend**, **Flask backend** and **yt-dlp** download engine. The interface is Persian (RTL), mobile-friendly and designed for fast local use.

## ✨ Features

### Download

- 🎬 Download YouTube videos in the selected quality
-  Download audio as MP3
-  Support for YouTube videos, Shorts and Playlists
-  Paste YouTube links directly from the Clipboard
-  Download video thumbnails
-  Fetch video title, thumbnail, uploader and duration before downloading
-  Dynamic quality detection
-  Best-quality download option
-  Automatic video/audio merging through FFmpeg

### Playlist

- Detect Playlist URLs
- Load playlist information and video thumbnails
- Select individual videos
- Select all / clear all
- Queue selected videos for download

### Download manager

- 📊 Real-time download progress
- ⚡ Download speed and ETA
- 📦 Downloaded/total size information
- ⏳ Queue and active download states
- ❌ Cancel running downloads
- 🔄 Retry failed downloads
- 🔌 Connection/retry status when the progress stream becomes stale
- Automatic server-side retry with exponential backoff
- Continued downloads when supported by yt-dlp
- Up to 2 concurrent downloads by default

### History & presets

- 🕘 Persistent download history using SQLite
- 🔍 Search downloaded items
- 🗑️ Delete individual history entries
- 🧹 Clear download history
- ⚡ Save reusable download presets
- One-click preset selection

### Settings & UI

- 🌙 Dark / light theme
- 📁 Configurable download directory
- 🚦 Configurable concurrent download count
- 🚀 Optional download speed limit
- 🔔 Download notification setting
- 📋 Clipboard monitor setting
- 🇮🇷 Persian RTL interface
- 📱 Responsive desktop, tablet and mobile layout
- 🎨 Modern glassmorphism-inspired UI
- Icons powered by Lucide Vue

### Network & error handling

The backend contains multiple recovery layers for unstable connections:

1. yt-dlp retries HTTP requests, fragments and extraction operations.
2. Flask applies application-level retries for common network/DNS/timeout failures.
3. Exponential backoff is used between retry attempts.
4. The Vue frontend continues polling the progress endpoint through short connection failures.
5. Stale download progress is reported as a reconnect/retry state instead of appearing frozen.
6. Common DNS, timeout, FFmpeg and unavailable-format errors are converted into readable Persian messages.

A persistent DNS problem cannot be fixed by the downloader itself. If `googlevideo.com` cannot be resolved, check the system's internet connection, DNS, VPN or Proxy configuration.

## 🧱 Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Vue 3 |
| Build tool | Vite |
| Icons | Lucide Vue Next |
| Backend | Python + Flask |
| Downloader engine | yt-dlp |
| Media processing | FFmpeg |
| Database | SQLite |
| UI direction | Persian / RTL |

## 📁 Project Structure

```text
youtube-downloader/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── downloader.db              # Created automatically at runtime
├── downloads/                 # Downloaded files
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── App.vue
│       ├── main.js
│       └── ...
└── static/
    └── font/
        ├── Vazir-Regular-FD.woff
        └── Vazir-Bold-FD.woff
```

`downloads/` and `downloader.db` are generated/used locally by the application.

## 💻 Requirements

- Python 3.10+
- Node.js 18+ recommended
- npm
- FFmpeg
- Internet connection

FFmpeg is required when the selected format needs separate video/audio streams to be merged and when extracting MP3 audio.

## 🚀 Installation

### 1. Clone the repository

```bash
git clone https://github.com/amirhosein126/youtube-downloader.git
cd youtube-downloader
```

### 2. Create the Python environment

#### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell blocks virtual-environment activation, run the environment's Python directly:

```powershell
.\.venv\Scripts\python.exe app.py
```

### 3. Install the Vue frontend dependencies

Open another terminal:

```bash
cd frontend
npm install
```

## ▶️ Development

You need to run the Flask backend and Vue development server.

### Terminal 1 — Flask

From the project root:

```bash
python app.py
```

Backend:

```text
http://127.0.0.1:5000
```

### Terminal 2 — Vue / Vite

From the `frontend` directory:

```bash
npm run dev
```

Vite runs on:

```text
http://127.0.0.1:5173
```

The Vite development server proxies `/api` requests to the Flask server at `http://127.0.0.1:5000`.

## 📦 Production Frontend Build

Build the Vue application with:

```bash
cd frontend
npm run build
```

The production files are generated in:

```text
frontend/dist/
```

The Flask application is configured to use this directory for the built frontend. For production deployment, use a proper WSGI server instead of Flask's development server.

## 🎞️ FFmpeg Setup

Make sure `ffmpeg` is installed and available in the system `PATH`.

Test it with:

```bash
ffmpeg -version
```

If the command is not recognized, downloads requiring video/audio merging or MP3 conversion may fail.

## 🔌 API Endpoints

The Flask backend exposes a JSON API used by the Vue frontend.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Backend, yt-dlp, FFmpeg and disk status |
| POST | `/api/info` | Get video information and available qualities |
| POST | `/api/playlist` | Read playlist entries |
| POST | `/api/download` | Start a video/audio download |
| GET | `/api/progress/<job_id>` | Get download progress |
| POST | `/api/cancel/<job_id>` | Cancel a download |
| POST | `/api/retry/<job_id>` | Retry a failed job |
| GET | `/api/file/<job_id>` | Download the completed file |
| POST | `/api/thumbnail` | Download the video thumbnail |
| GET | `/api/history` | Get download history |
| DELETE | `/api/history/<item_id>` | Delete one history item and its file |
| DELETE | `/api/history` | Clear history |
| GET | `/api/settings` | Read application settings |
| PUT | `/api/settings` | Update application settings |
| GET | `/api/presets` | Get saved presets |
| POST | `/api/presets` | Create a preset |
| DELETE | `/api/presets/<preset_id>` | Delete a preset |

## 🗃️ Local Database

The backend uses SQLite and creates `downloader.db` automatically.

The database stores:

- Download history
- Presets
- Application settings

No external database server is required.

## 🛠️ Troubleshooting

### FFmpeg is not found

Run:

```bash
ffmpeg -version
```

If it fails, install FFmpeg and add its `bin` directory to the system `PATH`.

### DNS / `googlevideo.com` errors

Check:

- Internet connection
- DNS configuration
- VPN / Proxy
- Firewall or network restrictions

The application already retries common DNS and network failures, but it cannot resolve a DNS problem that exists outside the application.

### Download progress appears stuck

The frontend polls `/api/progress/<job_id>` continuously. If the backend stops reporting progress for the configured stale interval, the job is shown as reconnecting/retrying instead of immediately being marked as failed.

### A selected quality is unavailable

YouTube formats can change between videos. Use **Best Quality** or choose another available resolution from the quality selector.

## 🧪 Development Commands

### Frontend

```bash
cd frontend
npm run dev
npm run build
npm run preview
```

### Backend

```bash
python app.py
```

## 🔒 Privacy

This project is designed for local/self-hosted use. Download history, settings and presets are stored in the local SQLite database, while downloaded files are stored in the configured local download directory.

## 📌 Notes

- The project is intended primarily for local and personal use.
- Do not use it to download content you do not have permission to copy or store.
- Flask's development server should not be exposed directly to the public internet in production.
- Generated downloads, the SQLite database, virtual environments and Python cache files should remain excluded from Git.

## 📄 License

See the repository license file for the project's current license information.

## 👨‍💻 Author

Developed by **amirhnfarahani**.

GitHub: https://github.com/amirhnfarahani/youtube-downloader

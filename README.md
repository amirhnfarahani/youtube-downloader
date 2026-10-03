# YouTube Downloader — Vue + Flask + yt-dlp

A modern, responsive and self-hosted YouTube downloader built with **Vue 3**, **Flask**, **yt-dlp**, **FFmpeg** and **SQLite**.

The application has a Persian **RTL** interface, responsive desktop/tablet/mobile layouts, playlist support, download management, persistent history, reusable presets and a dedicated **Windows desktop application** built with PyInstaller and pywebview.

## ✨ Features

### 🎬 Download

- Download YouTube videos in the selected quality
- ⭐ Best Quality mode
- 🎵 Extract audio as MP3
- 📺 Support for YouTube videos, Shorts and Playlists
- 📋 Paste YouTube links from the browser Clipboard or system Clipboard
- 🖼️ Download video thumbnails
- 🔎 Fetch title, thumbnail, uploader, duration and available formats before downloading
- 🎚️ Dynamic quality detection
- 🔀 Automatically merge separate video/audio streams with FFmpeg
- Continued downloads when supported by yt-dlp
- Bundled FFmpeg support in the Windows desktop build

### 📺 Playlist

- Detect YouTube Playlist URLs
- Load playlist information and thumbnails
- Select individual videos
- Select all / clear all
- Queue selected playlist items for download
- Process playlist downloads through the same download manager

### ⚡ Download Manager

- 📊 Real-time progress
- ⚡ Download speed
- ⏱️ ETA
- 📦 Downloaded and total size
- ⏳ Queue / active / completed / failed states
- ❌ Cancel active downloads
- 🔄 Retry failed downloads
- 🔌 Connection and retry status
- Automatic application-level retries
- Exponential backoff between retry attempts
- Stale-progress detection so an interrupted connection does not look permanently frozen
- Configurable concurrent download count
- Default concurrent download setting: **2**
- Backend executor supports up to **5** simultaneous workers

### 🕘 History

- Persistent SQLite download history
- Search history
- Delete individual history items
- Clear history
- Open a downloaded file directly
- Reveal a downloaded file in Windows Explorer
- Delete downloaded files through the history UI

### ⚡ Presets

Presets are reusable download profiles.

A preset currently stores:

- Media type: **Video** or **MP3 / Audio**
- Quality: **Best Quality**, 1080p, 720p, etc.

Example presets:

- `YouTube 1080p` → Video + 1080p
- `YouTube Best` → Video + Best Quality
- `MP3` → Audio

Preset actions:

- Create a preset from the current download settings
- Give the preset a custom name
- Apply a preset with one click
- Delete a preset

Applying a preset changes the download settings; it does **not** automatically start a download.

The desktop version uses an in-app preset dialog instead of relying on the browser `prompt()` dialog, making preset creation reliable inside pywebview.

### 🎨 UI & Settings

- 🌙 Dark / light theme
- 📁 Configurable download directory
- 🚦 Configurable concurrent downloads
- 🚀 Optional download speed limit
- 🔔 Download notifications setting
- 📋 Clipboard monitor setting
- 🇮🇷 Persian RTL interface
- 📱 Responsive desktop, tablet and mobile layout
- 🪟 Windows desktop application
- 🎨 Modern glassmorphism-inspired interface
- Lucide Vue icons
- Local Vazir Persian font support

### 🌐 Network & Error Recovery

The downloader uses multiple recovery layers for unstable YouTube connections.

1. yt-dlp retries HTTP requests, fragments and extraction operations.
2. The application retries common network, DNS and timeout failures.
3. Exponential backoff is used between retry attempts.
4. yt-dlp is installed with the `curl_cffi` extra for browser-style HTTP/TLS impersonation support.
5. Windows builds bundle `curl_cffi` and its PyInstaller resources.
6. The application first tries a Chrome/Windows impersonation profile and then falls back to IPv4/plain networking.
7. The frontend keeps polling download progress through short API failures.
8. Stale progress is displayed as a reconnect/retry state instead of immediately appearing frozen.
9. Common DNS, SSL, connection-reset, timeout, FFmpeg and unavailable-format errors are converted to readable Persian messages.

The project specifically handles errors such as:

- `SSL: UNEXPECTED_EOF_WHILE_READING`
- `SSLEOFError`
- Windows `WinError 10054`
- Connection reset / forcibly closed
- DNS resolution failures
- Network timeouts
- Missing FFmpeg
- Unavailable video formats

A network problem outside the application cannot always be repaired by software. If `googlevideo.com` cannot be resolved or your ISP/network blocks the connection, check the system's DNS, VPN, Proxy, firewall and internet connection.

yt-dlp supports browser impersonation through `curl_cffi`; available impersonation targets depend on the installed `curl_cffi` version. citeturn0search1turn0search2

## 🪟 Windows Desktop Application

The project can run as a standalone Windows application instead of requiring the user to open a browser and manually start Flask/Vite.

The Windows build contains:

- PyInstaller-generated `YouTubeDownloader.exe`
- pywebview desktop window
- Built Vue frontend
- Bundled FFmpeg
- Bundled Node.js runtime for yt-dlp JavaScript runtime support
- Bundled `curl_cffi`
- Bundled Windows application icon
- Local SQLite database
- Local `downloads` directory

### Available Windows packages

GitHub Actions produces:

| Package | Description |
|---|---|
| `YouTubeDownloader.exe` | Portable standalone executable |
| `YouTubeDownloader-Portable.zip` | Portable ZIP package |
| `YouTubeDownloader-Setup.exe` | Windows installer |

The installer uses a per-user installation directory under:

```text
%LOCALAPPDATA%\Programs\YouTube Downloader
```

Administrator privileges are not required by the installer.

The installer also creates:

- Start Menu shortcut
- Desktop shortcut
- Local downloads directory

### Running the portable EXE

Download `YouTubeDownloader.exe` and run it directly.

The desktop application uses the bundled frontend and media-processing resources, so a separate Node.js or FFmpeg installation is not required for the packaged application.

## 🧱 Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Vue 3 |
| Build tool | Vite |
| Icons | Lucide Vue Next |
| Desktop shell | pywebview |
| Backend | Python + Flask |
| Downloader engine | yt-dlp |
| HTTP/TLS fallback | curl_cffi |
| Media processing | FFmpeg |
| JavaScript runtime for yt-dlp | Node.js |
| Database | SQLite |
| Clipboard | pyperclip |
| Windows packaging | PyInstaller + Inno Setup |
| UI direction | Persian / RTL |

## 📁 Project Structure

```text
youtube-downloader/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── downloader.db                 # Created automatically at runtime
├── downloads/                    # Downloaded files
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   ├── dist/                     # Production frontend build
│   └── src/
│       ├── App.vue
│       ├── main.js
│       └── ...
├── static/
│   └── font/
│       ├── Vazir-Regular-FD.woff
│       └── Vazir-Bold-FD.woff
└── build/
    └── windows/
        ├── YouTubeDownloader.spec
        ├── installer.iss
        ├── create_icon.py
        ├── ffmpeg.exe            # Generated/downloaded during Windows build
        ├── node.exe              # Generated/downloaded during Windows build
        └── youtube-purple.ico
```

Runtime-generated files such as `downloads/` and `downloader.db` are local application data and should not be committed.

## 💻 Requirements

### Development

- Windows 10/11, Linux or macOS
- Python 3.10+
- Node.js 18+
- npm
- FFmpeg
- Internet connection

The current Windows release workflow uses:

- Python 3.12
- Node.js 22 for the frontend build
- Node.js 20 runtime bundled into the desktop application

### Windows packaged application

For the packaged Windows application, users do **not** need to install Python, Node.js or FFmpeg separately. These runtime components are bundled by the Windows build process.

## 🚀 Installation — Development

### 1. Clone the repository

```bash
git clone https://github.com/amirhnfarahani/youtube-downloader.git
cd youtube-downloader
```

### 2. Create the Python environment

#### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell blocks virtual-environment activation:

```powershell
.\.venv\Scripts\python.exe app.py
```

### 3. Install frontend dependencies

Open another terminal:

```bash
cd frontend
npm install
```

The Python requirements include:

```text
Flask
yt-dlp[default,curl-cffi]
pywebview
pyperclip
```

The `curl_cffi` dependency is important for the application's network/impersonation fallback. yt-dlp documents `curl_cffi` as the handler used for browser impersonation. citeturn0search1turn0search2

## ▶️ Development

Run the Flask backend and Vue development server separately.

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

Vite:

```text
http://127.0.0.1:5173
```

The Vite development server proxies `/api` requests to Flask at `http://127.0.0.1:5000`.

## 📦 Production Frontend Build

```bash
cd frontend
npm run build
```

The production files are generated in:

```text
frontend/dist/
```

Flask serves the production frontend from this directory.

## 🪟 Build the Windows Application

The repository contains a GitHub Actions workflow at:

```text
.github/workflows/build-windows.yml
```

Every push to `main` can trigger the Windows build workflow, and it can also be started manually from GitHub Actions.

The workflow:

1. Checks out the repository.
2. Installs Python 3.12.
3. Installs Node.js 22.
4. Builds the Vue frontend.
5. Installs Python dependencies.
6. Downloads FFmpeg.
7. Downloads a Node.js runtime for the packaged application.
8. Generates the Windows icon.
9. Builds `YouTubeDownloader.exe` with PyInstaller.
10. Builds the installer with Inno Setup.
11. Creates a portable ZIP.
12. Uploads the three Windows packages as GitHub Actions artifacts.
13. Creates/updates the Windows GitHub release.

### Manual local Windows build

Install the build dependencies:

```powershell
python -m pip install -r requirements.txt
python -m pip install pyinstaller pillow
```

Build the frontend:

```powershell
cd frontend
npm install
npm run build
cd ..
```

The PyInstaller specification is:

```text
build/windows/YouTubeDownloader.spec
```

The installer definition is:

```text
build/windows/installer.iss
```

The automated workflow is recommended because it downloads the required FFmpeg and Node.js runtime files and performs the complete packaging process.

## 🎞️ FFmpeg

FFmpeg is required for:

- Merging separate video/audio streams
- MP3 extraction
- Some post-processing operations

For development, test:

```bash
ffmpeg -version
```

For the packaged Windows application, FFmpeg is bundled into the executable build.

## 🔌 API Endpoints

The Flask backend exposes the JSON API used by the Vue frontend.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Backend, yt-dlp, FFmpeg, Node and disk status |
| GET | `/api/clipboard` | Read text from the system Clipboard |
| POST | `/api/info` | Fetch video information and available qualities |
| POST | `/api/playlist` | Read playlist entries |
| POST | `/api/download` | Start a video/audio download |
| GET | `/api/progress/<job_id>` | Get download progress |
| POST | `/api/cancel/<job_id>` | Cancel a download |
| POST | `/api/retry/<job_id>` | Retry a failed job |
| GET | `/api/file/<job_id>` | Serve/download a completed file |
| POST | `/api/open/<job_id>` | Open the downloaded file with the OS |
| POST | `/api/reveal/<job_id>` | Reveal the downloaded file in the file manager |
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

The application uses SQLite and automatically creates:

```text
downloader.db
```

The database stores:

- Download history
- Presets
- Application settings

Default settings include:

- Download directory
- Theme
- Language
- Concurrent download count
- Speed limit
- Notifications
- Clipboard monitor

No external database server is required.

## 🛠️ Troubleshooting

### SSL / `UNEXPECTED_EOF_WHILE_READING`

If you see:

```text
SSL: UNEXPECTED_EOF_WHILE_READING
```

the application treats it as a network/SSL failure and attempts alternative connection profiles and retries.

Also check:

- Internet connection
- DNS
- VPN
- Proxy
- Firewall
- Antivirus HTTPS inspection
- ISP/network restrictions

The project includes `curl_cffi` support because yt-dlp uses it for browser impersonation targets. The exact targets available depend on the installed `curl_cffi` version. citeturn0search1

### Windows `WinError 10054`

This means the connection was forcibly closed/reset.

The application retries the download and attempts its alternative networking profiles. If the error persists, check the network path, VPN/Proxy and firewall.

### DNS / `googlevideo.com` errors

Check:

- Internet connection
- DNS configuration
- VPN / Proxy
- Firewall
- Network restrictions

The downloader cannot repair a DNS server or network route that is unavailable outside the application.

### `curl_cffi` / impersonation unavailable

If yt-dlp reports that Chrome or another impersonation target is unavailable, verify that `curl_cffi` was installed in the same Python environment as yt-dlp.

You can inspect available targets with:

```bash
yt-dlp --list-impersonate-targets
```

yt-dlp documents the `--list-impersonate-targets` and `--impersonate` options for checking and selecting available targets. citeturn0search2

### FFmpeg is not found

Run:

```bash
ffmpeg -version
```

For development, install FFmpeg and add its `bin` directory to the system `PATH`.

For the packaged Windows application, FFmpeg is bundled during the official Windows build.

### Download progress appears stuck

The frontend continuously polls:

```text
/api/progress/<job_id>
```

If progress becomes stale, the application reports a reconnect/retry state instead of immediately treating the job as permanently failed.

### Selected quality is unavailable

YouTube formats can vary between videos.

Try:

- Best Quality
- Another available resolution
- Audio mode if only audio is required

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

The project is designed for local/self-hosted use.

- Download history is stored in the local SQLite database.
- Presets and settings are stored locally.
- Downloaded files remain in the configured local download directory.
- The application does not require a remote application database.

## 📌 Notes

- The project is primarily intended for local and personal use.
- Only download content you have permission to copy or store.
- Do not expose Flask's development server directly to the public internet.
- Keep generated downloads, `downloader.db`, virtual environments and Python cache files out of Git.
- Network behavior can still depend on the user's ISP, DNS, VPN, Proxy and firewall.
- YouTube and yt-dlp behavior can change over time as YouTube changes its delivery systems.

## 📄 License

See the repository license file for the project's current license information.

## 👨‍💻 Author

Developed by **amirhnfarahani**.

GitHub: https://github.com/amirhnfarahani

Repository: https://github.com/amirhnfarahani/youtube-downloader

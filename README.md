# YouTube Downloader — Flask + yt-dlp

A lightweight RTL Persian YouTube downloader built with **Flask**, **yt-dlp**, HTML/CSS and vanilla JavaScript.

## Features

- Responsive UI for desktop, tablet and mobile
- Fetch video title and thumbnail before downloading
- Detect available video qualities dynamically
- Download video or MP3
- Luxury glassmorphism download progress panel
- Real-time percentage, downloaded size, speed and ETA
- Automatic retry for common network/DNS/timeout failures
- Server-side retry + yt-dlp internal retries
- Front-end polling recovery when the browser temporarily loses connection to Flask
- Friendly Persian error messages for common DNS/network/FFmpeg problems
- Automatic final file download after completion

## Project structure

```text
downloader/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── templates/
│   └── index.html
├── static/
│   └── font/
│       ├── Vazir-Regular-FD.woff
│       └── Vazir-Bold-FD.woff
└── downloads/
```

`downloads/` is created automatically when the application starts.

## Requirements

- Python 3.10+ recommended
- FFmpeg is required for formats that need video/audio merging and for MP3 extraction
- A working internet connection

## Installation

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

### If PowerShell blocks activation

You can run the environment's Python directly:

```powershell
.\.venv\Scripts\python.exe app.py
```

## FFmpeg

Install FFmpeg and make sure `ffmpeg` is available in your system `PATH`.

Test it with:

```powershell
ffmpeg -version
```

If `ffmpeg` is not found, downloads that require merging separate video/audio streams or MP3 extraction may fail.

## Network/DNS retry behavior

The downloader uses multiple layers of recovery:

1. **yt-dlp retries** for HTTP, fragments and extractor operations.
2. **Application-level retries** for common network/DNS/timeout failures.
3. **Exponential backoff** between application-level attempts.
4. The browser keeps polling the progress endpoint through short connection failures instead of immediately marking the download as failed.
5. If the backend has not reported a progress hook for a while, the UI displays a reconnect/retry state instead of looking frozen.

A persistent DNS failure cannot be solved purely in code. If the machine cannot resolve `googlevideo.com`, check your internet connection, DNS settings and VPN/Proxy configuration.

## GitHub

Before pushing the project, make sure generated downloads, virtual environments and Python cache files are ignored by Git. The included `.gitignore` handles these common files.

```bash
git init
git add .
git commit -m "Initial responsive YouTube downloader"
git branch -M main
git remote add origin YOUR_GITHUB_REPOSITORY_URL
git push -u origin main
```

## Notes

- This project is intended for local/personal use.
- Respect YouTube's terms, copyright rules and the rights of content owners when downloading content.
- `debug=True` is enabled for local development. Use a production WSGI server for deployment.

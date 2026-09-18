from flask import Flask, jsonify, request, send_file, send_from_directory
import glob
import json
import os
import re
import shutil
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
import urllib.request
import yt_dlp
from flask import Flask, jsonify, request, send_file, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_FOLDER = os.path.join(BASE_DIR, 'downloads')
FRONTEND_DIST = os.path.join(BASE_DIR, 'frontend', 'dist')
STATIC_FOLDER = os.path.join(BASE_DIR, 'static')
DB_PATH = os.path.join(BASE_DIR, 'downloader.db')
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
app = Flask(__name__, static_folder=None)
MAX_RETRIES, STALE_SECONDS, MAX_WORKERS = 5, 12, 5
JOBS, JOBS_LOCK, CANCEL_EVENTS = {}, threading.RLock(), {}
EXECUTOR = ThreadPoolExecutor(max_workers=MAX_WORKERS)
DOWNLOAD_CONDITION = threading.Condition(JOBS_LOCK)
ACTIVE_DOWNLOADS = 0
FILE_NAME_LOCK = threading.Lock()


def db():
    c = sqlite3.connect(DB_PATH); c.row_factory = sqlite3.Row; return c


def init_db():
    c = db()
    c.executescript('''CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,url TEXT NOT NULL,filename TEXT,path TEXT,status TEXT NOT NULL,media_type TEXT DEFAULT 'video',quality TEXT,size INTEGER DEFAULT 0,created_at REAL NOT NULL);CREATE TABLE IF NOT EXISTS presets(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,settings TEXT NOT NULL,created_at REAL NOT NULL);CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);''')
    defaults={'download_path':DOWNLOAD_FOLDER,'theme':'dark','language':'fa','concurrent_downloads':'2','speed_limit':'0','notifications':'true','clipboard_monitor':'false'}
    for k,v in defaults.items(): c.execute('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)',(k,v))
    c.commit(); c.close()


def set_job(job_id, **values):
    with JOBS_LOCK:
        job=JOBS.setdefault(job_id,{}); job.update(values); job['updated_at']=time.time()


def get_job(job_id):
    with JOBS_LOCK: return dict(JOBS.get(job_id,{}))


def format_bytes(value):
    if not value:return '0 B'
    n=float(value)
    for unit in ['B','KB','MB','GB','TB']:
        if n<1024 or unit=='TB': return f'{n:.1f} {unit}' if unit!='B' else f'{int(n)} B'
        n/=1024


def format_eta(seconds):
    if seconds is None:return '—'
    s=max(0,int(seconds)); return f'{s//60}:{s%60:02d}'


def human_error(error):
    text=str(error or '').strip(); low=text.lower()
    if any(x in low for x in ('failed to resolve','getaddrinfo failed','name or service not known','dns')): return 'اتصال DNS برقرار نشد. اینترنت، DNS یا VPN/Proxy را بررسی کنید.'
    if any(x in low for x in ('timed out','timeout','connection reset','connection aborted','network is unreachable')): return 'ارتباط با سرور ناپایدار شد. برنامه تلاش مجدد خودکار انجام می‌دهد.'
    if 'ffmpeg' in low and ('not found' in low or 'not installed' in low): return 'FFmpeg نصب نیست و برای تبدیل یا ادغام صدا و تصویر لازم است.'
    if 'requested format is not available' in low: return 'کیفیت انتخاب‌شده در دسترس نیست. کیفیت دیگری را امتحان کنید.'
    return re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',text) or 'دانلود با خطای ناشناخته مواجه شد.'


def info_options(): return {'quiet':True,'no_warnings':True,'skip_download':True,'retries':MAX_RETRIES,'extractor_retries':3,'socket_timeout':20}


def extract(url,playlist=False):
    opts=info_options(); opts['noplaylist']=not playlist
    with yt_dlp.YoutubeDL(opts) as ydl:return ydl.extract_info(url,download=False)


def clean_title(title):
    title=re.sub(r'[\\/:*?"<>|]','_',title or 'video'); return re.sub(r'\s+',' ',title).strip(' .')[:180] or 'video'


def get_settings():
    c=db(); rows=c.execute('SELECT key,value FROM settings').fetchall(); c.close(); r={x['key']:x['value'] for x in rows}
    r['concurrent_downloads']=int(r.get('concurrent_downloads',2)); r['speed_limit']=int(r.get('speed_limit',0)); r['notifications']=r.get('notifications')=='true'; r['clipboard_monitor']=r.get('clipboard_monitor')=='true'; return r


@app.get('/api/health')
def health(): return jsonify(success=True,yt_dlp=getattr(yt_dlp,'version','unknown'),ffmpeg=bool(shutil.which('ffmpeg')),disk_free=shutil.disk_usage(BASE_DIR).free)


@app.post('/api/info')
def api_info():
    url=str((request.get_json(silent=True) or {}).get('url','')).strip()
    if not url:return jsonify(success=False,error='لینک را وارد کنید.'),400
    try:
        is_playlist=bool(re.search(r'[?&](list|playlist)=',url,re.I) or '/playlist' in url.lower())
        info=extract(url,playlist=is_playlist)
        formats=info.get('formats') or []
        heights=sorted({int(f['height']) for f in formats if f.get('height') and f.get('vcodec')!='none'},reverse=True)
        return jsonify(success=True,kind='playlist' if info.get('_type')=='playlist' else 'video',title=info.get('title'),thumbnail=info.get('thumbnail'),duration=info.get('duration'),uploader=info.get('uploader'),webpage_url=info.get('webpage_url',url),qualities=[{'value':str(h),'resolution':f'{h}p','label':'4K' if h>=2160 else '2K' if h>=1440 else 'Full HD' if h>=1080 else 'HD' if h>=720 else 'SD'} for h in heights])
    except Exception as e:return jsonify(success=False,error=human_error(e)),500


@app.post('/api/playlist')
def api_playlist():
    url=str((request.get_json(silent=True) or {}).get('url','')).strip()
    if not url:return jsonify(success=False,error='لینک Playlist را وارد کنید.'),400
    try:
        info=extract(url,playlist=True); entries=[]
        for i,item in enumerate(info.get('entries') or [],1):
            if item: entries.append({'index':i,'id':item.get('id'),'title':item.get('title'),'thumbnail':item.get('thumbnail'),'duration':item.get('duration'),'url':item.get('webpage_url') or item.get('original_url')})
        return jsonify(success=True,title=info.get('title') or 'Playlist',uploader=info.get('uploader'),count=len(entries),entries=entries)
    except Exception as e:return jsonify(success=False,error=human_error(e)),500


def download_options(job_id,url,quality,media_type):
    s=get_settings(); folder=s['download_path'] or DOWNLOAD_FOLDER; os.makedirs(folder,exist_ok=True); outtmpl=os.path.join(folder,f'{job_id}.%(ext)s')
    if media_type=='audio': fmt='bestaudio/best'
    elif quality=='best': fmt='bestvideo*+bestaudio/best'
    else:
        try:
            h=max(144,int(quality))
        except (TypeError,ValueError):
            h=1080
        fmt=f'bestvideo[height<={h}]+bestaudio/best[height<={h}]/best[height<={h}]/best'
    def hook(d):
        if CANCEL_EVENTS[job_id].is_set(): raise RuntimeError('DOWNLOAD_CANCELLED')
        if d.get('status')=='downloading':
            done=d.get('downloaded_bytes') or 0; total=d.get('total_bytes') or d.get('total_bytes_estimate') or 0; percent=round(min(99,done*100/total),1) if total else 0
            set_job(job_id,status='downloading',percent=percent,downloaded=format_bytes(done),total=format_bytes(total),speed=format_bytes(d.get('speed') or 0)+'/s' if d.get('speed') else '—',eta=format_eta(d.get('eta')),message='در حال دانلود...',last_progress_at=time.time(),connection_state='connected')
        elif d.get('status')=='finished': set_job(job_id,status='processing',percent=99,message='در حال پردازش فایل...',connection_state='processing')
    opts={'format':fmt,'outtmpl':outtmpl,'merge_output_format':'mp4','noplaylist':True,'quiet':True,'no_warnings':True,'progress_hooks':[hook],'retries':MAX_RETRIES,'fragment_retries':MAX_RETRIES,'extractor_retries':3,'file_access_retries':3,'socket_timeout':20,'continuedl':True}
    if s['speed_limit']: opts['ratelimit']=s['speed_limit']*1024
    if media_type=='audio': opts['postprocessors']=[{'key':'FFmpegExtractAudio','preferredcodec':'mp3','preferredquality':'320'},{'key':'EmbedThumbnail'},{'key':'FFmpegMetadata'}]; opts['writethumbnail']=True
    return opts,folder


def acquire_download_slot(job_id):
    global ACTIVE_DOWNLOADS
    while True:
        with DOWNLOAD_CONDITION:
            if CANCEL_EVENTS.get(job_id) and CANCEL_EVENTS[job_id].is_set(): return False
            limit=max(1,min(5,int(get_settings().get('concurrent_downloads',2))))
            if ACTIVE_DOWNLOADS < limit:
                ACTIVE_DOWNLOADS += 1
                return True
            set_job(job_id,status='queued',message=f'در صف دانلود؛ ظرفیت همزمان {limit} است...')
            DOWNLOAD_CONDITION.wait(timeout=1)

def release_download_slot():
    global ACTIVE_DOWNLOADS
    with DOWNLOAD_CONDITION:
        ACTIVE_DOWNLOADS=max(0,ACTIVE_DOWNLOADS-1)
        DOWNLOAD_CONDITION.notify_all()

def cleanup_job_files(folder,job_id):
    for p in glob.glob(os.path.join(folder,f'{job_id}.*')):
        try:
            if os.path.isfile(p): os.remove(p)
        except OSError: pass

def run_download(job_id,url,quality,media_type='video'):
    event=CANCEL_EVENTS[job_id]; last_error=None
    for attempt in range(1,MAX_RETRIES+1):
        slot_acquired=False
        if event.is_set(): set_job(job_id,status='cancelled',message='دانلود لغو شد.',connection_state='cancelled'); return
        try:
            if not acquire_download_slot(job_id):
                set_job(job_id,status='cancelled',message='دانلود لغو شد.',connection_state='cancelled')
                return
            slot_acquired=True
            set_job(job_id,status='starting',retry_count=attempt-1,message='در حال اتصال به YouTube...',connection_state='connecting')
            info=extract(url); title=info.get('title') or 'video'; opts,folder=download_options(job_id,url,quality,media_type)
            with yt_dlp.YoutubeDL(opts) as ydl: ydl.extract_info(url,download=True)
            files=[f for f in glob.glob(os.path.join(folder,job_id+'.*')) if not f.endswith('.part')]
            if not files: raise RuntimeError('فایل خروجی پیدا نشد')
            source=max(files,key=os.path.getmtime); ext=os.path.splitext(source)[1] or ('.mp3' if media_type=='audio' else '.mp4')
            base=clean_title(title)
            with FILE_NAME_LOCK:
                filename=base+ext
                destination=os.path.join(folder,filename)
                counter=1
                while os.path.exists(destination):
                    filename=f'{base}_{counter}{ext}'
                    destination=os.path.join(folder,filename)
                    counter+=1
                os.replace(source,destination)
            size=os.path.getsize(destination)
            c=db(); c.execute('INSERT INTO history(title,url,filename,path,status,media_type,quality,size,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(title,url,os.path.basename(destination),destination,'completed',media_type,quality,size,time.time())); c.commit(); c.close()
            set_job(job_id,status='completed',percent=100,downloaded=format_bytes(size),total=format_bytes(size),speed='—',eta='—',message='دانلود با موفقیت انجام شد.',filename=os.path.basename(destination),file_path=destination,connection_state='completed'); return
        except Exception as e:
            last_error=e
            if event.is_set() or str(e)=='DOWNLOAD_CANCELLED':
                cleanup_job_files(get_settings().get('download_path') or DOWNLOAD_FOLDER,job_id)
                set_job(job_id,status='cancelled',message='دانلود لغو شد.',connection_state='cancelled')
                return
            if attempt<MAX_RETRIES:
                wait=min(10,2**(attempt-1))
                set_job(job_id,status='retrying',retry_count=attempt,message=f'خطا؛ تلاش مجدد در {wait} ثانیه...',error=human_error(e),retrying=True,connection_state='retrying')
                time.sleep(wait)
            else: break
        finally:
            if slot_acquired: release_download_slot()
    cleanup_job_files(get_settings().get('download_path') or DOWNLOAD_FOLDER,job_id)
    set_job(job_id,status='error',message='دانلود ناموفق بود.',error=human_error(last_error),connection_state='failed')


@app.post('/api/download')
def api_download():
    d=request.get_json(silent=True) or {}; url=str(d.get('url','')).strip(); quality=str(d.get('quality','best')); media_type=str(d.get('media_type','video'))
    if not url:return jsonify(success=False,error='لینک وارد نشده است.'),400
    job_id=str(uuid.uuid4()); JOBS[job_id]={'id':job_id,'url':url,'quality':quality,'media_type':media_type,'status':'queued','percent':0,'message':'در صف دانلود...','retry_count':0,'created_at':time.time()}; CANCEL_EVENTS[job_id]=threading.Event(); EXECUTOR.submit(run_download,job_id,url,quality,media_type); return jsonify(success=True,job_id=job_id)


@app.get('/api/progress/<job_id>')
def api_progress(job_id):
    job=get_job(job_id)
    if not job:return jsonify(success=False,error='دانلود پیدا نشد.'),404
    if job.get('status')=='downloading' and time.time()-job.get('last_progress_at',job.get('updated_at',time.time()))>STALE_SECONDS: job['connection_state']='retrying'; job['message']='اتصال ناپایدار است؛ در حال تلاش مجدد...'
    return jsonify(success=True,**job)


@app.post('/api/cancel/<job_id>')
def api_cancel(job_id):
    if job_id not in CANCEL_EVENTS:return jsonify(success=False,error='دانلود پیدا نشد.'),404
    CANCEL_EVENTS[job_id].set(); set_job(job_id,status='cancelling',message='در حال لغو دانلود...',connection_state='cancelling'); return jsonify(success=True)


@app.post('/api/retry/<job_id>')
def api_retry(job_id):
    j=get_job(job_id)
    if not j:return jsonify(success=False,error='دانلود پیدا نشد.'),404
    new=str(uuid.uuid4()); JOBS[new]={'id':new,'url':j.get('url'),'quality':j.get('quality','best'),'media_type':j.get('media_type','video'),'status':'queued','percent':0,'message':'در صف دانلود...','created_at':time.time()}; CANCEL_EVENTS[new]=threading.Event(); EXECUTOR.submit(run_download,new,new and j['url'],j.get('quality','best'),j.get('media_type','video')); return jsonify(success=True,job_id:new)


@app.get('/api/file/<job_id>')
def api_file(job_id):
    j=get_job(job_id); p=j.get('file_path'); filename=j.get('filename')
    if not p and str(job_id).isdigit():
        c=db(); row=c.execute('SELECT path,filename FROM history WHERE id=?',(int(job_id),)).fetchone(); c.close()
        if row: p,filename=row['path'],row['filename']
    if not p or not os.path.isfile(p): return jsonify(success=False,error='فایل پیدا نشد یا حذف شده است.'),404
    return send_file(p,as_attachment=True,download_name=filename or os.path.basename(p))


@app.post('/api/thumbnail')
def api_thumbnail():
    url=str((request.get_json(silent=True) or {}).get('url','')).strip()
    try:
        info=extract(url); thumb=info.get('thumbnail')
        if not thumb:raise RuntimeError('Thumbnail پیدا نشد')
        name=clean_title(info.get('title'))+'_thumbnail.jpg'; path=os.path.join(DOWNLOAD_FOLDER,name)
        with urllib.request.urlopen(thumb,timeout=20) as response, open(path,'wb') as out: shutil.copyfileobj(response,out)
        return send_file(path,as_attachment=True,download_name=name)
    except Exception as e:return jsonify(success=False,error=human_error(e)),500


@app.get('/api/history')
def api_history():
    limit=min(int(request.args.get('limit',100)),500); c=db(); rows=c.execute('SELECT * FROM history ORDER BY created_at DESC LIMIT ?',(limit,)).fetchall(); c.close(); return jsonify(success=True,items=[dict(r) for r in rows])

@app.delete('/api/history/<int:item_id>')
def api_delete_history(item_id):
    c=db(); row=c.execute('SELECT path FROM history WHERE id=?',(item_id,)).fetchone()
    if row and row['path'] and os.path.isfile(row['path']):
        try:os.remove(row['path'])
        except OSError:pass
    c.execute('DELETE FROM history WHERE id=?',(item_id,)); c.commit(); c.close(); return jsonify(success=True)

@app.delete('/api/history')
def api_clear_history():
    c=db(); c.execute('DELETE FROM history'); c.commit(); c.close(); return jsonify(success=True)

@app.get('/api/settings')
def api_get_settings():return jsonify(success=True,settings=get_settings())

@app.put('/api/settings')
def api_put_settings():
    d=request.get_json(silent=True) or {}
    allowed={'download_path','theme','language','concurrent_downloads','speed_limit','notifications','clipboard_monitor'}
    if 'concurrent_downloads' in d:
        try: d['concurrent_downloads']=max(1,min(5,int(d['concurrent_downloads'])))
        except (TypeError,ValueError): d.pop('concurrent_downloads',None)
    if 'speed_limit' in d:
        try: d['speed_limit']=max(0,int(d['speed_limit']))
        except (TypeError,ValueError): d.pop('speed_limit',None)
    c=db()
    for k,v in d.items():
        if k in allowed:
            if isinstance(v,bool):v='true' if v else 'false'
            c.execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)',(k,str(v)))
    c.commit(); c.close(); return jsonify(success=True,settings=get_settings())

@app.get('/api/presets')
def api_presets():
    c=db(); rows=c.execute('SELECT * FROM presets ORDER BY created_at DESC').fetchall(); c.close(); return jsonify(success=True,items=[{**dict(r),'settings':json.loads(r['settings'])} for r in rows])

@app.post('/api/presets')
def api_create_preset():
    d=request.get_json(silent=True) or {}; name=str(d.get('name','Preset')).strip() or 'Preset'; c=db(); cur=c.execute('INSERT INTO presets(name,settings,created_at) VALUES(?,?,?)',(name,json.dumps(d.get('settings') or {},ensure_ascii=False),time.time())); c.commit(); pid=cur.lastrowid; c.close(); return jsonify(success=True,id=pid)

@app.delete('/api/presets/<int:preset_id>')
def api_delete_preset(preset_id):
    c=db(); c.execute('DELETE FROM presets WHERE id=?',(preset_id,)); c.commit(); c.close(); return jsonify(success=True)

@app.get('/api/jobs')
def api_jobs():
    with JOBS_LOCK:return jsonify(success=True,items=list(JOBS.values()))

@app.get('/font/<path:name>')
def font(name):return send_from_directory(os.path.join(STATIC_FOLDER,'font'),name)

@app.route('/',defaults={'path':''})
@app.route('/<path:path>')
def frontend(path):
    if os.path.isdir(FRONTEND_DIST):
        requested=os.path.join(FRONTEND_DIST,path)
        if path and os.path.isfile(requested):return send_from_directory(FRONTEND_DIST,path)
        return send_from_directory(FRONTEND_DIST,'index.html')
    return jsonify(success=True,message='Vue frontend is not built. Run: cd frontend && npm install && npm run build')

init_db()
if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.environ.get('PORT','5000')),debug=False)

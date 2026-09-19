<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Download, History, Settings, ListVideo, Sun, Moon, Clipboard, X, RotateCcw, FolderOpen, Trash2, Play, Pause, Search, Plus, Zap, Music2, Video, Image, CheckCircle2, AlertCircle } from 'lucide-vue-next'

const API = '/api'
const url = ref('')
const active = ref('download')
const loading = ref(false)
const error = ref('')
const info = ref(null)
const qualities = ref([])
const selectedQuality = ref('best')
const mediaType = ref('video')
const jobs = ref([])
const history = ref([])
const playlist = ref(null)
const selectedItems = ref([])
const presets = ref([])
const settings = ref({ theme:'dark', download_path:'downloads', concurrent_downloads:2, speed_limit:0, notifications:true, clipboard_monitor:false })
const search = ref('')
const isDark = ref(true)
let timer

const visibleHistory = computed(() => history.value.filter(x => (x.title || '').toLowerCase().includes(search.value.toLowerCase())))
const runningJobs = computed(() => jobs.value.filter(x => !['completed','error','cancelled'].includes(x.status)))

async function api(path, options={}) {
  const res = await fetch(API + path, { headers:{'Content-Type':'application/json'}, ...options })
  const data = await res.json().catch(() => ({}))
  if (!res.ok || data.success === false) throw new Error(data.error || 'خطای سرور')
  return data
}

async function inspect() {
  if (!url.value.trim()) return
  loading.value = true; error.value = ''; info.value = null; playlist.value = null
  try {
    const data = await api('/info', {method:'POST', body:JSON.stringify({url:url.value})})
    info.value = data; qualities.value = data.qualities || []
    if (data.kind === 'playlist') await inspectPlaylist()
  } catch(e) { error.value = e.message }
  finally { loading.value = false }
}

async function inspectPlaylist() {
  try { playlist.value = await api('/playlist', {method:'POST', body:JSON.stringify({url:url.value})}); selectedItems.value = playlist.value.entries.map(x => x.index) }
  catch(e) { error.value = e.message }
}

async function startDownload(itemUrl=url.value, quality=selectedQuality.value, type=mediaType.value) {
  if (!itemUrl) return
  try {
    const data = await api('/download', {method:'POST', body:JSON.stringify({url:itemUrl, quality, media_type:type})})
    jobs.value.unshift({id:data.job_id,status:'queued',percent:0,message:'در صف دانلود...'})
    active.value='download'; startPolling()
  } catch(e) { error.value=e.message }
}

async function downloadPlaylist() {
  if (!playlist.value) return
  for (const item of playlist.value.entries.filter(x=>selectedItems.value.includes(x.index))) await startDownload(item.url)
}

async function downloadThumbnail() {
  try {
    const res = await fetch(API+'/thumbnail',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:url.value})})
    if (!res.ok) throw new Error((await res.json()).error || 'خطا')
    const blob=await res.blob(); const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download='thumbnail.jpg'; a.click(); URL.revokeObjectURL(a.href)
  } catch(e){error.value=e.message}
}

async function poll() {
  if (!runningJobs.value.length) return
  jobs.value = await Promise.all(jobs.value.map(async j => {
    if (['completed','error','cancelled'].includes(j.status)) return j
    try { return (await api('/progress/'+j.id)) }
    catch { return j }
  }))
  if (runningJobs.value.length) timer=setTimeout(poll,800)
}
function startPolling(){clearTimeout(timer); poll()}
async function cancel(id){ await api('/cancel/'+id,{method:'POST'}); startPolling() }
async function retry(j){ if(j.url) await startDownload(j.url,j.quality,j.media_type) }
async function loadHistory(){ history.value=(await api('/history')).items }
async function loadPresets(){ presets.value=(await api('/presets')).items }
async function clearHistory(){ await api('/history',{method:'DELETE'}); await loadHistory() }
async function deleteHistory(id){ await api('/history/'+id,{method:'DELETE'}); await loadHistory() }
async function saveSettings(){ await api('/settings',{method:'PUT',body:JSON.stringify(settings.value)}) }
async function savePreset(){ const name=prompt('نام Preset را وارد کنید'); if(!name)return; await api('/presets',{method:'POST',body:JSON.stringify({name,settings:{quality:selectedQuality.value,mediaType:mediaType.value}})}); await loadPresets() }
async function usePreset(p){ selectedQuality.value=p.settings.quality||'best'; mediaType.value=p.settings.mediaType||'video' }
async function pasteFromClipboard(){
  error.value = ''
  try {
    if (!navigator.clipboard || !window.isSecureContext) {
      throw new Error('دسترسی مستقیم به Clipboard در این آدرس فعال نیست. داخل کادر کلیک کنید و Ctrl+V بزنید.')
    }
    const text = (await navigator.clipboard.readText()).trim()
    if (!text) {
      error.value = 'Clipboard خالی است.'
      return
    }
    url.value = text
    if (/youtube\.com|youtu\.be/i.test(text)) {
      await inspect()
    } else {
      error.value = 'متن Clipboard یک لینک YouTube معتبر نیست.'
    }
  } catch (e) {
    error.value = e?.message || 'دسترسی به Clipboard توسط مرورگر مسدود شده است. داخل کادر کلیک کنید و Ctrl+V بزنید.'
  }
}

async function handlePaste(event){
  const text = event.clipboardData?.getData('text')?.trim() || ''
  if (!text) return
  url.value = text
  if (/youtube\.com|youtu\.be/i.test(text)) {
    await inspect()
  }
}
function toggleTheme(){isDark.value=!isDark.value; document.documentElement.dataset.theme=isDark.value?'dark':'light'; settings.value.theme=isDark.value?'dark':'light'; saveSettings()}

onMounted(async()=>{ try{const s=await api('/settings');settings.value={...settings.value,...s.settings};isDark.value=settings.value.theme!=='light';document.documentElement.dataset.theme=isDark.value?'dark':'light';await loadHistory();await loadPresets();startPolling()}catch(e){error.value=e.message} })
onUnmounted(()=>clearTimeout(timer))
</script>

<template>
<div class="app-shell">
  <aside class="sidebar">
    <div class="brand"><div class="brand-icon">YT</div><div><b>Downloader</b><small>Professional</small></div></div>
    <nav>
      <button :class="{active:active==='download'}" @click="active='download'"><Download/> دانلود</button>
      <button :class="{active:active==='queue'}" @click="active='queue'"><ListVideo/> صف دانلود <span v-if="runningJobs.length" class="badge">{{runningJobs.length}}</span></button>
      <button :class="{active:active==='history'}" @click="active='history';loadHistory()"><History/> تاریخچه</button>
      <button :class="{active:active==='presets'}" @click="active='presets';loadPresets()"><Zap/> Presetها</button>
      <button :class="{active:active==='settings'}" @click="active='settings'"><Settings/> تنظیمات</button>
    </nav>
    <button class="theme" @click="toggleTheme"> <Moon v-if="isDark"/><Sun v-else/> {{isDark?'حالت تاریک':'حالت روشن'}} </button>
  </aside>

  <main class="content">
    <header class="topbar"><div><span class="eyebrow">VIDEO DOWNLOADER</span><h1>{{active==='download'?'دانلود سریع و حرفه‌ای':active==='queue'?'صف دانلود':active==='history'?'تاریخچه دانلود':'مدیریت برنامه'}}</h1></div><button class="icon-btn" @click="pasteFromClipboard" title="خواندن Clipboard"><Clipboard/></button></header>

    <section v-if="active==='download'" class="download-page">
      <div class="hero-card">
        <div class="hero-icon"><Download/></div><h2>لینک YouTube را وارد کنید</h2><p>ویدیو، Playlist و Shorts را با کیفیت دلخواه دانلود کنید.</p>
        <div class="url-row"><input v-model="url" @paste="handlePaste" @keyup.enter="inspect" placeholder="https://www.youtube.com/watch?v=..."/><button class="primary" :disabled="loading" @click="inspect">{{loading?'در حال بررسی...':'بررسی لینک'}} <Search/></button></div>
        <div class="quick"><button @click="pasteFromClipboard"><Clipboard/> Paste از Clipboard</button><button @click="mediaType='audio'"><Music2/> MP3</button><button @click="mediaType='video'"><Video/> Video</button></div>
      </div>

      <div v-if="error" class="alert error"><AlertCircle/> {{error}} <button @click="error=''">×</button></div>

      <div v-if="info && !playlist" class="media-card">
        <img :src="info.thumbnail"/><div class="media-main"><span class="pill">{{info.uploader||'YouTube'}}</span><h3>{{info.title}}</h3><p>{{info.duration?Math.floor(info.duration/60)+' دقیقه':''}}</p>
        <div class="controls"><select v-model="selectedQuality"><option value="best">بهترین کیفیت</option><option v-for="q in qualities" :key="q.value" :value="q.value">{{q.resolution}} · {{q.label}}</option></select><button class="primary" @click="startDownload()"><Download/> دانلود</button><button class="secondary" @click="downloadThumbnail"><Image/> Thumbnail</button></div></div>
      </div>

      <div v-if="playlist" class="playlist-card"><div class="section-title"><div><span class="pill">PLAYLIST</span><h2>{{playlist.title}}</h2><p>{{playlist.count}} ویدیو</p></div><button class="primary" @click="downloadPlaylist"><Download/> دانلود انتخاب‌ها</button></div><div class="playlist-tools"><button @click="selectedItems=playlist.entries.map(x=>x.index)">انتخاب همه</button><button @click="selectedItems=[]">لغو همه</button></div><label v-for="item in playlist.entries" :key="item.index" class="playlist-item"><input type="checkbox" :value="item.index" v-model="selectedItems"/><img :src="item.thumbnail"/><div><b>{{item.title}}</b><small>{{item.duration?Math.floor(item.duration/60)+' دقیقه':''}}</small></div></label></div>

      <div v-if="jobs.length" class="jobs"><div class="section-title"><h2>دانلودهای اخیر</h2><button @click="active='queue'">مشاهده همه</button></div><div v-for="j in jobs.slice(0,3)" :key="j.id" class="job"><div class="job-head"><b>{{j.message}}</b><strong>{{j.percent||0}}%</strong></div><div class="progress"><i :style="{width:(j.percent||0)+'%'}"></i></div><div class="job-meta"><span>{{j.downloaded||'—'}} / {{j.total||'—'}}</span><span>{{j.speed||'—'}}</span><button v-if="!['completed','error','cancelled'].includes(j.status)" @click="cancel(j.id)"><X/> لغو</button><a v-if="j.status==='completed'" :href="'/api/file/'+j.id"><FolderOpen/> فایل</a></div></div></div>
    </section>

    <section v-else-if="active==='queue'" class="panel"><div class="section-title"><div><h2>صف دانلود</h2><p>{{jobs.length}} عملیات ثبت شده</p></div></div><div v-if="!jobs.length" class="empty"><ListVideo/><h3>صف خالی است</h3><p>دانلود جدید را از صفحه اصلی اضافه کنید.</p></div><div v-for="j in jobs" :key="j.id" class="job big"><div class="job-head"><div><b>{{j.filename||j.message}}</b><small>{{j.status}}</small></div><strong>{{j.percent||0}}%</strong></div><div class="progress"><i :style="{width:(j.percent||0)+'%'}"></i></div><div class="job-meta"><span>{{j.speed||'—'}} · {{j.eta||'—'}}</span><button v-if="!['completed','error','cancelled'].includes(j.status)" @click="cancel(j.id)"><X/> لغو</button><button v-if="j.status==='error'" @click="retry(j)"><RotateCcw/> تلاش مجدد</button><a v-if="j.status==='completed'" :href="'/api/file/'+j.id"><FolderOpen/> باز کردن</a></div></div></section>

    <section v-else-if="active==='history'" class="panel"><div class="section-title"><div><h2>تاریخچه دانلود</h2><p>تمام فایل‌های قبلی</p></div><div class="actions"><div class="search"><Search/><input v-model="search" placeholder="جستجو..."/></div><button class="danger" @click="clearHistory"><Trash2/> پاک کردن</button></div></div><div v-if="!visibleHistory.length" class="empty"><History/><h3>تاریخچه‌ای وجود ندارد</h3></div><div v-for="item in visibleHistory" :key="item.id" class="history-item"><div class="history-icon">{{item.media_type==='audio'?'♫':'▶'}}</div><div class="history-info"><b>{{item.title}}</b><small>{{item.quality}} · {{item.media_type}} · {{item.size?Math.round(item.size/1024/1024)+' MB':'—'}}</small></div><a v-if="item.path" :href="'/api/file/'+item.id"><FolderOpen/></a><button @click="deleteHistory(item.id)"><Trash2/></button></div></section>

    <section v-else-if="active==='presets'" class="panel"><div class="section-title"><div><h2>Download Presets</h2><p>تنظیمات آماده برای دانلود سریع</p></div><button class="primary" @click="savePreset"><Plus/> ساخت Preset</button></div><div class="preset-grid"><div v-for="p in presets" :key="p.id" class="preset"><Zap/><h3>{{p.name}}</h3><p>{{p.settings.mediaType||'video'}} · {{p.settings.quality||'best'}}</p><button @click="usePreset(p)">استفاده</button></div></div></section>

    <section v-else class="panel settings"><h2>تنظیمات</h2><label>مسیر دانلود<input v-model="settings.download_path"/></label><label>تعداد دانلود همزمان<input type="number" min="1" max="5" v-model.number="settings.concurrent_downloads"/></label><label>محدودیت سرعت (KB/s، صفر = بدون محدودیت)<input type="number" min="0" v-model.number="settings.speed_limit"/></label><label class="switch"><input type="checkbox" v-model="settings.notifications"/> اعلان پایان دانلود</label><label class="switch"><input type="checkbox" v-model="settings.clipboard_monitor"/> مانیتور Clipboard</label><button class="primary" @click="saveSettings">ذخیره تنظیمات</button></section>
  </main>
</div>
</template>
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useState, useRef, useEffect } from 'react'
import { api } from '../lib/api'
import { Upload, Download, Eye, ArrowLeft, ZoomIn, X, Video } from 'lucide-react'
import { SplitTool } from './SplitTool'
import { MergeTool } from './MergeTool'
import { QuickNext } from '../components/QuickNext'

export function ToolPage(){
  const {id}=useParams()
  // hooks MUST run before any early return (React rules of hooks)
  const [files,setFiles]=useState<{id:string,name:string}[]>([])
  const [uploading,setUploading]=useState(false)
  const [uploadProgress,setUploadProgress]=useState(0)
  const [uploadDone,setUploadDone]=useState(false)
  const [job,setJob]=useState<any>(null)
  const [progress,setProgress]=useState('')
  const [params,setParams]=useState<any>({})
  const [previewRows,setPreviewRows]=useState<string[][]|null>(null)
  const [previewUrl,setPreviewUrl]=useState<string|null>(null)
  const [previewKind,setPreviewKind]=useState<string>("")
  const [jobStart,setJobStart]=useState<number|null>(null)
  const pollRef=useRef<any>(null)
  const isSplit = id==='split'
  const isMerge = id==='merge'
  if(isSplit) return <SplitTool/>
  if(isMerge) return <MergeTool/>

  return <GenericToolPage
    toolId={id||''}
    files={files} setFiles={setFiles}
    uploading={uploading} setUploading={setUploading}
    uploadProgress={uploadProgress} setUploadProgress={setUploadProgress}
    uploadDone={uploadDone} setUploadDone={setUploadDone}
    job={job} setJob={setJob}
    progress={progress} setProgress={setProgress}
    params={params} setParams={setParams}
    previewRows={previewRows} setPreviewRows={setPreviewRows}
    previewUrl={previewUrl} setPreviewUrl={setPreviewUrl}
    previewKind={previewKind} setPreviewKind={setPreviewKind}
    jobStart={jobStart} setJobStart={setJobStart}
    pollRef={pollRef}
  />
}

interface GenericProps{
  toolId:string
  files:{id:string,name:string}[]; setFiles:(f:any)=>void
  uploading:boolean; setUploading:(b:boolean)=>void
  uploadProgress:number; setUploadProgress:(n:number)=>void
  uploadDone:boolean; setUploadDone:(b:boolean)=>void
  job:any; setJob:(j:any)=>void
  progress:string; setProgress:(s:string)=>void
  params:any; setParams:(p:any)=>void
  previewRows:string[][]|null; setPreviewRows:(r:any)=>void
  previewUrl:string|null; setPreviewUrl:(u:string|null)=>void
  previewKind:string; setPreviewKind:(k:string)=>void
  jobStart:number|null; setJobStart:(n:number|null)=>void
  pollRef:any
}

function GenericToolPage(p:GenericProps){
  const toolId=p.toolId
  const navigate=useNavigate()
  // page thumbnails (like SplitTool) via backend
  const [pageCount,setPageCount]=useState(0)
  const [thumbs,setThumbs]=useState<string[]>([])
  const [infoErr,setInfoErr]=useState(false)
  const [zoomPage,setZoomPage]=useState<number|null>(null)
  const primaryFile=p.files[0]?.id || null
  const primaryName=p.files[0]?.name || ""
  const isPdf = primaryName.toLowerCase().endsWith('.pdf')

  useEffect(()=>{
    if(!primaryFile || !isPdf){ setPageCount(0); setThumbs([]); return }
    let cancelled=false
    const load=async()=>{
      try{
        const info=await api.get(`/api/files/${primaryFile}/info`)
        if(cancelled) return
        const pages=info.data.pages||0
        setPageCount(pages); setInfoErr(false); setThumbs([])
        const urls:string[]=[]
        const limit=Math.min(pages, 60) // jangan terlalu berat utk PDF besar
        for(let i=1;i<=limit;i++){
          try{
            const r=await api.get(`/api/files/${primaryFile}/thumb/${i}`, {responseType:'blob'})
            urls.push(URL.createObjectURL(r.data))
          }catch{ urls.push("") }
        }
        if(!cancelled) setThumbs(urls)
      }catch{
        if(!cancelled){ setInfoErr(true); setPageCount(0); setThumbs([]) }
      }
    }
    load()
    return()=>{ cancelled=true }
  },[primaryFile, isPdf])

  const upload=async(list:FileList|File[])=>{
    p.setUploading(true); p.setUploadProgress(0); p.setUploadDone(false)
    p.setPreviewRows(null); p.setPreviewUrl(null); p.setPreviewKind("")
    const out:{id:string,name:string}[]=[]
    const arr=Array.from(list as FileList)
    for(let idx=0; idx<arr.length; idx++){
      const f=arr[idx]
      const fd=new FormData(); fd.append('file',f)
      const r=await api.post('/api/files',fd,{
        headers:{'Content-Type':'multipart/form-data'},
        onUploadProgress:(e:any)=>{
          const pct=e.total ? Math.round(e.loaded*100/e.total) : 0
          const overall=Math.round((idx + pct/100)/arr.length*100)
          p.setUploadProgress(overall)
        }
      })
      out.push({id:r.data.id,name:r.data.original_name})
    }
    p.setFiles((prev:any)=>[...prev,...out]); p.setUploading(false); p.setUploadProgress(100); p.setUploadDone(true)
    setTimeout(()=>p.setUploadDone(false), 2500)
  }

  const removeFile=async(fid:string)=>{
    try{ await api.delete(`/api/files/${fid}`) }catch{}
    p.setFiles((prev:any)=>prev.filter((x:any)=>x.id!==fid))
    if(primaryFile===fid){ setPageCount(0); setThumbs([]); p.setPreviewUrl(null); p.setPreviewKind(""); p.setPreviewRows(null) }
  }

  const createJob=async()=>{
    const urlTools=['video-downloader']
    if(urlTools.includes(toolId)){
      if(!p.params.url?.trim()) return alert('Paste URL first')
      const body:any={tool:toolId, params:p.params}
      const r=await api.post('/api/jobs',body)
      p.setJob(r.data); p.setJobStart(Date.now()); poll(r.data.id)
      return
    }
    if(p.files.length===0) return alert('Upload file first')
    const body:any={tool:toolId, params:p.params, file_id: p.files[0].id, file_ids: p.files.map(f=>f.id)}
    const r=await api.post('/api/jobs',body)
    p.setJob(r.data); p.setJobStart(Date.now()); poll(r.data.id)
  }
  const poll=(jid:string)=>{
    p.pollRef.current && clearInterval(p.pollRef.current)
    p.pollRef.current=setInterval(async()=>{
      const r=await api.get(`/api/jobs/${jid}`)
      p.setJob(r.data); p.setProgress(`${r.data.status} ${r.data.progress}% ${r.data.message||''}`)
      if(['completed','failed','cancelled'].includes(r.data.status)){
        clearInterval(p.pollRef.current)
        if(r.data.status==='completed'){
          // result preview: CSV/Excel -> table rows
          try{ const pv=await api.get(`/api/jobs/${jid}/preview`); if(pv.data.rows) { p.setPreviewRows(pv.data.rows); } }catch{}
        }
      }
    },800)
  }
  const download=async()=>{
    const r=await api.get(`/api/jobs/${p.job.id}/download`,{responseType:'blob'})
    const cd=r.headers['content-disposition'] as string || ""
    let fname=""
    const m=cd.match(/filename="?([^"]+)"?/)
    if(m) fname=m[1]
    else if(toolId==='pdf-to-excel-cam') fname='Detail_CAM_Excel.xlsx'
    else fname = toolId==='pdf-to-excel' ? 'converted.xlsx' : toolId==='pdf-to-csv' ? 'tables.zip' : toolId+'_result.pdf'
    if((toolId==='pdf-to-excel'||toolId==='pdf-to-excel-cam') && !fname.endsWith('.xlsx')) fname='converted.xlsx'
    if(toolId==='pdf-to-csv' && !fname.endsWith('.csv') && !fname.endsWith('.zip')) fname+='.csv'
    const url=URL.createObjectURL(r.data); const a=document.createElement('a'); a.href=url; a.download=fname; a.click()
    setTimeout(()=>URL.revokeObjectURL(url), 5000)
  }

  const fmtETA=(start:number|null, prog:number)=>{
    if(!start || prog<=0 || prog>=100) return ""
    const elapsed=(Date.now()-start)/1000
    const total=elapsed*100/prog
    const remain=Math.max(0, total-elapsed)
    if(remain<60) return `~${Math.ceil(remain)} detik lagi`
    return `~${Math.ceil(remain/60)} menit lagi`
  }

  const showPageThumbs = pageCount>0 && p.files.length>0

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
      <button onClick={()=>navigate(-1)} className="inline-flex items-center gap-1.5 text-sm text-slate-600 hover:text-slate-900 mb-3">
        <ArrowLeft size={16}/> Kembali
      </button>
      <Link to="/dashboard" className="ml-3 text-sm text-brand-600 hover:underline">ke Dashboard</Link>
      <h1 className="text-2xl font-bold capitalize mt-1">{toolId.replaceAll('-',' ')}</h1>
      <p className="text-sm text-slate-500">Preview → Configure → Process → Download</p>

      <div className="mt-6 grid lg:grid-cols-5 gap-6 items-start">
        {/* ===== KIRI: upload + opsi + proses (sticky, tidak ikut scroll) ===== */}
        <div className="lg:col-span-2 lg:sticky lg:top-20 lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto bg-white dark:bg-slate-900 rounded-2xl p-6 border border-slate-200 dark:border-slate-800 space-y-6 self-start">
          {/* Upload */}
          <section>
            <h3 className="font-medium mb-3">1. {toolId==='video-downloader'?'Paste URL':'Upload'}</h3>
            {toolId==='video-downloader' ? (
              <div className="space-y-3">
                <input
                  placeholder="https://youtube.com/watch?v=… or any supported URL"
                  value={p.params.url||''}
                  onChange={e=>{ const v=e.target.value; p.setParams({...p.params, url:v}) }}
                  className="w-full px-3 py-2 rounded-xl border text-sm"
                />
                <div className="flex flex-wrap gap-2 text-xs text-slate-500">
                  <span className="px-2 py-1 bg-slate-100 rounded-lg">YouTube</span>
                  <span className="px-2 py-1 bg-slate-100 rounded-lg">Twitter/X</span>
                  <span className="px-2 py-1 bg-slate-100 rounded-lg">Instagram</span>
                  <span className="px-2 py-1 bg-slate-100 rounded-lg">TikTok</span>
                  <span className="px-2 py-1 bg-slate-100 rounded-lg">1000+ sites</span>
                </div>
              </div>
            ) : (
            <div>
            <label
              onDragOver={e=>e.preventDefault()}
              onDrop={e=>{e.preventDefault(); if(e.dataTransfer.files.length) upload(e.dataTransfer.files)}}
              className="border-2 border-dashed rounded-xl p-6 flex flex-col items-center cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800"
            >
              <Upload className="text-slate-400"/>
              <span className="text-sm mt-2">Drop atau klik untuk pilih file</span>
              <span className="text-xs text-slate-400 mt-1">{toolId==='image-to-pdf' ? 'JPG / PNG (bisa beberapa)' : toolId==='mp3-trim' ? 'MP3' : 'PDF (bisa beberapa)'}</span>
              <input type="file" multiple className="hidden" onChange={e=>e.target.files&&upload(e.target.files)}/>
            </label>
            {p.uploading && (
              <div className="mt-3">
                <div className="flex justify-between text-xs mb-1"><span className="text-slate-500">Upload</span><span className="font-medium">{p.uploadProgress}%</span></div>
                <div className="h-2 bg-slate-100 rounded-full overflow-hidden"><div className="h-full bg-brand-600 transition-all" style={{width:`${p.uploadProgress}%`}}/></div>
              </div>
            )}
            {!p.uploading && p.uploadDone && <div className="mt-2 text-xs font-medium text-emerald-600 flex items-center gap-1">✓ Upload selesai</div>}
            <ul className="mt-3 text-sm space-y-2">{p.files.map(f=>(
              <li key={f.id} className="flex items-center gap-2 bg-slate-100 dark:bg-slate-800 px-3 py-2 rounded-xl">
                <span className="flex-1 truncate text-xs">{f.name}</span>
                <button
                  onClick={()=>removeFile(f.id)}
                  className="w-6 h-6 rounded-full bg-white border text-slate-500 hover:text-rose-600 hover:border-rose-300 grid place-items-center text-xs flex-shrink-0"
                  title="Hapus file"
                >×</button>
              </li>
            ))}</ul>
            </div>
          )} {/* close ternary for video-downloader */}
          </section>

          {/* Options */}
          <section>
            <h3 className="font-medium mb-2">2. Options</h3>
            <ToolOptions tool={toolId} params={p.params} setParams={p.setParams}/>
          </section>

          {/* Process */}
          <section>
            <button onClick={createJob} className="w-full py-2.5 bg-indigo-600 text-white rounded-xl font-medium hover:bg-indigo-700">Process → Create Job</button>
            {p.job && <div className="mt-4 p-3 bg-white border rounded-xl text-sm shadow-sm">
              <div className="flex justify-between items-center"><span className="font-medium text-xs">Job {p.job.id.slice(0,8)} — {p.job.status}</span><span className="text-xs font-bold text-brand-600">{p.job.progress}%</span></div>
              <div className="h-2 bg-slate-100 rounded-full overflow-hidden mt-2"><div className={`h-full transition-all ${p.job.status==='completed'?'bg-emerald-500':p.job.status==='failed'?'bg-rose-500':'bg-brand-600'}`} style={{width:`${p.job.progress}%`}}/></div>
              <div className="flex justify-between mt-1"><span className="text-xs text-slate-500">{p.job.status==='processing' ? 'Processing' : p.progress || p.job.message}</span><span className="text-xs text-slate-400">{p.job.status==='processing' ? fmtETA(p.jobStart, p.job.progress) : ''}</span></div>
              <div className="text-[11px] text-slate-400 mt-1">{p.job.status==='processing' ? 'Upload selesai ✓ • Processing...' : p.job.status==='completed' ? 'Upload selesai ✓ • Selesai' : ''}</div>
              {p.job.error && <pre className="text-xs text-rose-600 whitespace-pre-wrap mt-2 bg-rose-50 p-2 rounded-lg">{p.job.error.slice(0,800)}</pre>}
              {p.job.status==='completed' && <button onClick={download} className="mt-3 w-full py-2 bg-emerald-600 text-white rounded-full flex gap-2 items-center justify-center text-sm"><Download size={16}/>Download Result</button>}
              {p.job.status==='completed' && <QuickNext current={toolId} />}
            </div>}
          </section>
        </div>

        {/* ===== KANAN: preview ===== */}
        <div className="lg:col-span-3 bg-white dark:bg-slate-900 rounded-2xl p-6 border border-slate-200 dark:border-slate-800">
          <h3 className="font-medium flex gap-2 items-center"><Eye size={16}/> Preview / Result</h3>

          {/* preview file utama (pdf/image/audio) */}
          {p.previewUrl && (
            <div className="mt-3">
              {p.previewKind==='pdf' && <iframe src={p.previewUrl} className="w-full h-[420px] rounded-xl border" title="pdf preview"/>}
              {p.previewKind==='image' && <img src={p.previewUrl} className="w-full rounded-xl border max-h-[420px] object-contain"/>}
              {p.previewKind==='audio' && <audio controls src={p.previewUrl} className="w-full mt-2"/>}
              {p.previewKind==='other' && <p className="text-xs text-slate-500">Preview: {p.files[0]?.name}</p>}
            </div>
          )}

          {/* thumbnails semua halaman seperti SplitTool + tombol zoom (kaca pembesar) */}
          {showPageThumbs && (
            <div className="mt-4">
              <div className="text-xs font-medium text-slate-500 mb-2">{p.files[0]?.name} · {pageCount} halaman{pageCount>60?' (menampilkan 60 pertama)':''} — klik 🔍 untuk detail</div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 max-h-[560px] overflow-y-auto pr-1">
                {Array.from({length:Math.min(pageCount,60)},(_,i)=>i+1).map(n=>(
                  <div key={n} className="relative group bg-white rounded-xl border border-slate-200 overflow-hidden">
                    <span className="absolute top-1.5 left-1.5 z-10 w-5 h-5 rounded-md bg-slate-700 text-white flex items-center justify-center text-[11px] font-bold">{n}</span>
                    <button
                      onClick={()=>setZoomPage(n)}
                      title="Lihat detail halaman"
                      className="absolute top-1.5 right-1.5 z-10 w-6 h-6 rounded-md bg-white/90 border border-slate-200 text-slate-500 hover:text-brand-600 hover:border-brand-300 items-center justify-center opacity-0 group-hover:opacity-100 transition hidden sm:flex"
                    ><ZoomIn size={13}/></button>
                    <button onClick={()=>setZoomPage(n)} className="block w-full cursor-zoom-in">
                      <div className="aspect-[0.71] bg-slate-50 flex items-center justify-center overflow-hidden">
                        {thumbs[n-1] ? <img src={thumbs[n-1]} alt={`p${n}`} className="w-full h-full object-contain"/> : <span className="text-xs text-slate-400">Hal {n}</span>}
                      </div>
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
          {!showPageThumbs && !p.previewUrl && p.files.length>0 && !infoErr && toolId!=='mp3-trim' && (
            <p className="text-xs text-slate-400 mt-3">Menyiapkan preview halaman…</p>
          )}

          {/* hasil tabel (CSV/Excel) */}
          {p.previewRows ? (
            <div className="mt-4">
              <div className="text-xs font-medium text-slate-500 mb-2">Hasil konversi (30 baris pertama):</div>
              <div className="overflow-auto max-h-[420px] border rounded-xl">
                <table className="text-xs w-full"><tbody>{p.previewRows.map((row,i)=><tr key={i} className="border-b">{row.map((c,j)=><td key={j} className="px-2 py-1 border-r whitespace-nowrap">{c}</td>)}</tr>)}</tbody></table>
              </div>
            </div>
          ) : null}

          {p.files.length===0 && !p.previewUrl && !p.previewRows && toolId!=='video-downloader' && (
            <p className="text-sm text-slate-500 mt-3">Upload file untuk melihat preview halaman di sini. Hasil konversi (CSV/Excel) juga akan tampil sebagai tabel setelah selesai.</p>
          )}
          {toolId==='video-downloader' && !p.job && (
            <div className="mt-6 flex flex-col items-center justify-center text-center py-16 text-slate-400">
              <div className="w-16 h-16 rounded-2xl bg-slate-100 grid place-items-center mb-4">
                <Video size={28} className="text-slate-400"/>
              </div>
              <p className="text-sm font-medium text-slate-500">Video / MP3 Downloader</p>
              <p className="text-xs text-slate-400 mt-1 max-w-xs">Paste URL dari YouTube, Twitter, Instagram, TikTok, atau 1000+ situs lalu pilih format dan klik Process.</p>
            </div>
          )}
          {toolId==='md-to-pdf' && <div className="text-xs text-slate-500 mt-2">Isi markdown di panel kiri (Options → textarea); hasil PDF bisa didownload setelah proses.</div>}
          {toolId==='mp3-trim' && <AudioPreview/>}
        </div>
      </div>

      {/* Modal zoom detail halaman */}
      {zoomPage !== null && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4" onClick={()=>setZoomPage(null)}>
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 max-w-4xl w-full max-h-[92vh] flex flex-col overflow-hidden" onClick={e=>e.stopPropagation()}>
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-800">
              <span className="text-sm font-semibold">Halaman {zoomPage} · {p.files[0]?.name}</span>
              <button onClick={()=>setZoomPage(null)} className="w-7 h-7 rounded-full bg-slate-100 hover:bg-rose-50 hover:text-rose-600 grid place-items-center text-slate-500"><X size={15}/></button>
            </div>
            <div className="flex-1 overflow-auto bg-slate-50 p-4 flex items-center justify-center">
              <ZoomThumb thumbs={thumbs} n={zoomPage} fid={p.files[0]?.id}/>
            </div>
            <div className="flex items-center justify-between px-4 py-2 border-t border-slate-200 dark:border-slate-800 text-xs text-slate-500">
              <button disabled={zoomPage<=1} onClick={()=>setZoomPage(zoomPage-1)} className="px-3 py-1.5 rounded-lg border disabled:opacity-40 hover:bg-slate-50">← Sebelumnya</button>
              <span>{zoomPage} / {pageCount}</span>
              <button disabled={zoomPage>=pageCount} onClick={()=>setZoomPage(zoomPage+1)} className="px-3 py-1.5 rounded-lg border disabled:opacity-40 hover:bg-slate-50">Berikutnya →</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function ZoomThumb({thumbs, n, fid}:{thumbs:string[], n:number, fid?:string}){
  const [url,setUrl]=useState<string|null>(null)
  useEffect(()=>{
    setUrl(thumbs[n-1]||null)
    let alive=true
    if(!thumbs[n-1] && fid){
      api.get(`/api/files/${fid}/thumb/${n}`, {responseType:'blob'}).then(r=>{
        if(alive) setUrl(URL.createObjectURL(r.data))
      }).catch(()=>{})
    }
    return()=>{ alive=false }
  },[n, fid])
  if(!url) return <span className="text-sm text-slate-400">Memuat halaman {n}…</span>
  return <img src={url} alt={`hal ${n}`} className="max-w-full max-h-[75vh] object-contain rounded-lg shadow"/>
}

function ToolOptions({tool,params,setParams}:{tool:string,params:any,setParams:(p:any)=>void}){
  const set=(k:string,v:any)=>setParams({...params,[k]:v})
  if(tool==='rotate') return <select value={params.angle||90} onChange={e=>set('angle',e.target.value)} className="w-full px-3 py-2 rounded-xl border"><option value={90}>90°</option><option value={180}>180°</option><option value={270}>270°</option></select>
  if(tool==='delete-pages' || tool==='extract-pages') return <input placeholder="Pages e.g. 1,3,5-7" value={params.pages||''} onChange={e=>set('pages',e.target.value.split(',').map((s:string)=>s.trim()).filter(Boolean))} className="w-full px-3 py-2 rounded-xl border"/>
  if(tool==='reorder') return <input placeholder="Order e.g. 3,1,2" value={params.order||''} onChange={e=>set('order',e.target.value.split(',').map((s:string)=>s.trim()))} className="w-full px-3 py-2 rounded-xl border"/>
  if(tool==='protect' || tool==='unlock') return <input placeholder="Password" type="password" value={params.password||''} onChange={e=>set('password',e.target.value)} className="w-full px-3 py-2 rounded-xl border"/>
  if(tool==='watermark') return <input placeholder="Watermark text" value={params.text||''} onChange={e=>set('text',e.target.value)} className="w-full px-3 py-2 rounded-xl border"/>
  if(tool==='remove-watermark') return <input placeholder="Teks watermark yang mau dihapus (kosong = auto semua)" value={params.text||''} onChange={e=>set('text',e.target.value)} className="w-full px-3 py-2 rounded-xl border"/>
  if(tool==='compress') return <select value={params.quality||'medium'} onChange={e=>set('quality',e.target.value)} className="w-full px-3 py-2 rounded-xl border"><option>low</option><option>medium</option><option>high</option></select>
  if(tool==='pdf-to-image') return <div className="flex gap-2"><select value={params.format||'png'} onChange={e=>set('format',e.target.value)} className="px-3 py-2 rounded-xl border"><option>png</option><option>jpg</option></select><input placeholder="dpi 150" value={params.dpi||''} onChange={e=>set('dpi',e.target.value)} className="flex-1 px-3 py-2 rounded-xl border"/></div>
  if(tool==='pdf-to-csv') return <div className="space-y-2"><select value={params.delimiter||','} onChange={e=>set('delimiter',e.target.value)} className="w-full px-3 py-2 rounded-xl border"><option value=",">Comma (,)</option><option value="semicolon">Semicolon (;)</option><option value="tab">Tab</option></select><p className="text-xs text-slate-500">Exports all detected tables; single CSV or ZIP if multiple.</p></div>
  if(tool==='pdf-to-excel') return <div className="space-y-2">
    <select value={params.excelMode||'per_sheet'} onChange={e=>set('excelMode',e.target.value)} className="w-full px-3 py-2 rounded-xl border bg-white">
      <option value="per_sheet">Pisah halaman per sheet</option>
      <option value="merge">Merge semua halaman ke 1 sheet</option>
    </select>
    <p className="text-xs text-slate-500">{(params.excelMode||'per_sheet')==='merge' ? 'Semua tabel dari semua halaman digabung ke 1 sheet (dipisah baris kosong).' : 'Tiap halaman jadi sheet terpisah.'}</p>
  </div>
  if(tool==='pdf-to-excel-cam') return <div className="space-y-2">
    <div className="p-3 rounded-xl bg-violet-50 border border-violet-100 text-xs text-violet-800 space-y-1">
      <p className="font-semibold">Mode khusus Detail CAM Prioritisasi</p>
      <p>1. Watermark (nama/NIP diagonal) dihapus otomatis terlebih dahulu.</p>
      <p>2. Semua halaman PDF digabung menjadi <b>1 sheet Excel</b> dengan header baku 32 kolom.</p>
      <p>3. Header berulang di tiap halaman otomatis dibuang.</p>
    </div>
    <p className="text-xs text-slate-500">Tidak ada opsi tambahan — cukup upload file PDF CAM lalu klik Process.</p>
  </div>
  if(tool==='md-to-pdf') return <div className="space-y-2"><textarea placeholder="# Hello Markdown..." value={params.markdown||''} onChange={e=>set('markdown',e.target.value)} rows={8} className="w-full px-3 py-2 rounded-xl border font-mono text-sm"/><div className="grid grid-cols-3 gap-2"><select value={params.paper||'A4'} onChange={e=>set('paper',e.target.value)} className="px-2 py-2 rounded-xl border"><option>A4</option><option>Letter</option><option>A3</option></select><select value={params.orientation||'portrait'} onChange={e=>set('orientation',e.target.value)} className="px-2 py-2 rounded-xl border"><option>portrait</option><option>landscape</option></select><input placeholder="filename.pdf" value={params.filename||''} onChange={e=>set('filename',e.target.value)} className="px-2 py-2 rounded-xl border"/></div></div>
  if(tool==='html-to-pdf') return <div className="space-y-2"><textarea placeholder="<h1>Hello HTML</h1>" value={params.html||''} onChange={e=>set('html',e.target.value)} rows={8} className="w-full px-3 py-2 rounded-xl border font-mono text-sm"/><div className="grid grid-cols-3 gap-2"><select value={params.paper||'A4'} onChange={e=>set('paper',e.target.value)} className="px-2 py-2 rounded-xl border"><option>A4</option><option>Letter</option></select><select value={params.orientation||'portrait'} onChange={e=>set('orientation',e.target.value)} className="px-2 py-2 rounded-xl border"><option>portrait</option><option>landscape</option></select><input placeholder="filename.pdf" value={params.filename||''} onChange={e=>set('filename',e.target.value)} className="px-2 py-2 rounded-xl border"/></div></div>
  if(tool==='mp3-trim') return <div className="grid grid-cols-2 gap-2"><input type="number" placeholder="Start sec" value={params.start||''} onChange={e=>set('start',e.target.value)} className="px-3 py-2 rounded-xl border"/><input type="number" placeholder="End sec" value={params.end||''} onChange={e=>set('end',e.target.value)} className="px-3 py-2 rounded-xl border"/></div>
  if(tool==='video-downloader') return <div className="space-y-2">
    <label className="text-xs font-medium text-slate-600">Format</label>
    <div className="flex gap-2">
      <button onClick={()=>set('format','mp4')} className={`flex-1 py-2 rounded-xl border text-sm font-medium transition-colors ${params.format!=='mp3'?'bg-indigo-600 text-white border-indigo-600':'bg-white text-slate-600 hover:bg-slate-50'}`}>🎬 MP4 (Video)</button>
      <button onClick={()=>set('format','mp3')} className={`flex-1 py-2 rounded-xl border text-sm font-medium transition-colors ${params.format==='mp3'?'bg-indigo-600 text-white border-indigo-600':'bg-white text-slate-600 hover:bg-slate-50'}`}>🎵 MP3 (Audio)</button>
    </div>
    <p className="text-xs text-slate-500">Output: {params.format==='mp3'?'MP3 audio 320kbps':'MP4 best quality'}</p>
  </div>
  return <p className="text-sm text-slate-500">No extra options. For Merge, upload multiple files.</p>
}

function AudioPreview(){
  const [url,setUrl]=useState<string|null>(null)
  return <div className="mt-4">
    <input type="file" accept=".mp3" onChange={e=>{ if(e.target.files?.[0]) setUrl(URL.createObjectURL(e.target.files[0])) }} className="text-sm"/>
    {url && <audio controls src={url} className="w-full mt-2"/>}
    <p className="text-xs text-slate-500 mt-1">Upload MP3, set start/end seconds, then Process. Result will be downloadable.</p>
  </div>
}
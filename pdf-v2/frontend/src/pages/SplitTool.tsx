import { useState, useRef, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { api } from '../lib/api'
import { QuickNext } from '../components/QuickNext'
import { ArrowLeft } from 'lucide-react'

function parseRange(input:string, max:number): number[]{
  const out=new Set<number>()
  const parts=input.split(',').map(s=>s.trim()).filter(Boolean)
  for(const p of parts){
    if(p.includes('-')){
      const [a,b]=p.split('-').map(s=>parseInt(s.trim()))
      if(isNaN(a)||isNaN(b)) continue
      const lo=Math.min(a,b), hi=Math.max(a,b)
      for(let i=lo;i<=hi;i++) if(i>=1&&i<=max) out.add(i)
    } else {
      const n=parseInt(p); if(!isNaN(n)&&n>=1&&n<=max) out.add(n)
    }
  }
  return Array.from(out).sort((a,b)=>a-b)
}
function pagesToRange(pages:number[]): string{
  if(pages.length===0) return "—"
  // compress consecutive
  const sorted=[...pages].sort((a,b)=>a-b)
  const groups:string[]=[]
  let start=sorted[0], prev=sorted[0]
  for(let i=1;i<sorted.length;i++){
    if(sorted[i]===prev+1) prev=sorted[i]
    else { groups.push(start===prev?`${start}`:`${start}-${prev}`); start=prev=sorted[i] }
  }
  groups.push(start===prev?`${start}`:`${start}-${prev}`)
  return groups.join(', ')
}

export function SplitTool(){
  const navigate=useNavigate()
  const [fileId,setFileId]=useState<string|null>(null)
  const [fileName,setFileName]=useState<string>("")
  const [pageCount,setPageCount]=useState(0)
  const [fileObj,setFileObj]=useState<File|null>(null)
  const [parts,setParts]=useState<{id:number,pages:number[],rangeInput:string}[]>([{id:1,pages:[],rangeInput:""}])
  const [activePart,setActivePart]=useState(0)
  const [job,setJob]=useState<any>(null)
  const [progress,setProgress]=useState("")
  const [uploading,setUploading]=useState(false)
  const [uploadProgress,setUploadProgress]=useState(0)
  const [uploadDone,setUploadDone]=useState(false)
  const [thumbs,setThumbs]=useState<string[]>([]) // data urls per page
  const [jobStart,setJobStart]=useState<number|null>(null)
  const inputRef=useRef<HTMLInputElement>(null)
  const pollRef=useRef<any>(null)
  const fmtETA=(s:number|null,p:number)=>{ if(!s||p<=0||p>=100) return ""; const e=(Date.now()-s)/1000; const t=e*100/p; const r=Math.max(0,t-e); return r<60?`~${Math.ceil(r)} detik lagi`:`~${Math.ceil(r/60)} menit lagi` }

  // backend thumbs + pageCount (reliable, no CDN worker)
  useEffect(()=>{
    if(!fileId) return
    let cancelled=false
    const load=async()=>{
      try{
        const info=await api.get(`/api/files/${fileId}/info`)
        if(cancelled) return
        const pages=info.data.pages || 1
        setPageCount(pages)
        // fetch thumbs via backend (PyMuPDF) — fast & no worker
        const urls:string[]=[]
        for(let i=1;i<=pages;i++){
          try{
            const r=await api.get(`/api/files/${fileId}/thumb/${i}`, {responseType:'blob'})
            const url=URL.createObjectURL(r.data)
            urls.push(url)
          }catch{
            urls.push("")
          }
        }
        if(!cancelled) setThumbs(urls)
      }catch(e){
        console.error("backend thumb", e)
      }
    }
    setThumbs([])
    load()
    return()=>{ cancelled=true }
  },[fileId])

  // pdfjs fallback (keep for offline backend fail) — also sets pageCount if backend not yet
  useEffect(()=>{
    if(!fileObj || pageCount>0) return
    let cancelled=false
    const render=async()=>{
      try{
        const pdfjs:any = await import('pdfjs-dist')
        try{ pdfjs.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.js` }catch{}
        const url=URL.createObjectURL(fileObj)
        const doc=await pdfjs.getDocument(url).promise
        if(cancelled) return
        setPageCount(doc.numPages)
        URL.revokeObjectURL(url)
      }catch{}
    }
    render()
    return()=>{ cancelled=true }
  },[fileObj, pageCount])

  const upload=async(files:FileList)=>{
    const f=files[0]; if(!f) return
    setUploading(true); setUploadProgress(0); setUploadDone(false)
    setFileName(f.name)
    setFileObj(f)
    const fd=new FormData(); fd.append('file',f)
    const r=await api.post('/api/files',fd,{headers:{'Content-Type':'multipart/form-data'}, onUploadProgress:(e:any)=>{ const p=e.total?Math.round(e.loaded*100/e.total):0; setUploadProgress(p) }})
    setFileId(r.data.id)
    setUploading(false); setUploadProgress(100); setUploadDone(true); setTimeout(()=>setUploadDone(false),2000)
    setParts([{id:1,pages:[],rangeInput:""}])
    setActivePart(0)
  }

  const togglePage=(n:number)=>{
    setParts(prev=>{
      const cp=[...prev]
      const p=cp[activePart]
      if(!p) return prev
      const has=p.pages.includes(n)
      let np:number[]
      if(has) np=p.pages.filter(x=>x!==n)
      else {
        // remove from other parts if already assigned? keep single assignment
        // remove from others
        cp.forEach((part,i)=>{ if(i!==activePart) part.pages=part.pages.filter(x=>x!==n) })
        np=[...p.pages, n].sort((a,b)=>a-b)
      }
      p.pages=np
      p.rangeInput=pagesToRange(np)
      if(p.rangeInput==="—") p.rangeInput=""
      return cp
    })
  }

  const applyRange=(idx:number)=>{
    const p=parts[idx]
    const parsed=parseRange(p.rangeInput, pageCount)
    // remove those pages from other parts
    setParts(prev=>{
      const cp=prev.map(x=>({...x, pages:[...x.pages], rangeInput:x.rangeInput}))
      // clear parsed pages from others
      cp.forEach((part,i)=>{ if(i!==idx) part.pages=part.pages.filter(x=>!parsed.includes(x)) })
      cp[idx].pages=parsed
      cp[idx].rangeInput=parsed.length? pagesToRange(parsed):""
      return cp
    })
  }

  const addPart=()=>{
    setParts(prev=>[...prev, {id: prev.length+1, pages:[], rangeInput:""}])
    setActivePart(parts.length)
  }
  const reset=()=>{
    setParts([{id:1,pages:[],rangeInput:""}]); setActivePart(0)
  }

  const totalAssigned=new Set(parts.flatMap(p=>p.pages)).size

  const process=async()=>{
    if(!fileId) return alert("Upload PDF dulu")
    if(totalAssigned===0) return alert("Pilih minimal 1 halaman")
    const payloadParts=parts.filter(p=>p.pages.length>0).map(p=>({pages:p.pages}))
    if(payloadParts.length===0) return alert("Isi rentang atau klik halaman")
    const r=await api.post('/api/jobs',{tool:'split', file_id:fileId, params:{parts: payloadParts, mode:'parts'}})
    setJob(r.data); setJobStart(Date.now()); poll(r.data.id)
  }
  const poll=(jid:string)=>{
    pollRef.current && clearInterval(pollRef.current)
    pollRef.current=setInterval(async()=>{
      const r=await api.get(`/api/jobs/${jid}`)
      setJob(r.data); setProgress(`${r.data.status} ${r.data.progress}% ${r.data.message||''}`)
      if(['completed','failed','cancelled'].includes(r.data.status)){
        clearInterval(pollRef.current)
      }
    },800)
  }
  const download=async()=>{
    const r=await api.get(`/api/jobs/${job.id}/download`,{responseType:'blob'})
    const cd=(r.headers['content-disposition'] as string)||""
    const m=cd.match(/filename="?([^"]+)"?/)
    const fname=m?m[1]:`split_${fileName}`
    const url=URL.createObjectURL(r.data); const a=document.createElement('a'); a.href=url; a.download=fname; a.click()
    setTimeout(()=>URL.revokeObjectURL(url),5000)
  }

  const onDrop=(e:React.DragEvent)=>{
    e.preventDefault()
    if(e.dataTransfer.files.length) upload(e.dataTransfer.files)
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6">
      <button onClick={()=>navigate(-1)} className="inline-flex items-center gap-1.5 text-sm text-slate-600 hover:text-slate-900 mb-3"><ArrowLeft size={16}/> Kembali</button>
      <Link to="/dashboard" className="ml-3 text-sm text-brand-600 hover:underline">ke Dashboard</Link>
      {/* Upload zone */}
      <div
        onDragOver={e=>e.preventDefault()}
        onDrop={onDrop}
        onClick={()=>inputRef.current?.click()}
        className="border-2 border-dashed border-rose-300 rounded-2xl bg-white p-8 text-center cursor-pointer hover:bg-rose-50/40 transition"
      >
        <div className="text-sm font-medium text-slate-800">Pilih PDF untuk dipisah</div>
        <div className="text-xs text-slate-500 mt-1">drag & drop atau klik</div>
        {fileName ? (
          <div className="flex items-center justify-center gap-2 mt-2">
            <span className="text-xs text-rose-600 font-medium">✓ {fileName} · {pageCount||'?'} halaman</span>
            <button
              onClick={async(e)=>{
                e.stopPropagation()
                if(fileId) try{ await api.delete(`/api/files/${fileId}`) }catch{}
                setFileId(null); setFileName(""); setFileObj(null); setPageCount(0); setThumbs([]); setParts([{id:1,pages:[],rangeInput:""}]); setActivePart(0)
              }}
              className="w-5 h-5 rounded-full bg-white border border-rose-200 text-rose-600 grid place-items-center text-xs hover:bg-rose-50"
              title="Hapus file"
            >×</button>
          </div>
        ) : (
          <div className="text-xs text-slate-400 mt-2">Belum ada file</div>
        )}
        <input ref={inputRef} type="file" accept=".pdf" className="hidden" onChange={e=>e.target.files&&upload(e.target.files)}/>
        {uploading && (
          <div className="mt-3">
            <div className="flex justify-between text-xs mb-1"><span className="text-slate-500">Upload</span><span className="font-medium">{uploadProgress}%</span></div>
            <div className="h-2 bg-slate-100 rounded-full overflow-hidden"><div className="h-full bg-brand-600 transition-all" style={{width:`${uploadProgress}%`}}/></div>
          </div>
        )}
        {!uploading && uploadDone && <div className="mt-2 text-xs font-medium text-emerald-600">✓ Upload selesai</div>}
      </div>

      {pageCount>0 && (
        <>
          <div className="text-xs font-medium mt-6 mb-2">Klik halaman → masuk ke <span className="text-rose-600">Part {activePart+1}</span></div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {Array.from({length:pageCount},(_,i)=>i+1).map(n=>{
              const inActive=parts[activePart]?.pages.includes(n)
              const inAny=parts.some(p=>p.pages.includes(n))
              const ownerIdx=parts.findIndex(p=>p.pages.includes(n))
              return (
                <button key={n} onClick={()=>togglePage(n)} className={`relative bg-white rounded-xl border-2 overflow-hidden text-left group ${inActive?'border-rose-400 shadow-md':'border-slate-200 hover:border-slate-300'} ${inAny && !inActive ? 'opacity-60':''}`}>
                  <span className={`absolute top-1.5 left-1.5 w-5 h-5 rounded-md flex items-center justify-center text-[11px] font-bold text-white ${inActive?'bg-rose-600':'bg-slate-700'}`}>{n}</span>
                  {ownerIdx!==-1 && ownerIdx!==activePart && <span className="absolute top-1.5 right-1.5 text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 border border-amber-200">P{ownerIdx+1}</span>}
                  <div className="aspect-[0.71] bg-slate-50 flex items-center justify-center overflow-hidden">
                    {thumbs[n-1] ? <img src={thumbs[n-1]} alt={`p${n}`} className="w-full h-full object-contain"/> : <span className="text-xs text-slate-400">Hal {n}</span>}
                  </div>
                </button>
              )
            })}
          </div>

          {/* Konfigurasi File */}
          <div className="mt-6 bg-white rounded-2xl border p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-sm">Konfigurasi File</h3>
              <div className="flex gap-2">
                <button onClick={addPart} className="px-3 py-1.5 rounded-full bg-rose-600 text-white text-xs font-medium">+ Part baru</button>
                <button onClick={reset} className="px-3 py-1.5 rounded-full bg-slate-100 text-slate-700 text-xs">Reset</button>
              </div>
            </div>
            <div className="mt-4 space-y-3">
              {parts.map((part, idx)=>(
                <div key={part.id} onClick={()=>setActivePart(idx)} className={`rounded-xl border p-3 cursor-pointer ${idx===activePart?'bg-rose-50 border-rose-200':'bg-slate-50 border-slate-200'}`}>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-500">#{part.id}</span>
                    <span className="font-medium text-sm flex-1">Part {part.id}</span>
                    <span className="text-xs text-slate-500">{part.pages.length} hlm</span>
                  </div>
                  <div className="flex gap-2 mt-2">
                    <span className="text-xs text-slate-500 px-2 py-2">Rentang</span>
                    <input
                      placeholder="mis. 1-5, 8"
                      value={part.rangeInput}
                      onChange={e=>setParts(prev=>{ const cp=[...prev]; cp[idx].rangeInput=e.target.value; return cp })}
                      onClick={e=>e.stopPropagation()}
                      className="flex-1 px-3 py-1.5 rounded-lg border text-sm"
                    />
                    <button onClick={(e)=>{ e.stopPropagation(); applyRange(idx)}} className="px-3 py-1.5 rounded-lg bg-white border text-xs font-medium">Pakai</button>
                  </div>
                  {part.pages.length>0 && <div className="text-xs text-slate-500 mt-1">{pagesToRange(part.pages)}</div>}
                </div>
              ))}
            </div>
            <p className="text-xs text-slate-400 mt-3">Isi manual dengan klik halaman, atau ketik rentang lalu “Pakai”. Nama tiap Part = nama file PDF (zip kalau &gt;1 Part).</p>
          </div>

          <div className="flex flex-col items-center mt-6 w-full max-w-md mx-auto">
            <button onClick={process} className="px-8 py-2.5 bg-red-600 hover:bg-red-700 text-white rounded-full text-sm font-semibold shadow">Proses & Download</button>
            {job && (
              <div className="mt-3 w-full bg-white border rounded-xl p-3">
                <div className="flex justify-between text-xs"><span className="font-medium">{job.status}</span><span className="font-bold text-brand-600">{job.progress}%</span></div>
                <div className="h-2 bg-slate-100 rounded-full overflow-hidden mt-1"><div className={`h-full transition-all ${job.status==='completed'?'bg-emerald-500':job.status==='failed'?'bg-rose-500':'bg-brand-600'}`} style={{width:`${job.progress}%`}}/></div>
                <div className="flex justify-between mt-1 text-xs"><span className="text-slate-500">{job.status==='processing'?'Processing':progress}</span><span className="text-slate-400">{job.status==='processing'?fmtETA(jobStart, job.progress):''}</span></div>
                <div className="text-[11px] text-slate-400 mt-1">{job.status==='processing'?'Upload selesai ✓ • Processing...':job.status==='completed'?'Upload selesai ✓ • Selesai':''}</div>
                {job.error && <pre className="text-xs text-rose-600 whitespace-pre-wrap mt-2 bg-rose-50 p-2 rounded-lg">{job.error.slice(0,600)}</pre>}
                {job.status==='completed' && <button onClick={download} className="mt-2 w-full py-2 bg-emerald-600 text-white rounded-full text-xs">Download Hasil</button>}
                {job.status==='completed' && <QuickNext current="split" />}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}

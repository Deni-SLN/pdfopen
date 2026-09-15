import { useState, useRef } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { api } from '../lib/api'
import { QuickNext } from '../components/QuickNext'
import { ArrowLeft } from 'lucide-react'

export function MergeTool(){
  const navigate=useNavigate()
  const [files,setFiles]=useState<{id:string,name:string,size:number}[]>([])
  const [thumbs,setThumbs]=useState<Record<string,string>>({})
  const [dragIdx,setDragIdx]=useState<number|null>(null)
  const [job,setJob]=useState<any>(null)
  const [progress,setProgress]=useState("")
  const [uploading,setUploading]=useState(false)
  const [uploadProgress,setUploadProgress]=useState(0)
  const [uploadDone,setUploadDone]=useState(false)
  const [jobStart,setJobStart]=useState<number|null>(null)
  const inputRef=useRef<HTMLInputElement>(null)
  const pollRef=useRef<any>(null)
  const fmtETA=(s:number|null,p:number)=>{ if(!s||p<=0||p>=100) return ""; const e=(Date.now()-s)/1000; const t=e*100/p; const r=Math.max(0,t-e); return r<60?`~${Math.ceil(r)} detik lagi`:`~${Math.ceil(r/60)} menit lagi` }

  const fetchThumb=async(fid:string)=>{
    try{
      const r=await api.get(`/api/files/${fid}/thumb/1`, {responseType:'blob'})
      const url=URL.createObjectURL(r.data)
      setThumbs(prev=>({...prev, [fid]:url}))
    }catch{
      // fallback no thumb
    }
  }

  const upload=async(list:FileList)=>{
    setUploading(true); setUploadProgress(0); setUploadDone(false)
    const newFiles:typeof files=[] 
    const arr=Array.from(list)
    for(let idx=0; idx<arr.length; idx++){
      const f=arr[idx]
      const fd=new FormData(); fd.append('file',f)
      const r=await api.post('/api/files',fd,{headers:{'Content-Type':'multipart/form-data'}, onUploadProgress:(e:any)=>{ const p=e.total?Math.round(e.loaded*100/e.total):0; const overall=Math.round((idx + p/100)/arr.length*100); setUploadProgress(overall) }})
      const rec={id:r.data.id,name:r.data.original_name,size:r.data.size}
      newFiles.push(rec)
      fetchThumb(rec.id)
    }
    setFiles(prev=>[...prev, ...newFiles])
    setUploading(false); setUploadProgress(100); setUploadDone(true); setTimeout(()=>setUploadDone(false),2000)
  }

  const onDrop=(e:React.DragEvent)=>{
    e.preventDefault()
    if(e.dataTransfer.files.length) upload(e.dataTransfer.files)
  }

  const move=(from:number, to:number)=>{
    if(from===to) return
    setFiles(prev=>{
      const a=[...prev]
      const [m]=a.splice(from,1)
      a.splice(to,0,m)
      return a
    })
  }

  const remove=async(idx:number)=>{
    const fid=files[idx].id
    try{ await api.delete(`/api/files/${fid}`) }catch{}
    setFiles(prev=>prev.filter((_,i)=>i!==idx))
    setThumbs(prev=>{ const c={...prev}; delete c[fid]; return c })
  }

  const process=async()=>{
    if(files.length<2) return alert("Upload minimal 2 PDF untuk digabung")
    const r=await api.post('/api/jobs',{tool:'merge', params:{file_ids: files.map(f=>f.id)}, file_ids: files.map(f=>f.id), file_id: files[0].id})
    setJob(r.data); setJobStart(Date.now()); poll(r.data.id)
  }
  const poll=(jid:string)=>{
    pollRef.current && clearInterval(pollRef.current)
    pollRef.current=setInterval(async()=>{
      const r=await api.get(`/api/jobs/${jid}`)
      setJob(r.data); setProgress(`${r.data.status} ${r.data.progress}%`)
      if(['completed','failed','cancelled'].includes(r.data.status)) clearInterval(pollRef.current)
    },800)
  }
  const download=async()=>{
    const r=await api.get(`/api/jobs/${job.id}/download`,{responseType:'blob'})
    const cd=(r.headers['content-disposition'] as string)||""
    const m=cd.match(/filename="?([^"]+)"?/)
    const fname=m?m[1]:`merged.pdf`
    const url=URL.createObjectURL(r.data); const a=document.createElement('a'); a.href=url; a.download=fname; a.click()
    setTimeout(()=>URL.revokeObjectURL(url),5000)
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6">
      <button onClick={()=>navigate(-1)} className="inline-flex items-center gap-1.5 text-sm text-slate-600 hover:text-slate-900 mb-3"><ArrowLeft size={16}/> Kembali</button>
      <Link to="/dashboard" className="ml-3 text-sm text-brand-600 hover:underline">ke Dashboard</Link>
      <div
        onDragOver={e=>e.preventDefault()}
        onDrop={onDrop}
        onClick={()=>inputRef.current?.click()}
        className="border-2 border-dashed border-violet-300 rounded-2xl bg-white p-8 text-center cursor-pointer hover:bg-violet-50/40 transition"
      >
        <div className="text-sm font-semibold text-slate-800">Gabung PDF — susun urutan</div>
        <div className="text-xs text-slate-500 mt-1">drag & drop atau klik — upload beberapa PDF lalu drag untuk susun ulang (ala ilovepdf)</div>
        <div className="text-xs text-violet-600 mt-2 font-medium">{files.length>0 ? `${files.length} file siap • drag kartu untuk urutkan` : 'Belum ada file'}</div>
        <input ref={inputRef} type="file" accept=".pdf" multiple className="hidden" onChange={e=>e.target.files&&upload(e.target.files)}/>
        {uploading && (
          <div className="mt-3 max-w-sm mx-auto">
            <div className="flex justify-between text-xs mb-1"><span className="text-slate-500">Upload</span><span className="font-medium">{uploadProgress}%</span></div>
            <div className="h-2 bg-slate-100 rounded-full overflow-hidden"><div className="h-full bg-violet-600 transition-all" style={{width:`${uploadProgress}%`}}/></div>
          </div>
        )}
        {!uploading && uploadDone && <div className="mt-2 text-xs font-medium text-emerald-600">✓ Upload selesai</div>}
      </div>

      {files.length>0 && (
        <>
          <div className="mt-6 grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {files.map((f, idx)=>(
              <div
                key={f.id}
                draggable
                onDragStart={()=>setDragIdx(idx)}
                onDragOver={e=>e.preventDefault()}
                onDrop={()=>{ if(dragIdx!==null) move(dragIdx, idx); setDragIdx(null)}}
                className={`bg-white rounded-2xl border-2 p-3 flex gap-3 items-center cursor-grab active:cursor-grabbing ${dragIdx===idx?'border-violet-400 opacity-60':'border-slate-200 hover:border-violet-300'} `}
              >
                <div className="flex flex-col items-center gap-1">
                  <span className="w-6 h-6 rounded-full bg-violet-600 text-white text-xs font-bold grid place-items-center">{idx+1}</span>
                  <span className="text-[10px] text-slate-400">drag</span>
                </div>
                <div className="w-20 h-28 bg-slate-50 rounded-xl border overflow-hidden flex-shrink-0">
                  {thumbs[f.id] ? <img src={thumbs[f.id]} alt={f.name} className="w-full h-full object-contain"/> : <div className="w-full h-full grid place-items-center text-xs text-slate-400">PDF</div>}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">{f.name}</div>
                  <div className="text-xs text-slate-500">{(f.size/1024).toFixed(1)} KB</div>
                  <div className="flex gap-1 mt-1">
                    <button onClick={e=>{e.stopPropagation(); if(idx>0) move(idx, idx-1)}} className="px-2 py-1 text-xs border rounded-lg">↑</button>
                    <button onClick={e=>{e.stopPropagation(); if(idx<files.length-1) move(idx, idx+1)}} className="px-2 py-1 text-xs border rounded-lg">↓</button>
                    <button onClick={e=>{e.stopPropagation(); remove(idx)}} className="px-2 py-1 text-xs bg-rose-50 border border-rose-200 text-rose-600 rounded-lg">Hapus</button>
                  </div>
                </div>
              </div>
            ))}
            <button onClick={()=>inputRef.current?.click()} className="rounded-2xl border-2 border-dashed border-slate-300 p-6 grid place-items-center text-sm text-slate-500 hover:bg-slate-50">
              + Tambah PDF
            </button>
          </div>

          <div className="mt-6 bg-white rounded-2xl border p-4 flex items-center justify-between">
            <div className="text-sm"><span className="font-semibold">{files.length}</span> file • urutan saat ini: <span className="font-mono text-xs">{files.map((_,i)=>i+1).join(' → ')}</span></div>
            <button onClick={()=>setFiles([])} className="px-3 py-1.5 rounded-full bg-slate-100 text-xs">Reset</button>
          </div>

          <div className="flex flex-col items-center mt-6 w-full max-w-md mx-auto">
            <button onClick={process} className="px-8 py-2.5 bg-violet-600 hover:bg-violet-700 text-white rounded-full text-sm font-semibold shadow">Gabung & Download</button>
            {job && (
              <div className="mt-3 w-full bg-white border rounded-xl p-3">
                <div className="flex justify-between text-xs"><span className="font-medium">{job.status}</span><span className="font-bold text-violet-600">{job.progress}%</span></div>
                <div className="h-2 bg-slate-100 rounded-full overflow-hidden mt-1"><div className={`h-full transition-all ${job.status==='completed'?'bg-emerald-500':'bg-violet-600'}`} style={{width:`${job.progress}%`}}/></div>
                <div className="flex justify-between mt-1 text-xs"><span className="text-slate-500">{job.status==='processing'?'Processing':progress}</span><span className="text-slate-400">{job.status==='processing'?fmtETA(jobStart, job.progress):''}</span></div>
                <div className="text-[11px] text-slate-400 mt-1">{job.status==='processing'?'Upload selesai ✓ • Processing...':job.status==='completed'?'Upload selesai ✓ • Selesai':''}</div>
                {job.error && <pre className="text-xs text-rose-600 whitespace-pre-wrap mt-2 bg-rose-50 p-2 rounded-lg">{job.error.slice(0,600)}</pre>}
                {job.status==='completed' && <button onClick={download} className="mt-2 w-full py-2 bg-emerald-600 text-white rounded-full text-xs">Download</button>}
                {job.status==='completed' && <QuickNext current="merge" />}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}

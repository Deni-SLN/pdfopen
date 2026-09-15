import { Link } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { toolsList } from '../lib/api'
import { Combine, Scissors, Copy, Trash2, RotateCw, GripVertical, Minimize2, Image as ImageIcon, FileImage, Lock, LockOpen, Droplet, Eraser, Hash, Table2, FileText, Code2, Music, Video, Shield, PenTool, Type, ImageOff, KeyRound, ShieldCheck, Scan, ImagePlus, RefreshCw, Crop, Wrench, Layers, GitCompare, EyeOff, Images, Stamp, Paperclip, Info, FileCheck, Check, XCircle, Shuffle, LayoutDashboard, Maximize, Palette, BookOpen, SquarePen, Tag, Contrast } from 'lucide-react'

const iconMap: Record<string, any> = {
  Combine, Scissors, Copy, Trash: Trash2, Trash2, RotateCw, Grip: GripVertical, GripVertical, Minimize2, Image: ImageIcon, FileImage, Lock, Unlock: LockOpen, LockOpen, Droplet, Eraser, Hash, Table: Table2, Table2, FileText, Code: Code2, Code2, Music, Video, Shield, Pen: PenTool, PenTool, Type, ImageOff, Key: KeyRound, KeyRound, ShieldCheck, Scan, ImagePlus, RefreshCw, Crop, Wrench, Layers, GitCompare, EyeOff, Images, Stamp, Paperclip, Info, FileInfo: FileCheck, FileCheck, Check, XCircle, Shuffle, Layout: LayoutDashboard, LayoutDashboard, Maximize, Palette, Book: BookOpen, BookOpen, Edit: SquarePen, SquarePen, Tag, Contrast,
}

const cats = [
  {id:'all', label:'All Tools', dot:'', count:0},
  {id:'pdf-tools', label:'PDF Tools', dot:'bg-violet-500', count:0},
  {id:'convert', label:'Convert', dot:'bg-blue-500', count:0},
  {id:'security', label:'Security', dot:'bg-rose-500', count:0},
  {id:'edit', label:'Edit', dot:'bg-amber-500', count:0},
  {id:'document', label:'Document', dot:'bg-cyan-500', count:0},
  {id:'media', label:'Media', dot:'bg-orange-500', count:0},
]
// mapping new Stirling tools to our tab ids (keep design unchanged)
const toolCat: Record<string,string> = {
  'merge':'pdf-tools','split':'pdf-tools','extract-pages':'pdf-tools','delete-pages':'pdf-tools','rotate':'pdf-tools','reorder':'pdf-tools','compress':'pdf-tools','pdf-to-csv':'pdf-tools','pdf-to-excel':'pdf-tools','remove-blanks':'pdf-tools','reorganize-pages':'pdf-tools','page-layout':'pdf-tools','scale-pages':'pdf-tools','booklet-imposition':'pdf-tools','pdf-to-single-page':'pdf-tools','repair':'pdf-tools','auto-rename':'pdf-tools','get-pdf-info':'pdf-tools','compare':'pdf-tools','extract-images':'pdf-tools','overlay-pdfs':'pdf-tools',
  'pdf-to-image':'convert','image-to-pdf':'convert','pdf-to-excel-cam':'convert',
  'protect':'security','unlock':'security','cert-sign':'security','sign':'security','change-permissions':'security','sanitize':'security','redact':'security','validate-signature':'security','remove-cert-sign':'security','unlock-pdf-forms':'security','show-js':'security','change-permissions':'security',
  'watermark':'edit','page-numbers':'edit','add-text':'edit','remove-annotations':'edit','remove-image':'edit','add-image':'edit','crop':'edit','flatten':'edit','add-stamp':'edit','add-attachments':'edit','change-metadata':'edit','replace-color':'edit','pdf-text-editor':'edit','scanner-effect':'edit','adjust-contrast':'edit','auto-rotate':'edit',
  'md-to-pdf':'document','html-to-pdf':'document',
  'mp3-trim':'media','video-downloader':'media',
  'ocr':'pdf-tools','add-attachments':'edit','booklet-imposition':'pdf-tools'
}
function catFor(id:string){ 
  // fallback to toolsList cat mapping
  const t = toolsList.find(x=>x.id===id) as any
  if(t){
    if(['Organize','Compress','Data'].includes(t.cat)) return 'pdf-tools'
    if(t.cat==='Convert') return 'convert'
    if(t.cat==='Security') return 'security'
    if(t.cat==='Edit') return 'edit'
    if(t.cat==='Document') return 'document'
    if(t.cat==='Media') return 'media'
  }
  return toolCat[id]||'pdf-tools' 
}

export function Dashboard(){
  const [active,setActive]=useState('all')
  const [query,setQuery]=useState('')
  useEffect(()=>{
    const h=(e:any)=>setQuery(e.detail||'')
    window.addEventListener('sofia-search', h as any); return()=>window.removeEventListener('sofia-search', h as any)
  },[])

  const filtered = toolsList.filter(t=>{
    const catOk = active==='all' || catFor(t.id)===active
    if(!catOk) return false
    if(!query) return true
    const q=query.toLowerCase()
    return t.name.toLowerCase().includes(q) || t.id.includes(q)
  })

  // group by cat for display (when all, show each section separated like template, else single)
  const groups = active==='all' ? ['pdf-tools','convert','security','edit','document','media'] : [active]

  return (
    <div className="w-full">
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-2 w-full">
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-brand-600 via-indigo-600 to-brand-700 p-8 sm:p-10 text-white shadow-xl shadow-brand-700/15">
          <div className="absolute -right-16 -top-16 w-80 h-80 bg-white/10 rounded-full blur-2xl pointer-events-none"></div>
          <div className="absolute -left-12 -bottom-12 w-64 h-64 bg-indigo-400/20 rounded-full blur-xl pointer-events-none"></div>
          <div className="relative z-10 max-w-3xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/15 border border-white/20 text-xs font-medium text-white mb-4 backdrop-blur-sm"><span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span> Self-Hosted • 100% Private Processing</div>
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight mb-3">Sofia Tools v2</h1>
            <p className="text-white/90 text-sm sm:text-base leading-relaxed max-w-2xl">Modern PDF tools, self-hosted, private, and simple. Drag &amp; drop → preview → configure → process → download.</p>
            <div className="mt-6 flex flex-wrap items-center gap-3 pt-4 border-t border-white/15 text-xs text-white/80">
              <div className="flex items-center gap-1.5"><svg className="w-4 h-4 text-emerald-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}/></svg> No Third-Party Tracking</div><span className="text-white/40">•</span>
              <div className="flex items-center gap-1.5"><svg className="w-4 h-4 text-emerald-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}/></svg> In-Memory Processing</div><span className="text-white/40">•</span>
              <div className="flex items-center gap-1.5"><svg className="w-4 h-4 text-emerald-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}/></svg> Proxmox &amp; Docker Ready</div>
            </div>
          </div>
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 w-full">
        <div className="relative bg-white/70 backdrop-blur-md rounded-2xl p-2 sm:p-2.5 border border-slate-200 shadow-xs">
          <div className="flex items-center gap-2 overflow-x-auto no-scrollbar scroll-smooth py-0.5 px-0.5" role="tablist">
            {cats.map(c=>{
              const activeTab = c.id===active
              return (
                <button key={c.id} onClick={()=>setActive(c.id)} aria-selected={activeTab} className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold whitespace-nowrap transition-all ${activeTab?'bg-brand-600 text-white shadow-sm shadow-brand-500/25':'text-slate-600 hover:text-slate-900 hover:bg-slate-100/80'}`}>
                  {c.dot && <span className={`w-2 h-2 rounded-full ${c.dot}`}></span>}
                  {c.label}
                  <span className={`px-2 py-0.5 rounded-full text-[11px] font-bold ${activeTab?'bg-white/20 text-white':'bg-slate-100 text-slate-600'}`}>{c.id==='all'? filtered.length : toolsList.filter(t=>catFor(t.id)===c.id).length}</span>
                </button>
              )
            })}
          </div>
        </div>
      </section>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 w-full flex-1 space-y-10">
        {groups.map(g=>{
          const label = cats.find(c=>c.id===g)?.label || g
          const dot = cats.find(c=>c.id===g)?.dot
          const list = filtered.filter(t=>catFor(t.id)===g)
          if(list.length===0) return null
          return (
            <section key={g} className="space-y-3">
              <div className="flex items-center justify-between pb-1 border-b border-slate-200">
                <div className="flex items-center gap-2"><span className={`w-2.5 h-2.5 rounded-full ${dot}`}></span><h2 className="text-sm font-bold tracking-wider text-slate-600 uppercase">{label}</h2></div>
                <span className="text-xs text-slate-400 font-medium">{list.length} Tools</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {list.map(t=>{
                  const Icon = iconMap[(t as any).icon] || null
                  return (
                  <Link key={t.id} to={`/tool/${t.id}`} className="tool-card group block p-4 bg-white rounded-2xl border border-slate-200 hover:border-violet-300 shadow-2xs">
                    <div className="flex items-center justify-between mb-3">
                      <div className="w-9 h-9 rounded-xl bg-violet-50 text-violet-700 flex items-center justify-center border border-violet-100 group-hover:bg-violet-600 group-hover:text-white transition-colors">
                        {Icon ? <Icon size={16} /> : <span className="text-sm font-bold">{t.name[0]}</span>}
                      </div>
                      <span className="text-[11px] font-mono text-slate-400 group-hover:text-violet-600 bg-slate-50 group-hover:bg-violet-50 px-2 py-0.5 rounded border border-slate-100 transition-colors">{t.id}</span>
                    </div>
                    <h3 className="font-semibold text-slate-900 text-sm group-hover:text-violet-700 transition-colors">{t.name}</h3>
                    <p className="text-xs text-slate-500 mt-1 leading-snug line-clamp-2">{(t as any).desc || catDesc(t.id)}</p>
                  </Link>
                )})}
              </div>
            </section>
          )
        })}
        {filtered.length===0 && <p className="text-center text-sm text-slate-500 py-10">No tools match “{query}”</p>}
      </main>
    </div>
  )
}
function catDesc(id:string){
  const m:Record<string,string>={
    'merge':'Combine multiple PDF documents into a unified, clean file.',
    'split':'Separate pages into independent files.',
    'extract-pages':'Extract specific pages into a new document.',
    'delete-pages':'Remove unnecessary pages cleanly.',
    'rotate':'Rotate scans by 90°, 180°, 270°.',
    'reorder':'Drag-and-drop board to restructure pages.',
    'compress':'Optimize file weight while keeping clarity.',
    'pdf-to-csv':'Detect tables and export to CSV.',
    'pdf-to-excel':'Convert tables into XLSX workbooks.',
    'pdf-to-excel-cam':'Detail CAM Prioritisasi: watermark dihapus otomatis, semua halaman digabung ke 1 sheet Excel (32 kolom baku).',
    'pdf-to-image':'Export pages as JPG/PNG.',
    'image-to-pdf':'Images to PDF.',
    'protect':'Add password.',
    'unlock':'Remove password.',
    'watermark':'Add text watermark.',
    'page-numbers':'Add page numbers.',
    'md-to-pdf':'Markdown to PDF.',
    'html-to-pdf':'HTML/CSS to PDF.',
    'mp3-trim':'Cut MP3 by time range.',
    'video-downloader':'Download video/MP3 from URL.',
    'pdf-text-editor':'Edit PDF text in-place.',
    'sanitize':'Remove hidden data from PDF.',
  }
  return m[id]||'Tool'
}

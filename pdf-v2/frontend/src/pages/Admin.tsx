import { useEffect, useState } from 'react'
import { api } from '../lib/api'

const fmt = (n:number) => new Intl.NumberFormat('id-ID').format(n ?? 0)
const fmtMB = (n:number) => `${fmt(n)} MB`

export function Admin(){
  const [stats,setStats]=useState<any>(null); const [jobs,setJobs]=useState<any[]>([]); const [users,setUsers]=useState<any[]>([]); const [storage,setStorage]=useState<any[]>([])
  const [period,setPeriod]=useState("all")
  const [retention,setRetention]=useState(1)
  const [form,setForm]=useState({identifier:"", password:"", role:"USER", quota_daily:100, max_file_mb:100})
  const [msg,setMsg]=useState("")
  const [edit,setEdit]=useState<any>(null)
  const [editForm,setEditForm]=useState<any>({})

  const load=async()=>{
    const s=await api.get(`/api/admin/stats?period=${period}`); setStats(s.data); setRetention(s.data.retention_hours)
    const j=await api.get('/api/admin/jobs'); setJobs(j.data)
    const u=await api.get('/api/users'); setUsers(u.data)
    const st=await api.get('/api/admin/storage'); setStorage(st.data)
  }
  useEffect(()=>{load().catch(console.error)},[period])

  const create=async(e:React.FormEvent)=>{
    e.preventDefault(); setMsg("")
    try{ await api.post('/api/users',{identifier:form.identifier, password:form.password, role:form.role, quota_daily:form.quota_daily, max_file_mb:form.max_file_mb}); setMsg("✅ User dibuat: "+form.identifier); setForm({identifier:"",password:"",role:"USER",quota_daily:100,max_file_mb:100}); load() } catch(ex:any){ setMsg("❌ "+(ex.response?.data?.detail||"Gagal")) }
  }
  const saveSettings=async()=>{
    await api.post('/api/admin/settings',{retention_hours: retention}); setMsg("✅ Retention disimpan "+retention+" jam"); load()
  }
  const doEdit=async()=>{
    if(!edit) return
    await api.patch(`/api/users/${edit.id}`, editForm); setEdit(null); load(); setMsg("✅ Edit disimpan")
  }
  const doReset=async(id:string)=>{
    if(!confirm("Reset password ke 12345678 dan wajib ganti saat login?")) return
    await api.post(`/api/users/${id}/reset-password`); load(); setMsg("✅ Password di-reset ke 12345678 (wajib ganti)")
  }
  const doDelete=async(id:string, name:string)=>{
    if(!confirm(`Hapus akun ${name}? Tidak bisa undo.`)) return
    await api.delete(`/api/users/${id}`); load(); setMsg("🗑️ User dihapus")
  }

  if(!stats) return <p className="p-8 text-center">Loading admin...</p>
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <h1 className="text-2xl font-bold tracking-tight">Admin Dashboard</h1>
      <p className="text-sm text-slate-500">Kelola user lokal, limit, retention, dan monitoring.</p>

      <div className="flex gap-2 mt-4 flex-wrap">
        {["1d","7d","30d","1y","all"].map(p=>(
          <button key={p} onClick={()=>setPeriod(p)} className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold border transition ${period===p?'bg-brand-600 text-white border-brand-600 shadow':'bg-white text-slate-600 hover:bg-slate-50'}`}>{p==="1d"?"1 hari":p==="7d"?"7 hari":p==="30d"?"1 bulan":p==="1y"?"1 tahun":"All"}</button>
        ))}
      </div>

      <div className="grid sm:grid-cols-4 gap-4 mt-6">
        <div className="bg-white rounded-2xl p-5 border shadow-2xs"><div className="text-xs font-medium text-slate-500">Total Users</div><div className="text-2xl font-bold mt-1">{stats.total_users}</div><div className="text-xs text-slate-400">Active {stats.active_users}</div></div>
        <div className="bg-white rounded-2xl p-5 border shadow-2xs"><div className="text-xs font-medium text-slate-500">File Uploaded</div><div className="text-2xl font-bold mt-1">{stats.files_count}</div><div className="text-xs text-brand-600 font-medium">{(stats.total_bytes/1024/1024).toFixed(2)} MB</div></div>
        <div className="bg-white rounded-2xl p-5 border shadow-2xs"><div className="text-xs font-medium text-slate-500">File Diproses</div><div className="text-2xl font-bold mt-1">{stats.jobs_today}</div><div className="text-xs text-slate-500">Completed {stats.jobs_completed} • <span className="text-rose-600">{stats.failed_jobs} failed</span></div></div>
        <div className="bg-white rounded-2xl p-5 border shadow-2xs"><div className="text-xs font-medium text-slate-500">Storage (disk)</div><div className="text-2xl font-bold mt-1">{(stats.storage_bytes/1024/1024).toFixed(1)} MB</div><div className="text-xs text-slate-500">Retention {stats.retention_hours} jam • {period}</div></div>
      </div>

      <div className="mt-6 bg-white rounded-2xl p-6 border shadow-2xs">
        <h3 className="font-semibold">Buat User Lokal</h3>
        <p className="text-xs text-slate-500">Tanpa email, contoh <b>DENI26</b> / <b>Ronaldo07@</b>. Username disimpan lowercase.</p>
        <form onSubmit={create} className="grid sm:grid-cols-6 gap-3 mt-4">
          <input placeholder="Username (DENI26)" value={form.identifier} onChange={e=>setForm({...form, identifier:e.target.value})} className="px-3 py-2.5 rounded-xl border border-slate-200 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none"/>
          <input placeholder="Password" type="password" value={form.password} onChange={e=>setForm({...form, password:e.target.value})} className="px-3 py-2.5 rounded-xl border border-slate-200 text-sm focus:border-brand-500 outline-none"/>
          <select value={form.role} onChange={e=>setForm({...form, role:e.target.value})} className="px-3 py-2.5 rounded-xl border text-sm"><option>USER</option><option>ADMIN</option></select>
          <input type="number" title="Limit file perhari" value={form.quota_daily} onChange={e=>setForm({...form, quota_daily:parseInt(e.target.value)||0})} className="px-3 py-2.5 rounded-xl border text-sm"/>
          <input type="number" title="Max MB per file" value={form.max_file_mb} onChange={e=>setForm({...form, max_file_mb:parseInt(e.target.value)||0})} className="px-3 py-2.5 rounded-xl border text-sm"/>
          <button className="px-4 py-2.5 bg-brand-600 text-white rounded-xl text-sm font-semibold hover:bg-brand-700">Buat</button>
        </form>
        {msg && <p className="text-sm mt-3 px-3 py-2 bg-slate-50 rounded-xl border">{msg}</p>}
      </div>

      <div className="mt-6 bg-white rounded-2xl p-6 border shadow-2xs flex flex-wrap gap-4 items-end">
        <div className="flex-1 min-w-[240px]">
          <h3 className="font-semibold text-sm">Auto-hapus file</h3>
          <p className="text-xs text-slate-500">Semua upload & hasil terhapus otomatis setelah N jam.</p>
        </div>
        <div className="flex gap-2 items-center">
          <input type="number" min={1} max={720} value={retention} onChange={e=>setRetention(parseInt(e.target.value)||1)} className="w-20 px-3 py-2 rounded-xl border text-sm"/>
          <span className="text-sm">jam</span>
          <button onClick={saveSettings} className="px-4 py-2 bg-slate-900 text-white rounded-xl text-sm font-medium">Simpan</button>
          <button onClick={async()=>{await api.post('/api/admin/cleanup'); load(); setMsg("✅ Cleanup dijalankan")}} className="px-4 py-2 bg-amber-500 text-white rounded-xl text-sm font-medium">Cleanup sekarang</button>
        </div>
      </div>

      <div className="mt-6 bg-white rounded-2xl p-6 border shadow-2xs">
        <h3 className="font-semibold">Storage Breakdown</h3>
        <div className="grid sm:grid-cols-3 gap-3 mt-3 text-sm">{storage.map((s:any)=><div key={s.dir} className="bg-slate-50 p-4 rounded-xl border"><div className="font-medium">{s.dir}</div><div className="text-xs text-slate-500">{s.files} files — {(s.bytes/1024/1024).toFixed(2)} MB</div></div>)}</div>
      </div>

      <div className="mt-6 bg-white rounded-2xl p-6 border shadow-2xs overflow-auto">
        <h3 className="font-semibold">Kelola Akun — Buat / Edit / Reset / Hapus</h3>
        <p className="text-xs text-slate-500">Reset = password jadi <code className="px-1 py-0.5 bg-slate-100 rounded">12345678</code> dan user wajib ganti saat login pertama.</p>
        <table className="w-full text-sm mt-4">
          <thead><tr className="text-xs text-slate-500 border-b"><th className="text-left py-2">Identifier</th><th>Role</th><th>Limit/hari</th><th>Max MB</th><th>Status</th><th className="text-right">Aksi</th></tr></thead>
          <tbody>{users.map((u:any)=>(
            <tr key={u.id} className="border-b last:border-0 hover:bg-slate-50/50">
              <td className="py-2.5"><div className="font-medium">{u.username || u.email}</div><div className="text-xs text-slate-400">{u.username?'local':'email'} • {new Date(u.created_at).toLocaleDateString()}</div></td>
              <td><span className={`px-2 py-1 rounded-full text-xs font-medium border ${u.role==='ADMIN'?'bg-amber-50 text-amber-700 border-amber-200':'bg-slate-100 text-slate-700'}`}>{u.role}</span>{u.must_change_password && <span className="ml-1 text-xs text-rose-600">• wajib ganti</span>}</td>
              <td className="text-center" title={`${u.quota_daily} file/hari`}>{fmt(u.quota_daily)}</td>
              <td className="text-center" title={`${u.max_file_mb||100} MB`}>{fmt(u.max_file_mb||100)}</td>
              <td><span className={`px-2 py-1 rounded-full text-xs ${u.is_active?'bg-emerald-50 text-emerald-700':'bg-slate-100 text-slate-500'}`}>{u.is_active?'active':'nonaktif'}</span></td>
              <td className="text-right">
                <div className="flex gap-1 justify-end flex-wrap">
                  <button onClick={()=>{ setEdit(u); setEditForm({identifier: u.username||u.email, role:u.role, quota_daily:u.quota_daily, max_file_mb:u.max_file_mb||100, is_active:u.is_active, password:""}) }} className="px-2.5 py-1 rounded-lg border text-xs hover:bg-white">Edit</button>
                  <button onClick={()=>doReset(u.id)} className="px-2.5 py-1 rounded-lg bg-amber-50 border border-amber-200 text-amber-700 text-xs">Reset</button>
                  <button onClick={()=>doDelete(u.id, u.username||u.email)} className="px-2.5 py-1 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs">Hapus</button>
                </div>
              </td>
            </tr>
          ))}</tbody>
        </table>
      </div>

      {edit && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm grid place-items-center p-4 z-50" onClick={()=>setEdit(null)}>
          <div onClick={e=>e.stopPropagation()} className="bg-white rounded-2xl p-6 w-full max-w-lg border shadow-xl">
            <h3 className="font-semibold">Edit Akun: {edit.username||edit.email}</h3>
            <div className="grid gap-3 mt-4">
              <input placeholder="Username / Email" value={editForm.identifier||""} onChange={e=>setEditForm({...editForm, identifier:e.target.value})} className="px-3 py-2.5 rounded-xl border text-sm"/>
              <div className="grid grid-cols-2 gap-3">
                <select value={editForm.role} onChange={e=>setEditForm({...editForm, role:e.target.value})} className="px-3 py-2.5 rounded-xl border text-sm"><option>USER</option><option>ADMIN</option></select>
                <select value={editForm.is_active ? "true":"false"} onChange={e=>setEditForm({...editForm, is_active:e.target.value==="true"})} className="px-3 py-2.5 rounded-xl border text-sm"><option value="true">Active</option><option value="false">Nonaktif</option></select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <label className="text-xs">Limit/hari<input type="number" value={editForm.quota_daily} onChange={e=>setEditForm({...editForm, quota_daily:parseInt(e.target.value)||0})} className="w-full mt-1 px-3 py-2 rounded-xl border text-sm"/></label>
                <label className="text-xs">Max MB<input type="number" value={editForm.max_file_mb} onChange={e=>setEditForm({...editForm, max_file_mb:parseInt(e.target.value)||0})} className="w-full mt-1 px-3 py-2 rounded-xl border text-sm"/></label>
              </div>
              <input placeholder="Password baru (kosongkan jika tidak ganti)" type="password" value={editForm.password||""} onChange={e=>setEditForm({...editForm, password:e.target.value})} className="px-3 py-2.5 rounded-xl border text-sm"/>
              <div className="flex gap-2 justify-end mt-2">
                <button onClick={()=>setEdit(null)} className="px-4 py-2 rounded-xl border text-sm">Batal</button>
                <button onClick={doEdit} className="px-4 py-2 bg-brand-600 text-white rounded-xl text-sm font-medium">Simpan</button>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="mt-6 bg-white rounded-2xl p-6 border shadow-2xs overflow-auto">
        <h3 className="font-semibold">Recent Jobs</h3>
        <table className="w-full text-sm mt-3"><thead><tr className="text-xs text-slate-500"><th className="text-left">Tool</th><th>Status</th><th>Progress</th></tr></thead><tbody>{jobs.slice(0,20).map((j:any)=><tr key={j.id} className="border-b"><td className="py-1">{j.tool}</td><td><span className={`px-2 py-0.5 rounded-full text-xs ${j.status==='completed'?'bg-emerald-50 text-emerald-700':j.status==='failed'?'bg-rose-50 text-rose-700':'bg-slate-100'}`}>{j.status}</span></td><td>{j.progress}%</td></tr>)}</tbody></table>
      </div>
    </div>
  )
}

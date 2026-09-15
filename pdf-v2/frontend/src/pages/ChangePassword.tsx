import { useState } from 'react'
import { api } from '../lib/api'
import { useStore } from '../lib/store'
import { useNavigate } from 'react-router-dom'

export function ChangePassword({forced=false}:{forced?:boolean}){
  const [oldPw,setOld]=useState('12345678')
  const [nw,setNw]=useState('')
  const [nw2,setNw2]=useState('')
  const [err,setErr]=useState('')
  const [ok,setOk]=useState('')
  const nav=useNavigate()
  const {user}=useStore()
  const submit=async(e:React.FormEvent)=>{
    e.preventDefault(); setErr(''); setOk('')
    if(nw!==nw2) { setErr('Konfirmasi password tidak cocok'); return }
    if(nw.length<8) { setErr('Minimal 8 karakter'); return }
    try{
      if(forced) await api.post('/api/auth/force-change',{new_password:nw})
      else await api.post('/api/auth/change-password',{old_password:oldPw, new_password:nw})
      setOk('Password berhasil diganti, silakan login kembali')
      setTimeout(()=>nav('/dashboard'), 1200)
    }catch(ex:any){ setErr(ex.response?.data?.detail||'Gagal') }
  }
  return (
    <div className="max-w-md mx-auto mt-10 bg-white rounded-2xl p-8 border shadow-sm">
      <h1 className="text-xl font-bold">{forced ? 'Wajib Ganti Password' : 'Ganti Password'}</h1>
      <p className="text-sm text-slate-500 mt-1">{forced ? 'Akun Anda di-reset ke 12345678. Silakan ganti sekarang.' : `User: ${(user as any)?.username || (user as any)?.email}`}</p>
      <form onSubmit={submit} className="mt-6 space-y-4">
        {!forced && <input placeholder="Password lama" type="password" value={oldPw} onChange={e=>setOld(e.target.value)} className="w-full px-4 py-2.5 rounded-xl border"/>}
        {forced && <input value="12345678" disabled className="w-full px-4 py-2.5 rounded-xl border bg-slate-100 text-slate-500"/>}
        <input placeholder="Password baru (min 8)" type="password" value={nw} onChange={e=>setNw(e.target.value)} className="w-full px-4 py-2.5 rounded-xl border"/>
        <input placeholder="Konfirmasi password baru" type="password" value={nw2} onChange={e=>setNw2(e.target.value)} className="w-full px-4 py-2.5 rounded-xl border"/>
        {err && <p className="text-sm text-red-600">{err}</p>}
        {ok && <p className="text-sm text-emerald-600">{ok}</p>}
        <button className="w-full py-2.5 bg-brand-600 text-white rounded-xl font-medium">Simpan Password</button>
      </form>
    </div>
  )
}

import { useState } from 'react'
import { api } from '../lib/api'
import { useStore } from '../lib/store'
import { useNavigate, Link } from 'react-router-dom'

export function Login(){
  const [ident,setIdent]=useState(''); const [password,setPassword]=useState(''); const [err,setErr]=useState(''); const nav=useNavigate(); const {setAuth}=useStore()
  const submit=async(e:React.FormEvent)=>{
    e.preventDefault(); setErr('')
    try{
      const r=await api.post('/api/auth/login',{identifier:ident, password})
      const u={...r.data.user, must_change_password: r.data.must_change_password || r.data.user.must_change_password}
      setAuth(r.data.access_token, u)
      if(u.must_change_password) nav('/force-change')
      else nav('/dashboard')
    } catch(ex:any){ setErr(ex.response?.data?.detail||'Login failed') }
  }
  return (
    <div className="max-w-md mx-auto mt-10 bg-white dark:bg-slate-900 rounded-2xl p-8 shadow-sm border border-slate-200 dark:border-slate-800">
      <h1 className="text-2xl font-bold">Login</h1>
      <p className="text-sm text-slate-500 mt-1">Opsional — tanpa login pun aplikasi bisa dipakai (kuota 5 proses/hari). Login untuk kuota lebih besar; admin unlimited.</p>
      <form onSubmit={submit} className="mt-6 space-y-4">
        <input placeholder="Username" value={ident} onChange={e=>setIdent(e.target.value)} className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-transparent"/>
        <input placeholder="Password" type="password" value={password} onChange={e=>setPassword(e.target.value)} className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-transparent"/>
        {err && <p className="text-sm text-red-600">{err}</p>}
        <button className="w-full py-2.5 bg-indigo-600 text-white rounded-xl font-medium">Login</button>
      </form>
      <Link to="/dashboard" className="block text-center text-sm text-slate-500 hover:text-slate-700 mt-4">Lanjut tanpa login →</Link>
    </div>
  )
}
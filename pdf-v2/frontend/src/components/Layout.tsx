import { Link, useNavigate } from 'react-router-dom'
import { useStore } from '../lib/store'
import { useState, useEffect } from 'react'

export function Layout({children}:{children:React.ReactNode}){
  const {user, logout, setAuth, token}=useStore() as any
  const nav=useNavigate()
  const [q,setQ]=useState("")
  useEffect(()=>{
    const ev=(e:KeyboardEvent)=>{ if((e.metaKey||e.ctrlKey) && e.key.toLowerCase()==='k'){ e.preventDefault(); document.getElementById('tool-search-input')?.focus() } }
    window.addEventListener('keydown',ev); return()=>window.removeEventListener('keydown',ev)
  },[])
  // refresh user from backend to avoid stale admin@test.com display
  useEffect(()=>{
    if(!token) return
    import('../lib/api').then(({api})=>{
      api.get('/api/auth/me').then(r=>{
        const fresh = r.data
        const identifier = (fresh as any).username || (fresh as any).email
        const stored = (user as any)?.username || (user as any)?.email
        if(identifier && identifier !== stored){
          setAuth(token, {...fresh, identifier})
        }
      }).catch(()=>{})
    })
  },[token])
  // expose search via custom event
  useEffect(()=>{ window.dispatchEvent(new CustomEvent('sofia-search',{detail:q})) },[q])
  // kuota harian (guest 5x, user sesuai kuota, admin unlimited)
  const [quota,setQuota]=useState<any>(null)
  useEffect(()=>{
    if(!token) return
    let alive=true
    const load=()=>{ import('../lib/api').then(({api})=>{
      api.get('/api/auth/quota').then(r=>{ if(alive) setQuota(r.data) }).catch(()=>{})
    })}
    load()
    const iv=setInterval(load, 15000)
    return()=>{ alive=false; clearInterval(iv) }
  },[token])
  const isGuest = !user || ((user as any).username||'').startsWith('guest-')

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col antialiased selection:bg-brand-500 selection:text-white" style={{fontFamily:'Inter, system-ui, sans-serif'}}>
      <header className="sticky top-0 z-40 bg-white/90 backdrop-blur-md border-b border-slate-200/80">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
          <Link to="/dashboard" className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-brand-600 to-indigo-500 flex items-center justify-center text-white font-bold text-lg shadow-sm shadow-brand-500/30">S</div>
            <span className="font-bold text-lg tracking-tight text-slate-900 flex items-center gap-1.5">Sofia Tools <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-brand-50 text-brand-700 border border-brand-200">v2</span></span>
          </Link>

          <div className="flex-1 max-w-md hidden md:block">
            <div className="relative">
              <svg className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" strokeLinecap="round" strokeLinejoin="round"/></svg>
              <input id="tool-search-input" value={q} onChange={e=>setQ(e.target.value)} placeholder="Search tools (e.g. merge, compress, protect)..." className="w-full bg-slate-100/70 hover:bg-slate-100 focus:bg-white text-sm pl-10 pr-12 py-2 rounded-xl border border-transparent focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 transition-all placeholder:text-slate-400 text-slate-800 outline-none"/>
              <kbd className="absolute right-3 top-1/2 -translate-y-1/2 font-mono text-[11px] font-medium text-slate-400 bg-white px-1.5 py-0.5 rounded border border-slate-200">⌘K</kbd>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            {user && <Link to="/dashboard" className="px-3.5 py-1.5 rounded-lg text-xs font-semibold text-slate-700 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 transition-colors">Dashboard</Link>}
            {user?.role==='ADMIN' && <Link to="/admin" className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-amber-50 text-amber-800 border border-amber-200"> <svg className="w-3.5 h-3.5 text-amber-600" fill="currentColor" viewBox="0 0 20 20"><path clipRule="evenodd" d="M10 1.944A11.954 11.954 0 012.166 5C2.056 5.649 2 6.319 2 7c0 5.225 3.34 9.67 8 11.317C14.66 16.67 18 12.225 18 7c0-.682-.057-1.35-.166-2.001A11.954 11.954 0 0110 1.944zM11 14a1 1 0 11-2 0 1 1 0 012 0zm0-7a1 1 0 10-2 0v3a1 1 0 102 0V7z" fillRule="evenodd"/></svg> Admin</Link>}
            {quota && !quota.unlimited && (
              <span className={`hidden sm:inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium border ${quota.remaining>0?'bg-emerald-50 text-emerald-700 border-emerald-200':'bg-rose-50 text-rose-700 border-rose-200'}`} title="Kuota proses hari ini">
                Kuota: {quota.remaining}/{quota.quota}
              </span>
            )}
            {quota?.unlimited && <span className="hidden sm:inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-medium bg-amber-50 text-amber-800 border border-amber-200">Unlimited</span>}
            <div className="flex items-center gap-2 pl-2 border-l border-slate-200">
              {user ? <>
                <div className="hidden lg:flex flex-col text-right"><span className="text-xs font-medium text-slate-700">{isGuest ? 'Tamu (5x/hari)' : ((user as any).username || (user as any).email || 'User')}</span></div>
                <div className="w-8 h-8 rounded-full bg-slate-200 border border-slate-300 flex items-center justify-center text-slate-600 text-xs font-bold">{isGuest?'T':((user as any).username||(user as any).email||'U')[0].toUpperCase()}</div>
              </> : <Link to="/login" className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-brand-600 text-white">Login</Link>}
            </div>
            {isGuest && <Link to="/login" className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-600 text-white hover:bg-brand-700">Login / Daftar</Link>}
            {user && <button aria-label="Sign Out" onClick={()=>{logout(); nav('/login')}} className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"><svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" strokeLinecap="round" strokeLinejoin="round"/></svg></button>}
          </div>
        </div>
      </header>
      <main className="flex-1 w-full">{children}</main>
      <footer className="border-t border-slate-200 bg-white py-8 mt-12 text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col md:flex-row items-center justify-between gap-4 text-center md:text-left">
          <div className="flex flex-col sm:flex-row items-center gap-2 sm:gap-3">
            <span className="font-semibold text-slate-700">Sofia Tools v2</span><span className="hidden sm:inline text-slate-300">•</span><span>2026 by deni s</span><span className="hidden sm:inline text-slate-300">•</span><span>Private • No AI • Self-hosted</span>
          </div>
          <div className="flex items-center gap-6 font-medium text-slate-600"><span>{isGuest ? 'Mode Tamu — kuota 5 proses/hari' : `Hi, ${(user as any).username||(user as any).email}`}</span></div>
        </div>
      </footer>
    </div>
  )
}

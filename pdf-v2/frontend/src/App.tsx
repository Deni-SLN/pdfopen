import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Login } from './pages/Login'
import { Dashboard } from './pages/Dashboard'
import { ToolPage } from './pages/ToolPage'
import { Admin } from './pages/Admin'
import { ChangePassword } from './pages/ChangePassword'
import { useEffect } from 'react'
import { useStore } from './lib/store'

function Guard({children}:{children:React.ReactNode}){
  const {token, user, ensureGuest, guestBooting}=useStore() as any
  useEffect(()=>{ if(!token) ensureGuest() },[token])
  // login opsional: tanpa token pun tetap bisa dipakai (tamu kuota 5x/hari)
  if(!token){
    return guestBooting ? (
      <div className="min-h-[50vh] grid place-items-center text-sm text-slate-500">Menyiapkan sesi tamu…</div>
    ) : <>{children}</>
  }
  if(user?.must_change_password) return <Navigate to="/force-change"/>
  return <>{children}</>
}
function ForceGuard({children}:{children:React.ReactNode}){
  const {token}=useStore() as any
  if(!token) return <Navigate to="/login"/>
  return <>{children}</>
}
export default function App(){
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard"/>}/>
          <Route path="/login" element={<Login/>}/>
          <Route path="/dashboard" element={<Guard><Dashboard/></Guard>}/>
          <Route path="/tool/:id" element={<Guard><ToolPage/></Guard>}/>
          <Route path="/admin" element={<Guard><Admin/></Guard>}/>
          <Route path="/change-password" element={<ForceGuard><ChangePassword/></ForceGuard>}/>
          <Route path="/force-change" element={<ForceGuard><ChangePassword forced/></ForceGuard>}/>
          <Route path="*" element={<Navigate to="/dashboard"/>}/>
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}
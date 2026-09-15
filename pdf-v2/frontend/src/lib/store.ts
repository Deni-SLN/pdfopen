import { create } from 'zustand'
import { api } from './api'
type User={id:string,email?:string,username?:string,role:string,must_change_password?:boolean,quota_daily?:number}
interface S{
  token:string|null; user:User|null; guestBooting:boolean
  setAuth:(t:string,u:User)=>void
  logout:()=>void
  ensureGuest:()=>Promise<void>
}
export const useStore=create<S>((set,get)=>({
  token: localStorage.getItem('token'),
  user: JSON.parse(localStorage.getItem('user')||'null'),
  guestBooting: false,
  setAuth:(token,user)=>{ localStorage.setItem('token',token); localStorage.setItem('user',JSON.stringify(user)); set({token,user})},
  logout:()=>{ localStorage.removeItem('token'); localStorage.removeItem('user'); set({token:null,user:null})},
  ensureGuest:async()=>{
    if(get().token) return
    if(get().guestBooting) return
    set({guestBooting:true})
    try{
      const r=await api.post('/api/auth/guest')
      get().setAuth(r.data.access_token, r.data.user)
    }catch{}
    set({guestBooting:false})
  }
}))
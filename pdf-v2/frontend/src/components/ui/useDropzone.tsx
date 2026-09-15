import { useState } from 'react'
export function useDropzone(onFiles:(f:File[])=>void){
  const [isDragActive,setA]=useState(false)
  const getRootProps=()=>({
    onDragOver:(e:React.DragEvent)=>{e.preventDefault(); setA(true)},
    onDragLeave:()=>setA(false),
    onDrop:(e:React.DragEvent)=>{e.preventDefault(); setA(false); onFiles(Array.from(e.dataTransfer.files))},
    onClick:()=>document.getElementById('file-input-hidden')?.click()
  })
  const getInputProps=()=>({
    id:'file-input-hidden', type:'file' as const, className:'hidden',
    onChange:(e:React.ChangeEvent<HTMLInputElement>)=>{ if(e.target.files) onFiles(Array.from(e.target.files)) }
  })
  return {getRootProps,getInputProps,isDragActive}
}

import { useDropzone } from './useDropzone'
import { Upload } from 'lucide-react'
export function Dropzone({onFiles, accept}:{onFiles:(files:File[])=>void, accept?:string}){
  const {getRootProps,getInputProps,isDragActive}=useDropzone(onFiles)
  return (
    <div {...getRootProps()} className={`border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition ${isDragActive?'border-indigo-500 bg-indigo-50 dark:bg-indigo-950':'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900'}`}>
      <input {...getInputProps()} accept={accept}/>
      <Upload className="mx-auto mb-3 text-slate-400" size={32}/>
      <p className="font-medium">Drop files here or click to browse</p>
      <p className="text-sm text-slate-500 mt-1">PDF, Images, Markdown, HTML, MP3 supported</p>
    </div>
  )
}
// lightweight hook inline

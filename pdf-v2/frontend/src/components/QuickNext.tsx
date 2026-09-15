import { Link } from 'react-router-dom'
import { toolsList } from '../lib/api'

export function QuickNext({current}:{current:string}){
  const others = toolsList.filter(t=>t.id!==current).slice(0,12)
  return (
    <div className="mt-4 p-4 bg-slate-50 rounded-xl border">
      <div className="text-xs font-semibold text-slate-700">Lanjut ke menu lainnya</div>
      <p className="text-xs text-slate-500 mt-1">File hasil bisa langsung diproses di tool lain tanpa upload ulang — klik untuk lanjut:</p>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mt-3">
        {others.map(t=>(
          <Link key={t.id} to={`/tool/${t.id}`} className="px-3 py-2 bg-white border rounded-xl text-xs font-medium hover:border-brand-300 hover:text-brand-700 text-center">
            {t.name}
          </Link>
        ))}
      </div>
      <Link to="/dashboard" className="mt-3 inline-block text-xs text-brand-600 hover:underline">← Kembali ke Dashboard</Link>
    </div>
  )
}

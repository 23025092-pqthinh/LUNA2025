import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { useAuth } from '../state/auth.jsx'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'

export default function Leaderboard(){
  const { API, token } = useAuth()
  const [items, setItems] = useState([])
  const [datasets, setDatasets] = useState([]) // API may return array or {items:[]}
  const [datasetId, setDatasetId] = useState('')
  const [metric, setMetric] = useState('AUC')

  const authHeaders = token ? { Authorization: `Bearer ${token}` } : null

  const load = async ()=>{
    try {
      const opts = authHeaders ? { headers: authHeaders } : undefined
      const dsResp = await axios.get(`${API}/datasets/`, opts)
      const dsData = dsResp.data
      setDatasets(Array.isArray(dsData) ? dsData : (dsData && dsData.items) ? dsData.items : [])

      const params = new URLSearchParams()
      if (datasetId) params.append('dataset_id', datasetId)
      if (metric) params.append('metric', metric)
      const lbResp = await axios.get(`${API}/leaderboard/?${params.toString()}`, opts)
      const lbData = lbResp.data
      setItems(Array.isArray(lbData) ? lbData : (lbData && lbData.items) ? lbData.items : [])
    } catch (err) {
      // keep UI responsive; log for debugging
      // eslint-disable-next-line no-console
      console.warn('Leaderboard load error', err?.response?.status, err?.message)
      setDatasets([])
      setItems([])
    }
  }
  useEffect(()=>{ load() }, [datasetId, metric])


  const getDatasetName = (id)=>{
    if (id === null || id === undefined) return '-'
    const d = datasets.find(ds => String(ds.id) === String(id))
    return d ? (d.name ?? `Dataset ${d.id}`) : `Dataset ${id}`
  }

  // Get medal emoji for top 3
  const getMedal = (rank) => {
    if (rank === 1) return '🥇'
    if (rank === 2) return '🥈'
    if (rank === 3) return '🥉'
    return rank
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-brand-500 to-brand-600 bg-clip-text text-transparent">
            Leaderboard
          </h1>
          <p className="text-navy-600 mt-2">Track team performance and rankings</p>
        </div>
      </div>
      
      <div className="card">
        <div className="flex gap-4 items-center flex-wrap">
          <div>
            <div className="label">Filter by Dataset</div>
            <select className="input w-64" value={datasetId} onChange={e=>setDatasetId(e.target.value)}>
              <option value="">All Datasets</option>
              {datasets.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </div>
          <div>
            <div className="label">Sort by Metric</div>
            <select className="input w-48" value={metric} onChange={e=>setMetric(e.target.value)}>
              <option value="AUC">AUC</option>
              <option value="F1">F1 Score</option>
              <option value="PRECISION">Precision</option>
              <option value="RECALL">Recall</option>
              <option value="ACC">Accuracy</option>
            </select>
          </div>
        </div>
      </div>

      <div className="card overflow-x-auto">
        <table className="min-w-full">
          <thead>
            <tr className="text-left border-b">
              <th className="p-2">#</th>
              <th className="p-2">Group</th>
              <th className="p-2">Uploader</th>
              <th className="p-2">Dataset</th>

              {/* clickable metric headers: click to sort by that metric */}
              <th className={`cursor-pointer ${metric==='AUC' ? 'text-brand-600' : ''}`} onClick={()=>setMetric('AUC')}>AUC</th>
              <th className={`cursor-pointer ${metric==='F1' ? 'text-brand-600' : ''}`} onClick={()=>setMetric('F1')}>F1</th>
              <th className={`cursor-pointer ${metric==='PRECISION' ? 'text-brand-600' : ''}`} onClick={()=>setMetric('PRECISION')}>PRECISION</th>
              <th className={`cursor-pointer ${metric==='RECALL' ? 'text-brand-600' : ''}`} onClick={()=>setMetric('RECALL')}>Recall {metric==='RECALL' && '↓'}</th>
              <th className={`cursor-pointer ${metric==='ACC' ? 'text-brand-600' : ''}`} onClick={()=>setMetric('ACC')}>ACC</th>
            </tr>
          </thead>
          <tbody>
            {items.map((x, i)=> (
              <tr key={x.submission_id || i} className="border-b">
                <td className="p-2">{i+1}</td>
                <td className="p-2">{x.group_name}</td>
                <td className="p-2">{x.gr ?? x.uploader_username ?? x.uploader_id ?? '-'}</td>
                <td className="p-2">{getDatasetName(x.dataset_id)}</td>
                <td className="p-2">{(x.auc!=null) ? x.auc.toFixed?.(4) ?? x.auc : '-'}</td>
                <td className="p-2">{(x.f1!=null) ? x.f1.toFixed?.(4) ?? x.f1 : '-'}</td>
                <td className="p-2">{(x.precision!=null) ? x.precision.toFixed?.(4) ?? x.precision : '-'}</td>
                <td className="p-2">{(x.recall!=null) ? x.recall.toFixed?.(4) ?? x.recall : '-'}</td>
                <td className="p-2">{(x.acc!=null) ? x.acc.toFixed?.(4) ?? x.acc : '-'}</td>
                <td className="p-2">
                  <button className="btn" onClick={()=>loadHistory(x.group_name, x.dataset_id)}>View</button>
                </td>
              </tr>
            ))}
            {items.length===0 && (
              <tr>
                <td className="p-8 text-center text-slate-500" colSpan={9}>
                  No submissions found for the selected dataset/metric.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

    
    </div>
  )
}

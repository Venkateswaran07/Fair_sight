import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Spinner from './Spinner'

export default function ApplicantList({ sessionId }) {
  const navigate = useNavigate()
  const [applicants, setApplicants] = useState([])
  const [headers, setHeaders] = useState([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!sessionId) return

    async function fetchData() {
      setLoading(true)
      const PRODUCTION_BACKEND_URL = 'https://fairsight-backend-403339568263.us-central1.run.app'
      const baseUrl = import.meta.env.VITE_API_URL || (window.location.hostname === 'localhost' ? 'http://localhost:8000' : PRODUCTION_BACKEND_URL)
      try {
        const res = await fetch(`${baseUrl}/audit/applicants/${sessionId}`)
        if (res.ok) {
          const data = await res.json()
          setApplicants(data.applicants)
          setHeaders(data.headers)
        } else {
          setError("Session data not found on server. Re-upload your CSV to view the audit log.")
        }
      } catch (e) {
        setError("Failed to connect to audit service.")
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [sessionId])

  const filtered = applicants.filter(app => {
    if (!search) return true
    const s = search.toLowerCase()
    return Object.values(app).some(val => String(val).toLowerCase().includes(s))
  })

  if (loading) return <div className="p-8 text-center"><Spinner size={24} label="Loading applicant log..." /></div>
  if (error) return <div className="p-6 bg-amber-50 border border-amber-200 rounded-lg text-amber-800 text-sm">{error}</div>

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm mt-10">
      <div className="px-6 py-4 border-b border-gray-200 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-gray-50/50">
        <div>
          <h3 className="text-base font-bold text-gray-900">Applicant Audit Log</h3>
          <p className="text-xs text-gray-500 mt-0.5">Explore individual predictions and drill down into the Glass Box.</p>
        </div>
        <div className="relative w-full sm:w-64">
          <input
            type="text"
            placeholder="Search applicants..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-accent outline-none"
          />
          <svg className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
      </div>

      <div className="overflow-x-auto max-h-[500px]">
        <table className="w-full text-left text-sm border-collapse">
          <thead className="bg-white sticky top-0 z-10 shadow-sm">
            <tr>
              <th className="px-6 py-3 border-b border-gray-100 text-gray-400 font-medium text-[11px] uppercase tracking-wider">Actions</th>
              {headers.map(h => (
                <th key={h} className="px-6 py-3 border-b border-gray-100 text-gray-600 font-semibold text-[11px] uppercase tracking-wider">
                  {h.replace(/_/g, ' ')}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={headers.length + 1} className="px-6 py-10 text-center text-gray-400 italic">
                  No applicants match your search.
                </td>
              </tr>
            ) : (
              filtered.map((app, idx) => (
                <tr key={idx} className="hover:bg-blue-50/30 transition-colors">
                  <td className="px-6 py-3">
                    <button
                      onClick={() => navigate('/explain')}
                      className="text-xs font-semibold text-accent hover:underline flex items-center gap-1"
                    >
                      Glass Box
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                      </svg>
                    </button>
                  </td>
                  {headers.map(h => {
                    const val = app[h];
                    const isDecision = h.toLowerCase().includes('prediction') || h.toLowerCase().includes('outcome');
                    return (
                      <td key={h} className="px-6 py-3 whitespace-nowrap">
                        {isDecision ? (
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${String(val) === '1' || String(val).toLowerCase() === 'approved' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                            {val}
                          </span>
                        ) : (
                          <span className="text-gray-700 font-mono text-[13px]">{val}</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <div className="px-6 py-3 border-t border-gray-100 bg-gray-50/30 text-[11px] text-gray-400 text-right">
        Showing {filtered.length} of {applicants.length} records.
      </div>
    </div>
  )
}

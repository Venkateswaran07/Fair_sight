import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import AuditDashboard from '../components/AuditDashboard'

export default function ResultsPage() {
  const navigate = useNavigate()
  const [data, setData] = useState(null)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const sessionId = params.get('session_id')

    async function loadFromHistory(id) {
      const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
      try {
        const res = await fetch(`${baseUrl}/audit/history`)
        if (res.ok) {
          const data = await res.json()
          const record = data.history.find(r => r.session_id === id)
          if (record) {
            // Map history record back to the format expected by ResultsPage
            setData({
              demographics: record.demographics || null,
              performance: record.performance || null,
              fairness: record.metrics ? { ...record.metrics, ...record } : null,
              proxies: record.proxies || null
            })
            return true
          }
        }
      } catch (e) {
        console.error("Failed to fetch history", e)
      }
      return false
    }

    async function init() {
      if (sessionId) {
        const success = await loadFromHistory(sessionId)
        if (success) return
      }

      const stored = sessionStorage.getItem('fairsight_results')
      if (stored) {
        setData(JSON.parse(stored))
      } else {
        navigate('/upload')
      }
    }

    init()
  }, [navigate])

  if (!data) return null

  return (
    <div className="min-h-screen bg-[#F9F9F7]">
      <Navbar />
      <main className="max-w-6xl mx-auto px-6 section">
        <div className="mb-8 flex justify-between items-end border-b border-gray-200 pb-5">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Audit Results</h1>
            <p className="mt-2 text-gray-600">
              Comprehensive fairness and performance analysis across your protected groups.
            </p>
          </div>
          <button
            onClick={() => navigate('/upload')}
            className="border border-gray-300 text-gray-700 hover:bg-gray-100 font-medium px-4 py-2 rounded transition-colors text-sm"
          >
            New Audit
          </button>
        </div>

        <AuditDashboard
          demographicsResult={data.demographics}
          performanceResult={data.performance}
          fairnessResult={data.fairness}
          proxyResult={data.proxies}
        />
      </main>
    </div>
  )
}

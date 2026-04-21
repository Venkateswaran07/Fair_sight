import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import AuditDashboard from '../components/AuditDashboard'

export default function ResultsPage() {
  const navigate = useNavigate()
  const [data, setData] = useState(null)

  useEffect(() => {
    try {
      const stored = sessionStorage.getItem('fairsight_results')
      if (stored) {
        setData(JSON.parse(stored))
      } else {
        // Redirect to upload if no data in session
        navigate('/upload')
      }
    } catch (err) {
      console.error('Failed to parse session data', err)
      navigate('/upload')
    }
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

import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import AuditDashboard from '../components/AuditDashboard'

export default function ResultsPage() {
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loadingMitigation, setLoadingMitigation] = useState(false)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const sessionId = params.get('session_id')

    async function loadFromHistory(id) {
      const PRODUCTION_BACKEND_URL = 'https://fairsight-backend-403339568263.us-central1.run.app'
      const baseUrl = import.meta.env.VITE_API_URL || (window.location.hostname === 'localhost' ? 'http://localhost:8000' : PRODUCTION_BACKEND_URL)
      try {
        const res = await fetch(`${baseUrl}/audit/history`)
        if (res.ok) {
          const historyData = await res.json()
          const record = historyData.history.find(r => r.session_id === id)
          if (record) {
            const formattedData = {
              demographics: record.demographics || null,
              performance: record.performance || null,
              fairness: record.metrics ? { ...record.metrics, ...record } : null,
              proxies: record.proxies || null,
              mitigation: record.mitigation || null,
              session_id: id
            }
            setData(formattedData)
            return formattedData
          }
        }
      } catch (e) {
        console.error("Failed to fetch history", e)
      }
      return null
    }

    async function init() {
      let currentData = null
      if (sessionId) {
        currentData = await loadFromHistory(sessionId)
      }

      if (!currentData) {
        const stored = sessionStorage.getItem('fairsight_results')
        if (stored) {
          currentData = JSON.parse(stored)
          setData(currentData)
        }
      }

      if (currentData) {
        // AUTOMATIC MITIGATION: Run it if missing
        if (!currentData.mitigation && currentData.session_id) {
          runMitigation(currentData)
        }
      } else {
        navigate('/upload')
      }
    }

    init()
  }, [navigate])

  // AGGRESSIVE AUTO-RUN: Trigger whenever data is loaded but mitigation is missing
  useEffect(() => {
    if (data && !data.mitigation && data.session_id && !loadingMitigation) {
      console.log("[AutoRun] Triggering mitigation audit...")
      runMitigation(data)
    }
  }, [data])

  const runMitigation = async (targetData) => {
    if (!targetData?.session_id || loadingMitigation) return
    
    const PRODUCTION_BACKEND_URL = 'https://fairsight-backend-403339568263.us-central1.run.app'
    const baseUrl = import.meta.env.VITE_API_URL || (window.location.hostname === 'localhost' ? 'http://localhost:8000' : PRODUCTION_BACKEND_URL)
    
    setLoadingMitigation(true)
    try {
      const cols = targetData.demographics?.protected_attributes || targetData.fairness?.protected_attributes || []
      const protected_col = cols[0] || 'gender'

      const formData = new FormData()
      formData.append('session_id', targetData.session_id)
      formData.append('protected_column', protected_col)

      const res = await fetch(`${baseUrl}/audit/mitigate`, { method: 'POST', body: formData })
      if (res.ok) {
        const mitigation = await res.json()
        setData(prev => {
          const newData = { ...prev, mitigation }
          sessionStorage.setItem('fairsight_results', JSON.stringify(newData))
          return newData
        })
      }
    } catch (e) {
      console.error("[AutoMitigation] Error:", e)
    } finally {
      setLoadingMitigation(false)
    }
  }

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
          <div className="flex gap-3 items-center">
            <button
              onClick={() => navigate('/upload')}
              className="border border-gray-300 text-gray-700 hover:bg-gray-100 font-medium px-4 py-2 rounded transition-colors text-sm"
            >
              New Audit
            </button>
          </div>
        </div>

        <AuditDashboard
          demographicsResult={data.demographics}
          performanceResult={data.performance}
          fairnessResult={data.fairness}
          proxyResult={data.proxies}
          mitigationResult={data.mitigation}
          sessionId={data.session_id}
          loadingMitigation={loadingMitigation}
        />
      </main>
    </div>
  )
}

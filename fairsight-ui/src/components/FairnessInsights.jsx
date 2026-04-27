import React, { useState, useEffect } from 'react'

export default function FairnessInsights({ sessionId, fairnessResult, protectedColumn }) {
  const [insights, setInsights] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (fairnessResult && sessionId && !insights) {
      fetchInsights()
    }
  }, [fairnessResult, sessionId])

  const fetchInsights = async () => {
    setLoading(true)
    setError(null)
    const PRODUCTION_BACKEND_URL = 'https://fairsight-backend-403339568263.us-central1.run.app'
    const baseUrl = import.meta.env.VITE_API_URL || (window.location.hostname === 'localhost' ? 'http://localhost:8000' : PRODUCTION_BACKEND_URL)
    
    try {
      const formData = new FormData()
      formData.append('session_id', sessionId)
      formData.append('protected_column', protectedColumn || fairnessResult.protected_column)
      formData.append('fairness_json', JSON.stringify(fairnessResult))

      const res = await fetch(`${baseUrl}/audit/insights`, {
        method: 'POST',
        body: formData
      })

      if (res.ok) {
        const data = await res.json()
        setInsights(data.insights)
      } else {
        setError('Failed to load strategic recommendations.')
      }
    } catch (e) {
      setError('Connection error while fetching AI insights.')
    } finally {
      setLoading(false)
    }
  }

  if (!fairnessResult) return null

  return (
    <section className="py-8 border-b border-gray-200 last:border-0 animate-in fade-in duration-500">
      <div className="mb-5 flex justify-between items-center">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-indigo-700">
            AI Strategic Recommendations
          </p>
          <p className="mt-1 text-sm text-gray-500">
            Automated analysis of bias root causes and actionable steps for model improvement.
          </p>
        </div>
        {!insights && !loading && (
           <button 
             onClick={fetchInsights}
             className="text-xs bg-indigo-50 text-indigo-700 px-3 py-1 rounded border border-indigo-100 hover:bg-indigo-100 transition-colors"
           >
             Regenerate
           </button>
        )}
      </div>

      <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-6 min-h-[100px] relative">
        {loading ? (
          <div className="flex items-center gap-3 text-indigo-600">
            <div className="animate-spin h-4 w-4 border-2 border-indigo-600 border-t-transparent rounded-full"></div>
            <span className="text-sm font-medium">Gemini is analyzing your fairness metrics...</span>
          </div>
        ) : error ? (
          <p className="text-sm text-red-600">{error}</p>
        ) : insights ? (
          <div className="prose prose-indigo prose-sm max-w-none text-indigo-900 leading-relaxed">
             {/* We use a simple markdown-style renderer here since we expect basic MD */}
             <div className="whitespace-pre-wrap">
               {insights}
             </div>
          </div>
        ) : (
          <p className="text-sm text-indigo-400 italic">No recommendations generated yet.</p>
        )}
      </div>
    </section>
  )
}

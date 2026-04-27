import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import DropZone from '../components/DropZone'
import Spinner from '../components/Spinner'

/* ──────────────────────────────────────────────────────────────────────────
   UploadPage — Screen 1
   - Original Layout (Vertical Form)
   - Enhanced with Live Data Preview (from Glass Box)
────────────────────────────────────────────────────────────────────────── */

function FieldError({ msg }) {
  return msg ? (
    <p role="alert" className="text-xs text-red-600 mt-1">{msg}</p>
  ) : null
}

const PRODUCTION_BACKEND_URL = 'https://fairsight-backend-403339568263.us-central1.run.app'

export default function UploadPage() {
  const navigate = useNavigate()
  const baseUrl = import.meta.env.VITE_API_URL || (window.location.hostname === 'localhost' ? 'http://localhost:8000' : PRODUCTION_BACKEND_URL)

  /* ── Form state ──────────────────────────────────────────────── */
  const [datasetFile, setDatasetFile]     = useState(null)
  const [predictFile, setPredictFile]     = useState(null)
  const [protectedCols, setProtectedCols] = useState('')
  
  // Session IDs for the uploaded files
  const [datasetSessionId, setDatasetSessionId] = useState(null)
  const [predictSessionId, setPredictSessionId] = useState(null)

  /* ── UI state ────────────────────────────────────────────────── */
  const [loading, setLoading]   = useState(false)
  const [result, setResult]     = useState(null)
  const [error, setError]       = useState(null)
  const [fieldErrors, setFieldErrors] = useState({})
  
  // Preview state
  const [csvPreview, setCsvPreview] = useState(null)
  const [previewPage, setPreviewPage] = useState(0)
  const [previewSearch, setPreviewSearch] = useState('')
  const [isAnalyzingHeaders, setIsAnalyzingHeaders] = useState(false)

  /* ── Background Upload & Preview ─────────────────────────────── */
  // Unified upload function to handle sequential queue
  const [uploadQueue, setUploadQueue] = useState(Promise.resolve())

  const [isUploading, setIsUploading] = useState({ dataset: false, predict: false })

  const performUpload = async (file, type) => {
    setIsUploading(prev => ({ ...prev, [type]: true }))
    console.log(`[FairSight] Uploading ${type} to: ${baseUrl}/audit/upload`)
    
    const formData = new FormData()
    formData.append('file', file)
    
    try {
        const res = await fetch(`${baseUrl}/audit/upload`, { 
          method: 'POST', 
          body: formData 
        })
        if (res.ok) {
            const data = await res.json()
            console.log(`[FairSight] ${type} upload success. Session: ${data.session_id}`)
            
            if (type === 'dataset') setDatasetSessionId(data.session_id)
            else setPredictSessionId(data.session_id)
            
            // Show preview
            setCsvPreview({ headers: data.headers, allRows: data.preview_rows, total: data.total_rows })
        } else {
            const text = await res.text()
            setError(`Upload failed (${res.status}). If your file is very large (>100MB), the server might reject it.`)
        }
    } catch (e) {
        console.error(`[FairSight] ${type} upload error:`, e)
        setError(`Connection failed. The backend might be starting up (Cold Start) or the 90MB file timed out. Please wait 10 seconds and try dropping the file again.`)
    } finally {
        setIsUploading(prev => ({ ...prev, [type]: false }))
    }
  }

  // Effect for Dataset File
  useEffect(() => {
    if (!datasetFile) {
        setDatasetSessionId(null)
        return
    }
    // If files are identical, share the session
    if (predictFile && datasetFile.name === predictFile.name && datasetFile.size === predictFile.size && predictSessionId) {
        setDatasetSessionId(predictSessionId)
        return
    }
    setUploadQueue(prev => prev.then(() => performUpload(datasetFile, 'dataset')))
  }, [datasetFile])

  // Effect for Prediction File
  useEffect(() => {
    if (!predictFile) {
        setPredictSessionId(null)
        return
    }
    // If files are identical, share the session
    if (datasetFile && predictFile.name === datasetFile.name && predictFile.size === datasetFile.size && datasetSessionId) {
        setPredictSessionId(datasetSessionId)
        return
    }
    setIsAnalyzingHeaders(true)
    setUploadQueue(prev => prev.then(() => performUpload(predictFile, 'predict')).finally(() => setIsAnalyzingHeaders(false)))
  }, [predictFile])

  const handleHeaderClick = (header) => {
      const current = protectedCols.split(',').map(s => s.trim()).filter(Boolean)
      if (current.includes(header)) {
          setProtectedCols(current.filter(h => h !== header).join(', '))
      } else {
          setProtectedCols([...current, header].join(', '))
      }
  }

  /* ── Submit ──────────────────────────────────────────────────── */
  async function handleSubmit(e) {
    if (e) e.preventDefault()
    
    // Validation
    const errs = {}
    if (!datasetFile) errs.dataset = 'Please upload a training dataset CSV.'
    if (!predictFile) errs.predict = 'Please upload a predictions CSV.'
    if (!protectedCols.trim()) errs.cols = 'Enter at least one protected column name.'
    setFieldErrors(errs)
    if (Object.keys(errs).length > 0) return

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const cols = protectedCols.split(',').map(s => s.trim()).filter(Boolean)

      const fetchWithSession = async (path, sessionId, additionalFields = {}) => {
        const formData = new FormData()
        formData.append('session_id', sessionId)
        Object.entries(additionalFields).forEach(([k, v]) => formData.append(k, v))
        
        const res = await fetch(`${baseUrl}${path}`, { method: 'POST', body: formData })
        if (!res.ok) {
           const text = await res.text()
           throw new Error(`Error on ${path}: ${res.statusText} - ${text}`)
        }
        return res.json()
      }

      // Sequential requests using Session IDs (PREVENT OOM)
      // We run them one by one so the backend doesn't try to process 4 large analyses simultaneously
      const demographics = await fetchWithSession('/audit/demographics', datasetSessionId, { protected_columns: JSON.stringify(cols) })
      const performance  = await fetchWithSession('/audit/performance', predictSessionId, { protected_columns: JSON.stringify(cols) })
      const fairness     = await fetchWithSession('/audit/fairness', predictSessionId, { protected_column: cols[0], positive_label: '1' })
      const proxies      = await fetchWithSession('/audit/proxies', datasetSessionId, { protected_columns: JSON.stringify(cols) })
      
      // Run mitigation on the primary protected attribute
      let mitigation = null
      try {
        mitigation = await fetchWithSession('/audit/mitigate', datasetSessionId, { protected_column: cols[0] })
      } catch (me) {
        console.warn("Mitigation analysis skipped or failed:", me)
      }

      const fullResult = { 
        demographics, 
        performance, 
        fairness, 
        proxies,
        mitigation,
        session_id: predictSessionId,
        protected_attributes: cols,
        fairness_assessment: (fairness.overall_pass) ? "FAIR" : "BIASED",
        metrics: fairness
      }
      
      // Save to history automatically
      try {
        await fetch(`${baseUrl}/audit/history/save`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ...fullResult, session_id: predictSessionId })
        })
      } catch (saveErr) {
        console.error("Failed to auto-save to history:", saveErr)
      }

      setResult(fullResult)
    } catch (err) {
      setError(err.message || 'An unexpected error occurred.')
    } finally {
      setLoading(false)
    }
  }

  if (result) {
    return (
      <div className="min-h-screen bg-[#F9F9F7]">
        <Navbar />
        <main className="max-w-2xl mx-auto px-6 section">
          <div className="border border-green-200 bg-green-50 rounded-lg p-6 text-center">
            <svg className="w-10 h-10 text-green-500 mx-auto" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
            </svg>
            <h2 className="mt-4 text-xl font-semibold text-gray-900">Audit ready</h2>
            <p className="mt-2 text-gray-600">
              Analysed <strong>{result.demographics?.num_rows?.toLocaleString()}</strong> rows
            </p>
            <div className="mt-6 flex flex-col sm:flex-row gap-3 justify-center">
              <button
                onClick={() => {
                  sessionStorage.setItem('fairsight_results', JSON.stringify(result))
                  navigate('/results')
                }}
                className="bg-accent hover:bg-accent-hover text-white font-medium px-6 py-2.5 rounded transition-colors"
              >
                View results
              </button>
              <button onClick={() => setResult(null)} className="border border-gray-300 text-gray-700 hover:bg-gray-100 font-medium px-6 py-2.5 rounded transition-colors">
                New audit
              </button>
            </div>
          </div>
        </main>
      </div>
    )
  }

  const selectedList = protectedCols.split(',').map(s => s.trim()).filter(Boolean)

  return (
    <div className="min-h-screen bg-[#F9F9F7]">
      <Navbar />

      <main className="max-w-6xl mx-auto px-6 py-10">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">Upload your data</h1>
          <p className="mt-2 text-gray-600">
            Analyze your model for bias using <strong>Vertex AI</strong>. All results are securely saved to <strong>Google Firestore</strong>.
          </p>
        </div>

        <div className="flex flex-col lg:flex-row gap-10">
          {/* Left: Original Form */}
          <form onSubmit={handleSubmit} noValidate className="flex-1 flex flex-col gap-7 max-w-xl">
            <div>
              <label className="block text-sm font-semibold text-gray-800 mb-2">Training dataset</label>
              <DropZone
                label="Drop your dataset CSV here"
                hint="Used for demographics & proxy analysis"
                file={datasetFile}
                onFile={(f) => { setDatasetFile(f); setFieldErrors(e => ({ ...e, dataset: '' })) }}
                loading={isUploading.dataset}
              />
              <FieldError msg={fieldErrors.dataset} />
            </div>

            <div>
              <label className="block text-sm font-semibold text-gray-800 mb-2">Predictions CSV</label>
              <DropZone
                label="Drop your predictions CSV here"
                hint="Requires prediction and ground_truth columns"
                file={predictFile}
                onFile={(f) => { setPredictFile(f); setFieldErrors(e => ({ ...e, predict: '' })) }}
                loading={isUploading.predict}
              />
              <FieldError msg={fieldErrors.predict} />
            </div>

            <div>
              <label htmlFor="protected-cols" className="block text-sm font-semibold text-gray-800 mb-2">
                Protected columns
              </label>
              <input
                id="protected-cols"
                type="text"
                placeholder="gender, race, age"
                value={protectedCols}
                onChange={(e) => {
                  setProtectedCols(e.target.value)
                  setFieldErrors(err => ({ ...err, cols: '' }))
                }}
                className="w-full border border-gray-300 rounded-lg px-4 py-2.5 text-sm text-gray-900 focus:ring-2 focus:ring-accent outline-none"
              />
              <p className="mt-1.5 text-xs text-gray-500">Click headers in the table to select, or type here.</p>
              <FieldError msg={fieldErrors.cols} />
            </div>

            {error && (
              <div className="border border-red-200 bg-red-50 rounded-lg px-4 py-3 text-sm text-red-700">
                <strong className="font-semibold">Request failed: </strong>{error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="bg-accent hover:bg-accent-hover disabled:opacity-60 text-white font-medium px-8 py-3 rounded-lg transition-all self-start flex items-center gap-2"
            >
              {loading ? <Spinner size={16} /> : 'Submit for audit'}
            </button>
          </form>

          {/* Right: Glass Box Style Preview */}
          <div className="flex-[1.5] flex flex-col min-h-[500px]">
             {csvPreview ? (() => {
                 // 1. Filter rows by search
                 const searchLower = previewSearch.toLowerCase()
                 let filteredTokens = []
                 for(let i=0; i<csvPreview.allRows.length; i++) {
                     const row = csvPreview.allRows[i]
                     if (!searchLower || row.some(cell => cell.toLowerCase().includes(searchLower))) {
                         filteredTokens.push({ originalIndex: i + 1, row })
                     }
                 }
                 
                 // 2. Paginate (15 per page)
                 const rowsPerPage = 15
                 const totalPages = Math.ceil(filteredTokens.length / rowsPerPage)
                 const currentPage = Math.min(previewPage, Math.max(0, totalPages - 1))
                 
                 const startIndex = currentPage * rowsPerPage
                 const paginatedRows = filteredTokens.slice(startIndex, startIndex + rowsPerPage)
                 const isSearching = previewSearch.trim() !== ''

                 return (
                 <div className="border border-gray-200 rounded-lg bg-white overflow-hidden shadow-sm flex flex-col h-full">
                     <div className="bg-gray-50 px-4 py-3 border-b border-gray-200 flex flex-col gap-2">
                         <div className="flex justify-between items-center">
                             <div className="flex items-center gap-2">
                                <span className="text-sm font-bold text-gray-700 uppercase tracking-tight">Live Data Preview</span>
                                {isAnalyzingHeaders && <Spinner size={12} label="AI analyzing headers..." />}
                             </div>
                             <span className="text-[10px] text-gray-500 font-medium">
                                {isSearching ? `Matched ${filteredTokens.length}` : `Total ${csvPreview.total} rows`}
                             </span>
                         </div>
                         <div className="flex flex-col gap-1">
                            <input 
                                type="text"
                                placeholder="Search data..."
                                value={previewSearch}
                                onChange={e => { setPreviewSearch(e.target.value); setPreviewPage(0); }}
                                className="border border-gray-300 rounded px-2 py-1 text-xs outline-none focus:ring-1 focus:ring-accent"
                            />
                            {isAnalyzingHeaders && <p className="text-[9px] text-accent animate-pulse">Syncing with AI mapping...</p>}
                         </div>
                     </div>
                     <div className="overflow-auto flex-1">
                         <table className="w-full text-left text-xs whitespace-nowrap">
                             <thead className="bg-white sticky top-0 z-10 border-b">
                                 <tr>
                                     <th className="px-4 py-3 text-gray-400 font-normal">#</th>
                                     {csvPreview.headers.map((h, i) => {
                                         const isSelected = selectedList.includes(h);
                                         return (
                                             <th 
                                                key={i} 
                                                onClick={() => handleHeaderClick(h)}
                                                className={`px-4 py-3 font-semibold cursor-pointer transition-colors ${isSelected ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-100'}`}
                                             >
                                                 {h}
                                                 {isSelected && <span className="ml-1 text-[10px]">●</span>}
                                             </th>
                                         )
                                     })}
                                 </tr>
                             </thead>
                             <tbody className="divide-y divide-gray-100">
                                 {paginatedRows.map((item, i) => (
                                     <tr key={i}>
                                         <td className="px-4 py-2 text-gray-400">{item.originalIndex}</td>
                                         {item.row.map((cell, j) => {
                                              const isSelected = selectedList.includes(csvPreview.headers[j]);
                                              return (
                                                  <td key={j} className={`px-4 py-2 ${isSelected ? 'bg-blue-50/30' : ''}`}>{cell}</td>
                                              )
                                         })}
                                     </tr>
                                 ))}
                             </tbody>
                         </table>
                     </div>
                     {totalPages > 1 && (
                         <div className="bg-gray-50 px-4 py-2 border-t flex justify-between items-center text-[11px]">
                             <button type="button" onClick={() => setPreviewPage(p => Math.max(0, p - 1))} disabled={currentPage === 0} className="text-gray-600 hover:text-black font-semibold disabled:text-gray-300">
                                 &larr; Prev
                             </button>
                             <span className="text-gray-500 font-medium">Page {currentPage + 1} of {totalPages}</span>
                             <button type="button" onClick={() => setPreviewPage(p => Math.min(totalPages - 1, p + 1))} disabled={currentPage >= totalPages - 1} className="text-gray-600 hover:text-black font-semibold disabled:text-gray-300">
                                 Next &rarr;
                             </button>
                         </div>
                     )}
                 </div>
                 )
             })() : (
                 <div className="border-2 border-dashed border-gray-200 rounded-lg bg-gray-50/50 flex flex-col items-center justify-center p-12 text-center h-full">
                     <p className="text-gray-400 text-sm">Upload a CSV to preview your data and select audit columns</p>
                 </div>
             )}
          </div>
        </div>
      </main>
    </div>
  )
}

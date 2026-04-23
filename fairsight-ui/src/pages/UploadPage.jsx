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

export default function UploadPage() {
  const navigate = useNavigate()

  /* ── Form state ──────────────────────────────────────────────── */
  const [datasetFile, setDatasetFile]     = useState(null)
  const [predictFile, setPredictFile]     = useState(null)
  const [protectedCols, setProtectedCols] = useState('')

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

  /* ── Auto-parse CSV file for preview ─────────────────────────── */
  useEffect(() => {
    const fileToPreview = predictFile || datasetFile
    if (!fileToPreview) {
        setCsvPreview(null)
        return
    }
    
    // Immediate background upload to get AI-mapped headers
    const uploadToGetHeaders = async () => {
        setIsAnalyzingHeaders(true)
        const formData = new FormData()
        formData.append('file', fileToPreview)
        try {
            const res = await fetch('http://localhost:8000/audit/upload', { method: 'POST', body: formData })
            if (res.ok) {
                const data = await res.json()
                if (data && data.headers) {
                    // Update preview with AI-NORMALIZED data from backend
                    setCsvPreview({ 
                        headers: data.headers, 
                        allRows: data.preview_rows, 
                        total: data.total_rows 
                    })
                    setIsAnalyzingHeaders(false)
                    return
                }
            }
        } catch (e) {
            console.error("Auto-mapping upload failed", e)
        }

        // Fallback: Local parsing
        const reader = new FileReader()
        reader.onload = (e) => {
            const text = e.target.result
            const lines = text.split(/\r?\n/).filter(line => line.trim())
            if (lines.length > 0) {
                const stripQuotes = (s) => s.trim().replace(/^["'](.+)["']$/, '$1')
                const headers = lines[0].split(',').map(stripQuotes)
                const allRows = lines.slice(1).map(line => line.split(',').map(stripQuotes))
                setCsvPreview({ headers, allRows, total: lines.length - 1 })
            }
            setIsAnalyzingHeaders(false)
        }
        reader.readAsText(fileToPreview)
    }
    
    uploadToGetHeaders()
  }, [datasetFile, predictFile])

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

      const formDemo = new FormData()
      formDemo.append('file', datasetFile)
      formDemo.append('protected_columns', JSON.stringify(cols))

      const formPerf = new FormData()
      formPerf.append('file', predictFile)
      formPerf.append('protected_columns', JSON.stringify(cols))
      formPerf.append('prediction_column', 'prediction')
      formPerf.append('ground_truth_column', 'ground_truth')
      
      const formFair = new FormData()
      formFair.append('file', predictFile)
      formFair.append('protected_column', cols[0])
      formFair.append('positive_label', '1')

      const formProxy = new FormData()
      formProxy.append('file', datasetFile)
      formProxy.append('protected_columns', JSON.stringify(cols))

      const fetchApi = async (path, bodyData) => {
        const res = await fetch(`http://localhost:8000${path}`, { method: 'POST', body: bodyData })
        if (!res.ok) {
           const text = await res.text()
           throw new Error(`Error on ${path}: ${res.statusText} - ${text}`)
        }
        return res.json()
      }

      const [demographics, performance, fairness, proxies] = await Promise.all([
        fetchApi('/audit/demographics', formDemo),
        fetchApi('/audit/performance', formPerf),
        fetchApi('/audit/fairness', formFair),
        fetchApi('/audit/proxies', formProxy),
      ])

      const fullResult = { demographics, performance, fairness, proxies }
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
          <p className="mt-2 text-gray-600">Provide your dataset and predictions to audit for bias.</p>
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

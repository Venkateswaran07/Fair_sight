import { useState, useEffect } from 'react'
import Navbar from '../components/Navbar'
import DropZone from '../components/DropZone'
import Spinner from '../components/Spinner'
import GlassBoxViewer from '../components/GlassBoxViewer'

export default function ExplainPage() {
  const [datasetFile, setDatasetFile] = useState(null)
  const [targetColumn, setTargetColumn] = useState('prediction')
  const [applicantId, setApplicantId] = useState('1')
  const [audience, setAudience] = useState('hr_manager')
  const [proxyCols, setProxyCols] = useState('gender')

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  
  const [csvPreview, setCsvPreview] = useState(null)
  const [previewPage, setPreviewPage] = useState(0)
  const [previewSearch, setPreviewSearch] = useState('')

  // Auto-parse CSV file for preview via backend Smart Mapper
  useEffect(() => {
    if (!datasetFile) {
        setCsvPreview(null)
        return
    }
    
    const syncWithBackend = async () => {
        const PRODUCTION_BACKEND_URL = 'https://fairsight-backend-403339568263.us-central1.run.app'
        const baseUrl = import.meta.env.VITE_API_URL || (window.location.hostname === 'localhost' ? 'http://localhost:8000' : PRODUCTION_BACKEND_URL)
        const formData = new FormData()
        formData.append('file', datasetFile)
        try {
            const res = await fetch(`${baseUrl}/audit/upload`, { method: 'POST', body: formData })
            if (res.ok) {
                const data = await res.json()
                setCsvPreview({ 
                    headers: data.headers, 
                    allRows: data.preview_rows, 
                    total: data.total_rows 
                })
            }
        } catch (e) {
            console.error("Failed to sync preview with backend", e)
            // Fallback to local if backend is down
            const text = await datasetFile.text()
            const lines = text.split(/\r?\n/).filter(line => line.trim())
            if (lines.length > 0) {
                const headers = lines[0].split(',').map(s => s.trim())
                const allRows = lines.slice(1).map(line => line.split(',').map(s => s.trim()))
                setCsvPreview({ headers, allRows, total: lines.length - 1 })
            }
        }
    }
    syncWithBackend()
  }, [datasetFile])

  // States to pass to GlassBoxViewer
  const [decision, setDecision] = useState(null)
  const [topFeatures, setTopFeatures] = useState([])
  const [proxyFlags, setProxyFlags] = useState([])
  const [counterfactuals, setCounterfactuals] = useState([])
  const [plainExplanation, setPlainExplanation] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    if (!datasetFile) {
      setError('Please provide a training dataset CSV.')
      return
    }

    setLoading(true)
    setError(null)
    setDecision(null)
    setPlainExplanation('')

    try {
        let activeInstanceJson = ""
        try {
            const fileText = await datasetFile.text()
            const lines = fileText.split(/\r?\n/).filter(line => line.trim()) // filter empty lines
            const headers = lines[0].split(',').map(s => s.trim())
            
            // Treat the input as a 1-based row number
            const rowIndex = parseInt(applicantId, 10)
            if (isNaN(rowIndex) || rowIndex < 1 || rowIndex >= lines.length) {
                throw new Error(`Please enter a valid row number between 1 and ${lines.length - 1}.`)
            }
            
            const targetRow = lines[rowIndex].split(',')
            
            // Keywords that indicate a column is an outcome/result (not a feature)
            const outcomeKeywords = ['ground_truth', 'prediction', 'outcome', 'decision', 'label', 'target', 'status', 'bank_loan'];
            
            let extractedJson = {}
            targetRow.forEach((val, idx) => {
                const header = headers[idx]
                const cleanHeader = header.toLowerCase().replace(/[^a-z0-9]/g, '');
                
                // Only include as a feature if it's NOT the target and NOT an outcome column
                const isTarget = header === targetColumn || cleanHeader === targetColumn.toLowerCase().replace(/[^a-z0-9]/g, '');
                const isOutcome = outcomeKeywords.some(k => cleanHeader.includes(k));

                if (!isTarget && !isOutcome) {
                    const num = Number(val)
                    extractedJson[header] = isNaN(num) ? val.trim() : num
                }
            })
            
            // Remove ID columns
            Object.keys(extractedJson).forEach(key => {
                if (key.toLowerCase().includes('id') || key.toLowerCase() === 'no' || key.toLowerCase() === '#') {
                    delete extractedJson[key]
                }
            })
            
            activeInstanceJson = JSON.stringify(extractedJson)
        } catch (e) {
            throw new Error(`Failed to extract row data: ${e.message}`)
        }

        const PRODUCTION_BACKEND_URL = 'https://fairsight-backend-403339568263.us-central1.run.app'
        const baseUrl = import.meta.env.VITE_API_URL || (window.location.hostname === 'localhost' ? 'http://localhost:8000' : PRODUCTION_BACKEND_URL)

        // 1. Fetch SHAP Explain
        const formExplain = new FormData()
        formExplain.append('file', datasetFile)
        formExplain.append('target_column', targetColumn)
        formExplain.append('instance', activeInstanceJson)
        formExplain.append('top_n', '5')

        const resExplain = await fetch(`${baseUrl}/audit/explain`, { method: 'POST', body: formExplain })
        if (!resExplain.ok) throw new Error(await resExplain.text())
        const explainData = await resExplain.json()

        const actualDecision = explainData.predicted_class == 1 ? "APPROVED" : "REJECTED"
        const feats = explainData.top_features

        // 2. Fetch Proxy Flags
        // Safely map protected cols to array
        const cols = proxyCols.split(',').map(s => s.trim()).filter(Boolean)
        const formProxy = new FormData()
        formProxy.append('file', datasetFile)
        formProxy.append('protected_columns', JSON.stringify(cols))

        const resProxy = await fetch(`${baseUrl}/audit/proxies`, { method: 'POST', body: formProxy })
        if (!resProxy.ok) throw new Error(await resProxy.text())
        const proxyData = await resProxy.json()
        const flags = proxyData.high_risk_features

        // 3. Fetch Counterfactuals
        const formCF = new FormData()
        formCF.append('file', datasetFile)
        formCF.append('target_column', targetColumn)
        formCF.append('instance', activeInstanceJson)
        // Flip the actual decision: if it was rejected, we want approved (1)
        const desired = explainData.predicted_class == 1 ? 0 : 1
        formCF.append('desired_class', desired.toString())

        const resCF = await fetch(`${baseUrl}/audit/counterfactual`, { method: 'POST', body: formCF })
        const cfs = []
        if (resCF.ok) {
            const cfData = await resCF.json()
            cfData.counterfactuals.forEach(cf => cfs.push(cf.explanation))
        }

        // 4. Fetch Plain English Explanation
        const explainPlainPayload = {
            decision: actualDecision,
            top_features: feats,
            proxy_flags: flags,
            counterfactuals: cfs,
            audience: audience
        }
        
        const resPlain = await fetch(`${baseUrl}/audit/explain-plain`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(explainPlainPayload)
        })
        let plainText = ''
        if (resPlain.ok) {
            const plainData = await resPlain.json()
            plainText = plainData.explanation
        } else {
            console.warn("LLM explanation failed (API key missing?)")
        }

        setDecision(actualDecision)
        setTopFeatures(feats)
        setProxyFlags(flags)
        setCounterfactuals(cfs)
        setPlainExplanation(plainText)

    } catch (err) {
        setError(err.message || "An unexpected error occurred")
    } finally {
        setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#F9F9F7]">
      <Navbar />
      <main className="max-w-4xl mx-auto px-6 section mb-20">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">Glass Box Explainer</h1>
          <p className="mt-2 text-gray-600">
            Generate an individual applicant explanation using LLMs and SHAP.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-6 bg-white p-6 rounded-lg border border-gray-200">
          <div>
            <label className="block text-sm font-semibold text-gray-800 mb-2">Training Dataset</label>
            <DropZone
              label="Drop your training dataset CSV here"
              hint="Used to compute baseline statistics"
              file={datasetFile}
              onFile={f => setDatasetFile(f)}
            />
          </div>

          <div className="flex gap-4">
             <div className="flex-1">
                <label className="block text-sm font-semibold text-gray-800 mb-2">Target Column</label>
                <input
                    type="text"
                    value={targetColumn}
                    onChange={e => setTargetColumn(e.target.value)}
                    className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
                />
             </div>
             <div className="flex-1">
                <label className="block text-sm font-semibold text-gray-800 mb-2">Proxy Check Columns</label>
                <input
                    type="text"
                    value={proxyCols}
                    onChange={e => setProxyCols(e.target.value)}
                    className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
                    placeholder="gender, race"
                />
             </div>
             <div className="flex-1">
                <label className="block text-sm font-semibold text-gray-800 mb-2">Target Audience</label>
                <select 
                    value={audience} 
                    onChange={e => setAudience(e.target.value)}
                    className="w-full border border-gray-300 bg-white rounded px-3 py-2 text-sm"
                >
                    <option value="hr_manager">HR Manager</option>
                    <option value="developer">Developer</option>
                    <option value="executive">Executive</option>
                </select>
             </div>
          </div>

          <div className="flex gap-4 items-start">
             <div className="flex-1">
                 <label className="block text-sm font-semibold text-gray-800 mb-2">Row Number to Explain (1-based)</label>
                 <input 
                    type="text"
                    value={applicantId}
                    onChange={e => setApplicantId(e.target.value)}
                    className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
                    placeholder="e.g. 1"
                 />
                 <p className="mt-1 text-xs text-gray-500">
                    Enter the row number from the CSV (1 for the first applicant, 2 for the second, etc.)
                 </p>
             </div>
             
             {csvPreview && (() => {
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
                 <div className="flex-[2_2_0%] border border-gray-200 rounded-md bg-gray-50 overflow-hidden flex flex-col">
                     <div className="bg-gray-100 px-3 py-2 border-b border-gray-200 flex flex-col gap-2">
                         <div className="flex justify-between items-center text-xs font-semibold text-gray-700">
                             <span>Live Data Preview</span>
                             <span className="font-normal text-gray-500">
                                {isSearching ? `Found ${filteredTokens.length} matches` : `Total ${csvPreview.total} rows`}
                             </span>
                         </div>
                         <div className="flex gap-2">
                             <input 
                                type="text"
                                placeholder="Search by name, value, etc..."
                                value={previewSearch}
                                onChange={e => { setPreviewSearch(e.target.value); setPreviewPage(0); }}
                                className="w-full border border-gray-300 rounded px-2 py-1 text-xs"
                             />
                         </div>
                     </div>
                     <div className="max-h-[180px] overflow-auto flex-1 bg-white">
                         <table className="w-full text-left text-xs whitespace-nowrap">
                             <thead className="bg-white sticky top-0 shadow-[0_1px_2px_rgba(0,0,0,0.05)] z-10">
                                 <tr>
                                     <th className="px-3 py-2 text-gray-400 font-normal border-b border-gray-100">#</th>
                                     {csvPreview.headers.map((h, i) => (
                                         <th key={i} className="px-3 py-2 font-semibold text-gray-600 border-b border-gray-100">{h}</th>
                                     ))}
                                 </tr>
                             </thead>
                             <tbody className="divide-y divide-gray-50">
                                 {paginatedRows.length === 0 ? (
                                    <tr><td colSpan={csvPreview.headers.length + 1} className="p-4 text-center text-gray-400 italic">No matching rows</td></tr>
                                 ) : (
                                     paginatedRows.map((item, i) => {
                                         const rowNum = item.originalIndex;
                                         const isSelected = rowNum.toString() === applicantId;
                                         return (
                                             <tr 
                                                key={i} 
                                                onClick={() => setApplicantId(rowNum.toString())}
                                                className={`cursor-pointer transition-colors ${isSelected ? 'bg-blue-50/80 hover:bg-blue-100/80' : 'hover:bg-gray-50 bg-white'}`}
                                             >
                                                 <td className={`px-3 py-1.5 font-medium ${isSelected ? 'text-blue-600 border-l-2 border-blue-500' : 'text-gray-400 border-l-2 border-transparent'}`}>{rowNum}</td>
                                                 {item.row.map((cell, j) => (
                                                     <td key={j} className={`px-3 py-1.5 truncate max-w-[120px] ${isSelected ? 'text-blue-800' : 'text-gray-600'}`} title={cell}>
                                                         {cell}
                                                     </td>
                                                 ))}
                                             </tr>
                                         )
                                     })
                                 )}
                             </tbody>
                         </table>
                     </div>
                     {totalPages > 1 && (
                         <div className="bg-gray-50 px-3 py-2 border-t border-gray-200 flex justify-between items-center text-xs">
                             <button type="button" onClick={() => setPreviewPage(p => Math.max(0, p - 1))} disabled={currentPage === 0} className="px-2 py-1 text-gray-600 hover:text-gray-900 disabled:text-gray-300">
                                 &larr; Prev
                             </button>
                             <span className="text-gray-500">Page {currentPage + 1} of {totalPages}</span>
                             <button type="button" onClick={() => setPreviewPage(p => Math.min(totalPages - 1, p + 1))} disabled={currentPage >= totalPages - 1} className="px-2 py-1 text-gray-600 hover:text-gray-900 disabled:text-gray-300">
                                 Next &rarr;
                             </button>
                         </div>
                     )}
                 </div>
                 )
             })()}
          </div>

          {error && <div className="text-red-600 text-sm">{error}</div>}

          <button
            type="submit"
            disabled={loading}
            className="self-start inline-flex items-center gap-3 bg-accent hover:bg-accent-hover text-white px-6 py-2 rounded font-medium disabled:opacity-60"
          >
            {loading ? <><Spinner size={16} /> Generating...</> : "Generate Explanation"}
          </button>
        </form>

        {decision && (
            <div className="mt-12">
                <GlassBoxViewer 
                   decision={decision}
                   top_features={topFeatures}
                   proxy_flags={proxyFlags}
                   counterfactuals={counterfactuals}
                   plain_explanation={plainExplanation}
                   applicantId="app-demo-1"
                />
            </div>
        )}
      </main>
    </div>
  )
}

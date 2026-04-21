import { useState } from 'react'
import Navbar from '../components/Navbar'
import DropZone from '../components/DropZone'
import Spinner from '../components/Spinner'
import GlassBoxViewer from '../components/GlassBoxViewer'

export default function ExplainPage() {
  const [datasetFile, setDatasetFile] = useState(null)
  const [targetColumn, setTargetColumn] = useState('prediction')
  const [applicantId, setApplicantId] = useState('APP-0005')
  const [audience, setAudience] = useState('hr_manager')
  const [proxyCols, setProxyCols] = useState('gender')

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  
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
            const lines = fileText.split(/\r?\n/)
            const headers = lines[0].split(',').map(s => s.trim())
            let targetRow = null
            for (let i = 1; i < lines.length; i++) {
                const line = lines[i]
                if (!line.trim()) continue
                const fields = line.split(',')
                if (fields[0].trim() === applicantId.trim()) {
                    targetRow = fields
                    break
                }
            }
            if (!targetRow) throw new Error(`Applicant ID '${applicantId}' not found in the dataset.`)
            let extractedJson = {}
            targetRow.forEach((val, idx) => {
                const header = headers[idx]
                if (header !== targetColumn && header !== 'applicant_id' && header !== 'ground_truth') {
                    const num = Number(val)
                    extractedJson[header] = isNaN(num) ? val.trim() : num
                }
            })
            activeInstanceJson = JSON.stringify(extractedJson)
        } catch (e) {
            throw new Error(`Failed to extract applicant data: ${e.message}`)
        }

        // 1. Fetch SHAP Explain
        const formExplain = new FormData()
        formExplain.append('file', datasetFile)
        formExplain.append('target_column', targetColumn)
        formExplain.append('instance', activeInstanceJson)
        formExplain.append('top_n', '5')

        const resExplain = await fetch('http://localhost:8000/audit/explain', { method: 'POST', body: formExplain })
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

        const resProxy = await fetch('http://localhost:8000/audit/proxies', { method: 'POST', body: formProxy })
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

        const resCF = await fetch('http://localhost:8000/audit/counterfactual', { method: 'POST', body: formCF })
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
        
        const resPlain = await fetch('http://localhost:8000/audit/explain-plain', {
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

          <div>
             <label className="block text-sm font-semibold text-gray-800 mb-2">Applicant ID to Explain</label>
             <input 
                type="text"
                value={applicantId}
                onChange={e => setApplicantId(e.target.value)}
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
                placeholder="e.g. APP-0005"
             />
             <p className="mt-1 text-xs text-gray-500">The system will automatically locate this applicant's profile from the dataset and analyze it.</p>
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

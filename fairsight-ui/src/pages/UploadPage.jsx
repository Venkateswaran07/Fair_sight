import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import DropZone from '../components/DropZone'
import Spinner from '../components/Spinner'

const API_URL = 'http://localhost:8000/audit/demographics'

/* ──────────────────────────────────────────────────────────────────────────
   UploadPage — Screen 1
   - Drag-and-drop zone: training dataset CSV
   - Drag-and-drop zone: predictions CSV (needs prediction + ground_truth cols)
   - Text input: comma-separated protected column names
   - Submit → POST /audit/demographics via FormData
   - States: idle → loading → success | error
────────────────────────────────────────────────────────────────────────── */

/** Inline field error message. */
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
  const [result, setResult]     = useState(null)   // success payload
  const [error, setError]       = useState(null)   // error string
  const [fieldErrors, setFieldErrors] = useState({})

  /* ── Validation ──────────────────────────────────────────────── */
  function validate() {
    const errs = {}
    if (!datasetFile) errs.dataset = 'Please upload a training dataset CSV.'
    if (!predictFile) errs.predict = 'Please upload a predictions CSV.'
    if (!protectedCols.trim()) errs.cols = 'Enter at least one protected column name.'
    setFieldErrors(errs)
    return Object.keys(errs).length === 0
  }

  /* ── Submit ──────────────────────────────────────────────────── */
  async function handleSubmit(e) {
    e.preventDefault()
    if (!validate()) return

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      // Parse protected_columns into a JSON array string as the API expects
      const cols = protectedCols
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean)

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
      // The fairness endpoint only analyzes a single binary column at a time, so we pass the first one.
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

      // Fetch all four endpoints in parallel
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

  /* ── Success banner ──────────────────────────────────────────── */
  if (result) {
    return (
      <div className="min-h-screen bg-[#F9F9F7]">
        <Navbar />
        <main className="max-w-2xl mx-auto px-6 section">
          <div className="border border-green-200 bg-green-50 rounded-lg p-6 text-center">
            {/* Check icon */}
            <svg className="w-10 h-10 text-green-500 mx-auto" fill="none" stroke="currentColor"
                 strokeWidth={1.5} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round"
                    d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
            </svg>
            <h2 className="mt-4 text-xl font-semibold text-gray-900">Audit ready</h2>
            <p className="mt-2 text-gray-600">
              Analysed <strong>{result.demographics?.num_rows?.toLocaleString()}</strong> rows
              across <strong>{result.demographics?.columns_analyzed?.length ?? 0}</strong> protected column(s).
              {result.missing_columns?.length > 0 && (
                <span className="block mt-1 text-yellow-700 text-sm">
                  Columns not found in CSV: {result.missing_columns.join(', ')}
                </span>
              )}
            </p>

            <div className="mt-6 flex flex-col sm:flex-row gap-3 justify-center">
              <button
                onClick={() => {
                  sessionStorage.setItem('fairsight_results', JSON.stringify(result))
                  navigate('/results')
                }}
                className="bg-accent hover:bg-accent-hover text-white font-medium
                           px-6 py-2.5 rounded transition-colors"
              >
                View results
              </button>
              <button
                onClick={() => { setResult(null); setDatasetFile(null); setPredictFile(null); setProtectedCols('') }}
                className="border border-gray-300 text-gray-700 hover:bg-gray-100
                           font-medium px-6 py-2.5 rounded transition-colors"
              >
                New audit
              </button>
            </div>

            {/* Raw JSON for devs */}
            <details className="mt-6 text-left">
              <summary className="text-xs text-gray-400 cursor-pointer select-none hover:text-gray-600">
                Show raw API response
              </summary>
              <pre className="mt-2 text-xs bg-white border border-gray-200 rounded p-4
                              overflow-auto max-h-64 text-gray-700">
                {JSON.stringify(result, null, 2)}
              </pre>
            </details>
          </div>
        </main>
      </div>
    )
  }

  /* ── Main form ───────────────────────────────────────────────── */
  return (
    <div className="min-h-screen bg-[#F9F9F7]">
      <Navbar />

      <main className="max-w-2xl mx-auto px-6 section">
        {/* Page header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">Upload your data</h1>
          <p className="mt-2 text-gray-600">
            Provide your dataset, your model's predictions, and the columns you
            want to audit for bias.
          </p>
        </div>

        <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-7">

          {/* ── Zone 1: Training dataset ──────────────────────── */}
          <div>
            <label className="block text-sm font-semibold text-gray-800 mb-2">
              Training dataset
            </label>
            <DropZone
              label="Drop your dataset CSV here"
              hint="Any columns; used for demographics & proxy analysis"
              file={datasetFile}
              onFile={(f) => { setDatasetFile(f); setFieldErrors((e) => ({ ...e, dataset: '' })) }}
            />
            <FieldError msg={fieldErrors.dataset} />
          </div>

          {/* ── Zone 2: Predictions CSV ───────────────────────── */}
          <div>
            <label className="block text-sm font-semibold text-gray-800 mb-2">
              Predictions CSV
              <span className="ml-2 text-xs font-normal text-gray-500">
                (requires <code className="bg-gray-100 px-1 rounded">prediction</code>
                and <code className="bg-gray-100 px-1 rounded">ground_truth</code> columns)
              </span>
            </label>
            <DropZone
              label="Drop your predictions CSV here"
              hint="Must contain: prediction, ground_truth, + any protected columns"
              file={predictFile}
              onFile={(f) => { setPredictFile(f); setFieldErrors((e) => ({ ...e, predict: '' })) }}
            />
            <FieldError msg={fieldErrors.predict} />
          </div>

          {/* ── Protected columns input ───────────────────────── */}
          <div>
            <label
              htmlFor="protected-cols"
              className="block text-sm font-semibold text-gray-800 mb-2"
            >
              Protected columns
            </label>
            <input
              id="protected-cols"
              type="text"
              placeholder="gender, race, age"
              value={protectedCols}
              onChange={(e) => {
                setProtectedCols(e.target.value)
                setFieldErrors((err) => ({ ...err, cols: '' }))
              }}
              className="w-full border border-gray-300 rounded-lg px-4 py-2.5 text-sm
                         text-gray-900 placeholder-gray-400 bg-white
                         focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent"
            />
            <p className="mt-1.5 text-xs text-gray-500">
              Comma-separated column names that contain protected attributes.
            </p>
            <FieldError msg={fieldErrors.cols} />
          </div>

          {/* ── Error banner ──────────────────────────────────── */}
          {error && (
            <div role="alert" className="border border-red-200 bg-red-50
                                         rounded-lg px-4 py-3 text-sm text-red-700">
              <strong className="font-semibold">Request failed: </strong>{error}
            </div>
          )}

          {/* ── Submit ────────────────────────────────────────── */}
          <div>
            <button
              type="submit"
              disabled={loading}
              className="inline-flex items-center gap-3 bg-accent hover:bg-accent-hover
                         disabled:opacity-60 disabled:cursor-not-allowed
                         text-white font-medium px-6 py-2.5 rounded transition-colors"
            >
              {loading ? (
                <>
                  <Spinner size={16} label="Running audit…" />
                  <span>Running audit…</span>
                </>
              ) : (
                'Submit for audit'
              )}
            </button>
          </div>

          {/* ── Note ──────────────────────────────────────────── */}
          <p className="text-xs text-gray-400">
            Files are sent to your local FairSight API at{' '}
            <code className="bg-gray-100 px-1 rounded">localhost:8000</code>.
            Nothing is stored remotely.
          </p>
        </form>
      </main>
    </div>
  )
}

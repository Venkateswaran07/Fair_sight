import { useRef, useState } from 'react'

/**
 * Reusable drag-and-drop file zone.
 *
 * Props
 * -----
 * label       string   — visible heading
 * hint        string   — helper text below label
 * accept      string   — MIME type filter, e.g. ".csv"
 * file        File|null
 * onFile      (File) => void
 */
export default function DropZone({ label, hint, accept = '.csv', file, onFile, loading = false }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)

  function handleDrop(e) {
    e.preventDefault()
    if (loading) return
    setDragging(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped) onFile(dropped)
  }

  function handleChange(e) {
    if (loading) return
    const chosen = e.target.files[0]
    if (chosen) onFile(chosen)
  }

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={`Upload zone: ${label}. ${file ? `Selected: ${file.name}` : 'No file selected.'}`}
      onClick={() => !loading && inputRef.current.click()}
      onKeyDown={(e) => e.key === 'Enter' && !loading && inputRef.current.click()}
      onDragOver={(e) => { e.preventDefault(); if (!loading) setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={[
        'border-2 border-dashed rounded-lg px-6 py-8 cursor-pointer select-none',
        'transition-colors duration-150',
        loading
          ? 'border-blue-400 bg-blue-50 cursor-wait'
          : dragging
          ? 'border-accent bg-blue-50'
          : file
          ? 'border-green-400 bg-green-50'
          : 'border-gray-300 bg-white hover:border-accent hover:bg-blue-50',
      ].join(' ')}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={handleChange}
        aria-hidden="true"
        disabled={loading}
      />

      <div className="flex flex-col items-center gap-2 text-center pointer-events-none">
        {loading ? (
          <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        ) : file ? (
          <svg className="w-8 h-8 text-green-500" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
          </svg>
        ) : (
          <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5" />
          </svg>
        )}

        <p className="text-sm font-medium text-gray-900">{loading ? 'Uploading...' : label}</p>

        {loading ? (
          <p className="text-xs text-blue-600 animate-pulse">Please wait for 90MB file...</p>
        ) : file ? (
          <p className="text-xs text-green-700 font-medium">{file.name}</p>
        ) : (
          <>
            <p className="text-xs text-gray-500">
              Drag & drop or <span className="text-accent font-medium">browse</span>
            </p>
            {hint && <p className="text-xs text-gray-400 mt-1">{hint}</p>}
          </>
        )}
      </div>
    </div>
  )
}

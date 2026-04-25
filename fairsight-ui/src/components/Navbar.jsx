import { Link, useLocation } from 'react-router-dom'

export default function Navbar() {
  const { pathname } = useLocation()

  return (
    <header className="bg-[#F9F9F7] border-b border-gray-200 sticky top-0 z-50">
      <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2 font-semibold text-gray-900">
          {/* Simple geometric mark — no orbs, no gradients */}
          <span className="inline-block w-6 h-6 bg-accent rounded-sm" aria-hidden="true" />
          FairSight <span className="text-[10px] font-normal text-gray-400 ml-1">Powered by Vertex AI</span>
        </Link>

        {/* Nav items */}
        <nav className="flex items-center gap-6 text-sm text-gray-600">
          <div className="flex items-center gap-1.5 text-[10px] bg-green-50 text-green-700 px-2 py-0.5 rounded border border-green-100">
            <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse"></span>
            Firestore DB Connected
          </div>
          <Link
            to="/explain"
            className="hover:text-gray-900 transition-colors font-medium text-blue-700 hover:bg-blue-50 px-3 py-1.5 rounded"
          >
            Glass Box Demo
          </Link>
          <Link
            to="/audit-history"
            className="hover:text-gray-900 transition-colors font-medium"
          >
            History
          </Link>
          <a
            href={`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/docs`}
            target="_blank"
            rel="noreferrer"
            className="hover:text-gray-900 transition-colors"
          >
            API Docs
          </a>
          <Link
            to="/upload"
            className={`px-4 py-1.5 rounded text-sm font-medium transition-colors ${
              pathname === '/upload'
                ? 'bg-accent text-white'
                : 'bg-accent text-white hover:bg-accent-hover'
            }`}
          >
            Start Audit
          </Link>
        </nav>
      </div>
    </header>
  )
}

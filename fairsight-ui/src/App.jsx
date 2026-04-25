import React from 'react'
import { Routes, Route } from 'react-router-dom'
import LandingPage from './pages/LandingPage'
import UploadPage from './pages/UploadPage'
import ResultsPage from './pages/ResultsPage'
import ExplainPage from './pages/ExplainPage'
import HistoryPage from './pages/HistoryPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/upload" element={<UploadPage />} />
      <Route path="/results" element={<ResultsPage />} />
      <Route path="/explain" element={<ExplainPage />} />
      <Route path="/audit-history" element={<HistoryPage />} />
      <Route path="*" element={<div style={{padding: '20px'}}><h1>404 Not Found</h1><a href="/">Back Home</a></div>} />
    </Routes>
  )
}

export default App

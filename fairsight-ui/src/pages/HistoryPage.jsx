import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import Spinner from '../components/Spinner';

const HISTORY_URL = 'http://localhost:8000/audit/history';

export default function HistoryPage() {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    fetchHistory();
  }, []);

  async function fetchHistory() {
    setLoading(true);
    const PRODUCTION_BACKEND_URL = 'https://fairsight-backend-403339568263.us-central1.run.app';
    const baseUrl = import.meta.env.VITE_API_URL || (window.location.hostname === 'localhost' ? 'http://localhost:8000' : PRODUCTION_BACKEND_URL);
    try {
      const res = await fetch(`${baseUrl}/audit/history`);
      if (!res.ok) throw new Error('Failed to fetch history');
      const data = await res.json();
      setHistory(Array.isArray(data.history) ? data.history : []);
    } catch (err) {
      console.error("History fetch error:", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const isFair = (assessment) => (assessment || '').startsWith('FAIR');

  return (
    <div className="min-h-screen bg-[#F9F9F7] flex flex-col">
      <Navbar />
      
      <main className="flex-1 max-w-5xl w-full mx-auto px-6 py-12">
        <div className="mb-10">
          <h1 className="text-3xl font-bold text-gray-900">Audit History</h1>
          <p className="mt-2 text-gray-600">Review all fairness audits performed on the FairSight platform.</p>
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 bg-white rounded-2xl border border-gray-200 shadow-sm">
            <Spinner size={40} />
            <p className="mt-4 text-gray-500 font-medium text-blue-600">Fetching records from Firestore...</p>
          </div>
        ) : error ? (
          <div className="p-6 bg-red-50 border border-red-200 rounded-xl text-red-800">
            <h3 className="font-bold">Error loading history</h3>
            <p className="text-sm">{error}</p>
            <button onClick={fetchHistory} className="mt-4 px-4 py-2 bg-red-100 hover:bg-red-200 rounded-lg text-sm font-semibold transition-colors">
              Try Again
            </button>
          </div>
        ) : history.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 bg-white rounded-2xl border border-gray-200 shadow-sm text-center px-6">
            <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4">
              <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <h3 className="text-xl font-bold text-gray-900">No audits yet</h3>
            <p className="mt-2 text-gray-500 max-w-sm">Your fairness audit results will appear here automatically once you upload and analyze a dataset.</p>
            <button onClick={() => navigate('/upload')} className="mt-8 px-6 py-3 bg-blue-600 text-white font-bold rounded-xl shadow-lg hover:bg-blue-700 transition-all transform hover:-translate-y-0.5 active:scale-95">
              Start New Audit
            </button>
          </div>
        ) : (
          <div className="grid gap-4">
            {history.map((record) => (
              <div 
                key={record.session_id || Math.random().toString()}
                className="group relative bg-white border border-gray-200 rounded-2xl p-6 shadow-sm hover:shadow-md transition-all cursor-pointer"
                onClick={() => navigate(`/results?session_id=${record.session_id}`)}
              >
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-1">
                      <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider ${
                        isFair(record.fairness_assessment) ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                      }`}>
                        {isFair(record.fairness_assessment) ? '✓ Fair' : '⚠ Biased'}
                      </span>
                      <span className="text-xs text-gray-400 font-mono">{(record.session_id || '').slice(0, 8)}</span>
                    </div>
                    <h3 className="text-lg font-bold text-gray-900 truncate">
                      {(record.protected_attributes || []).join(', ') || 'Dataset'} Audit
                    </h3>
                    <div className="mt-1 flex items-center gap-4 text-sm text-gray-500">
                      <span className="flex items-center gap-1.5">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" /></svg>
                        {(record.num_rows || 0).toLocaleString()} rows
                      </span>
                      <span className="flex items-center gap-1.5">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                        {record.timestamp ? new Date(record.timestamp).toLocaleDateString() : 'Unknown Date'}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-8 text-right">
                    <div className="hidden sm:block">
                      <p className="text-[10px] uppercase font-bold text-gray-400 tracking-wider">Disparate Impact</p>
                      <p className={`text-xl font-mono font-bold ${isFair(record.fairness_assessment) ? 'text-green-600' : 'text-red-600'}`}>
                        {record.metrics?.disparate_impact !== undefined ? Number(record.metrics.disparate_impact).toFixed(3) : 'N/A'}
                      </p>
                    </div>
                    <div className="flex items-center justify-center w-10 h-10 rounded-full bg-gray-50 text-gray-400 group-hover:bg-blue-50 group-hover:text-blue-500 transition-colors">
                      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

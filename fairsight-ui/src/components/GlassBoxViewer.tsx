import React, { useState } from 'react'
import Spinner from './Spinner'

const REVIEW_URL = 'http://localhost:8000/audit/review'

/**
 * ════════════════════════════════════════════════════════════════════════
 *  Interfaces
 * ════════════════════════════════════════════════════════════════════════
 */

export interface SHAPFeature {
  feature: string;
  shap_value: number;
  contribution_percent: number;
  direction?: "Positive" | "Negative";
}

export interface GlassBoxViewerProps {
  decision?: 'APPROVED' | 'REJECTED';
  top_features?: SHAPFeature[];
  proxy_flags?: string[];
  counterfactuals?: string[];
  plain_explanation?: string;
  applicantId?: string | null;
  onReviewed?: () => void;
}

/* ════════════════════════════════════════════════════════════════════════
   Decision Badge
════════════════════════════════════════════════════════════════════════ */

const DecisionBadge: React.FC<{ decision: 'APPROVED' | 'REJECTED' }> = ({ decision }) => {
  const approved = decision === 'APPROVED'

  return (
    <div className={[
      'flex flex-col items-center justify-center gap-2 rounded-xl px-10 py-7 w-full',
      approved ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200',
    ].join(' ')}>
      {approved ? (
        <svg className="w-10 h-10 text-green-500" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
        </svg>
      ) : (
        <svg className="w-10 h-10 text-red-500" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="m9.75 9.75 4.5 4.5m0-4.5-4.5 4.5M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
        </svg>
      )}

      <span className={['text-3xl font-bold tracking-tight', approved ? 'text-green-800' : 'text-red-800'].join(' ')}>
        {decision}
      </span>

      <span className={['text-sm font-medium', approved ? 'text-green-600' : 'text-red-600'].join(' ')}>
        {approved ? 'Application approved by model' : 'Application rejected by model'}
      </span>
    </div>
  )
}

/* ════════════════════════════════════════════════════════════════════════
   Diverging SHAP Bar Chart
════════════════════════════════════════════════════════════════════════ */

const SHAPLegend: React.FC = () => (
  <div className="flex items-center justify-center gap-6 mb-4 text-xs text-gray-500">
    <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded-sm bg-red-500" /><span>Pushed toward rejection</span></div>
    <div className="w-px h-4 bg-gray-200" />
    <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded-sm bg-green-500" /><span>Pushed toward approval</span></div>
  </div>
)

const SHAPBarRow: React.FC<{ feat: SHAPFeature; maxAbsShap: number; proxySet: Set<string> }> = ({ feat, maxAbsShap, proxySet }) => {
  const isProxy = proxySet.has(feat.feature)
  const isPositive = feat.shap_value >= 0
  const halfPct = maxAbsShap > 0 ? (Math.abs(feat.shap_value) / maxAbsShap) * 100 : 0
  const shapFormatted = `${isPositive ? '+' : ''}${feat.shap_value.toFixed(3)}`

  return (
    <div className="flex items-center gap-2 py-2.5 border-b border-gray-100 last:border-0">
      <div className="w-[28%] flex items-center justify-end gap-1.5 pr-2 flex-shrink-0 min-w-0">
        {isProxy && <span title="This feature may be a proxy" className="text-amber-500 flex-shrink-0 text-base leading-none">⚠</span>}
        <span className={['text-sm font-mono truncate', isProxy ? 'text-amber-700 font-semibold' : 'text-gray-800'].join(' ')}>{feat.feature}</span>
      </div>

      <div className="flex-1 flex items-center min-w-0">
        <div className="flex-1 flex justify-end items-center h-7 min-w-0">
          {!isPositive && <div className="h-5 bg-red-500 rounded-l-sm transition-all duration-300" style={{ width: `${halfPct}%` }} />}
        </div>
        <div className="w-px h-9 bg-gray-300 flex-shrink-0 mx-0" />
        <div className="flex-1 flex justify-start items-center h-7 min-w-0">
          {isPositive && <div className="h-5 bg-green-500 rounded-r-sm transition-all duration-300" style={{ width: `${halfPct}%` }} />}
        </div>
      </div>

      <div className={['w-14 text-right text-xs font-mono flex-shrink-0', isPositive ? 'text-green-700' : 'text-red-700'].join(' ')}>
        {shapFormatted}
      </div>
      <div className="w-10 text-right text-xs text-gray-400 flex-shrink-0">
        {feat.contribution_percent?.toFixed(1)}%
      </div>
    </div>
  )
}

const SHAPSection: React.FC<{ top_features: SHAPFeature[]; proxy_flags: string[] }> = ({ top_features, proxy_flags }) => {
  if (!top_features?.length) return null
  const proxySet = new Set(proxy_flags ?? [])
  const maxAbsShap = Math.max(...top_features.map((f) => Math.abs(f.shap_value)))

  return (
    <div>
      <SectionHeading title="Feature Impact" subtitle="How each feature moved the model's decision — measured by SHAP value." />
      <SHAPLegend />
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        {top_features.map((feat) => <SHAPBarRow key={feat.feature} feat={feat} maxAbsShap={maxAbsShap} proxySet={proxySet} />)}
      </div>
      {proxy_flags?.length > 0 && (
        <div className="mt-3 flex gap-2 px-4 py-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
          <span className="flex-shrink-0 text-amber-500 font-bold">⚠</span>
          <span><strong>Proxy risk:</strong> {proxy_flags.join(', ')} {proxy_flags.length === 1 ? 'is' : 'are'} statistically correlated with protected attributes and may encode indirect bias.</span>
        </div>
      )}
    </div>
  )
}

/* ════════════════════════════════════════════════════════════════════════
   Counterfactuals & Explanations
════════════════════════════════════════════════════════════════════════ */

const CounterfactualsSection: React.FC<{ counterfactuals: string[]; decision: 'APPROVED'|'REJECTED' }> = ({ counterfactuals, decision }) => {
  if (!counterfactuals?.length) return null
  return (
    <div>
      <SectionHeading
        title={decision === 'APPROVED' ? "Vulnerability Test (What Would Reject This)" : "What Would Change This Decision"}
        subtitle={decision === 'APPROVED' ? "Minimal hypothetical changes that would flip the outcome to REJECTED." : "Minimal hypothetical changes that would flip the outcome to APPROVED."}
      />
      <ol className="flex flex-col gap-3">
        {counterfactuals.map((cf, i) => (
          <li key={i} className="flex items-start gap-3 px-4 py-3.5 bg-white border border-gray-200 rounded-lg">
            <span className="flex-shrink-0 flex items-center justify-center w-5 h-5 rounded-full bg-blue-100 text-blue-700 text-xs font-bold mt-0.5">{i + 1}</span>
            <span className="text-sm text-gray-800 leading-relaxed">{cf}</span>
          </li>
        ))}
      </ol>
    </div>
  )
}

const ExplanationSection: React.FC<{ plain_explanation: string }> = ({ plain_explanation }) => {
  if (!plain_explanation) return null
  return (
    <div>
      <SectionHeading title="Plain English Explanation" subtitle="Generated by Gemini 2.5 Flash via Google AI Studio — summarises the decision for a non-technical reader." />
      <blockquote className="relative px-6 py-5 bg-white border-l-4 border-blue-700 border border-t border-r border-b-gray-200 rounded-r-lg">
        <span className="absolute top-3 left-3 text-4xl text-blue-100 font-serif leading-none pointer-events-none select-none" aria-hidden>"</span>
        <p className="text-gray-800 text-[0.95rem] leading-relaxed pl-4">{plain_explanation}</p>
        <footer className="mt-3 pl-4">
          <span className="text-xs text-gray-400 font-medium tracking-wide uppercase">Google AI Studio · Gemini 2.5 Flash</span>
        </footer>
      </blockquote>
    </div>
  )
}

/* ════════════════════════════════════════════════════════════════════════
   Review Actions
════════════════════════════════════════════════════════════════════════ */

const ReviewActions: React.FC<{ decision: 'APPROVED'|'REJECTED'; applicantId?: string | null; onReviewed?: () => void }> = ({ decision, applicantId, onReviewed }) => {
  const [state, setState] = useState<{ loading: boolean; done: "flagged" | "reviewed" | null; error: string | null }>({ loading: false, done: null, error: null })

  async function handleAction(status: "flagged" | "reviewed") {
    setState({ loading: true, done: null, error: null })
    try {
      const res = await fetch(REVIEW_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision, status, ...(applicantId ? { applicant_id: applicantId } : {}) }),
      })
      if (!res.ok) {
        const detail = await res.json().then((d) => d.detail).catch(() => `HTTP ${res.status}`)
        throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
      }
      setState({ loading: false, done: status, error: null })
      onReviewed?.()
    } catch (err: any) {
      setState({ loading: false, done: null, error: err.message })
    }
  }

  if (state.done) {
    return (
      <div className={['flex items-center gap-2 px-4 py-3 rounded-lg text-sm font-medium', state.done === 'flagged' ? 'bg-amber-50 border border-amber-200 text-amber-800' : 'bg-green-50 border border-green-200 text-green-800'].join(' ')}>
        <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" /></svg>
        {state.done === 'flagged' ? 'Flagged as concerning — a reviewer will follow up.' : 'Marked as reviewed — no further action needed.'}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      {state.error && <p role="alert" className="text-xs text-red-600 px-1">Action failed: {state.error}</p>}
      <div className="flex flex-col sm:flex-row gap-3">
        <button disabled={state.loading} onClick={() => handleAction('flagged')} className="flex-1 flex items-center justify-center gap-2 border border-amber-400 bg-amber-50 text-amber-800 hover:bg-amber-100 disabled:opacity-60 disabled:cursor-not-allowed font-medium text-sm px-5 py-2.5 rounded-lg transition-colors">
          {state.loading ? <Spinner size={14} label="Submitting…" /> : <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M3 3v1.5M3 21v-6m0 0 2.77-.693a9 9 0 0 1 6.208.682l.108.054a9 9 0 0 0 6.086.71l3.114-.732a48.524 48.524 0 0 1-.005-10.499l-3.11.732a9 9 0 0 1-6.085-.711l-.108-.054a9 9 0 0 0-6.208-.682L3 4.5M3 15V4.5" /></svg>} Flag as concerning
        </button>
        <button disabled={state.loading} onClick={() => handleAction('reviewed')} className="flex-1 flex items-center justify-center gap-2 border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-60 disabled:cursor-not-allowed font-medium text-sm px-5 py-2.5 rounded-lg transition-colors">
          {state.loading ? <Spinner size={14} label="Submitting…" /> : <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" /></svg>} Mark as reviewed
        </button>
      </div>
    </div>
  )
}

/* ════════════════════════════════════════════════════════════════════════
   Shared
════════════════════════════════════════════════════════════════════════ */

const SectionHeading: React.FC<{ title: string; subtitle?: string }> = ({ title, subtitle }) => (
  <div className="mb-4">
    <h2 className="text-xs font-semibold uppercase tracking-wider text-blue-700">{title}</h2>
    {subtitle && <p className="mt-0.5 text-sm text-gray-500">{subtitle}</p>}
  </div>
)

const Divider: React.FC = () => <hr className="border-gray-200" />

/* ════════════════════════════════════════════════════════════════════════
   Root component
════════════════════════════════════════════════════════════════════════ */

const GlassBoxViewer: React.FC<GlassBoxViewerProps> = ({
  decision = 'REJECTED',
  top_features = [],
  proxy_flags = [],
  counterfactuals = [],
  plain_explanation = '',
  applicantId = null,
  onReviewed = undefined,
}) => {
  return (
    <article className="max-w-2xl mx-auto bg-[#F9F9F7] font-sans" aria-label="Applicant fairness explanation">
      <DecisionBadge decision={decision} />
      <div className="mt-8 flex flex-col gap-8">
        <SHAPSection top_features={top_features} proxy_flags={proxy_flags} />
        <Divider />
        {counterfactuals.length > 0 && (
          <>
            <CounterfactualsSection counterfactuals={counterfactuals} decision={decision} />
            <Divider />
          </>
        )}
        {plain_explanation && (
          <>
            <ExplanationSection plain_explanation={plain_explanation} />
            <Divider />
          </>
        )}
        <div>
          <SectionHeading title="Reviewer Actions" subtitle="Record your assessment of this decision." />
          <ReviewActions decision={decision} applicantId={applicantId} onReviewed={onReviewed} />
        </div>
      </div>
    </article>
  )
}

export default GlassBoxViewer

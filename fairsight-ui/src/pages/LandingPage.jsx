import { Link } from 'react-router-dom'
import Navbar from '../components/Navbar'

/* ──────────────────────────────────────────────────────────────────────────
   LandingPage
   Design rules enforced:
   - Single flat background #F9F9F7, single accent #1D4ED8
   - No gradients, glassmorphism, floating orbs, or decorative blurs
   - No fake testimonials, no generic icon-trio cards
   - Consistent 5rem vertical section rhythm
   - body line-height set globally (index.css)
   - "Proof" section shows a real sample audit result, not a mockup screengrab
   - Font: Inter (loaded in index.html)
────────────────────────────────────────────────────────────────────────── */

/** One pipeline step — numbered, text only. */
function Step({ n, title, body }) {
  return (
    <div className="flex gap-5">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-accent text-white
                      flex items-center justify-center text-sm font-semibold mt-0.5">
        {n}
      </div>
      <div>
        <p className="font-semibold text-gray-900">{title}</p>
        <p className="text-gray-600 mt-1">{body}</p>
      </div>
    </div>
  )
}

/** One metric row inside the sample audit card. */
function MetricRow({ label, value, status }) {
  const dot = status === 'FAIL'
    ? 'bg-red-500'
    : status === 'PASS'
      ? 'bg-green-500'
      : 'bg-yellow-400'

  return (
    <div className="flex items-center justify-between py-2.5 border-b border-gray-100 last:border-0">
      <span className="text-sm text-gray-700">{label}</span>
      <div className="flex items-center gap-3">
        <span className="text-sm font-mono text-gray-900">{value}</span>
        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${dot}`} aria-label={status} />
        <span className={`text-xs font-medium ${status === 'FAIL' ? 'text-red-600' :
          status === 'PASS' ? 'text-green-600' : 'text-yellow-600'
          }`}>{status}</span>
      </div>
    </div>
  )
}

/** Sample audit output — real schema, real values, clearly labelled as a sample. */
function SampleAuditCard() {
  return (
    <div className="border border-gray-200 rounded-lg bg-white overflow-hidden max-w-lg w-full">
      {/* Header bar */}
      <div className="px-5 py-3 border-b border-gray-200 flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-gray-900">hiring_decisions.csv</p>
          <p className="text-xs text-gray-500 mt-0.5">8 240 rows · protected: gender, race</p>
        </div>
        <span className="text-xs bg-red-100 text-red-700 font-medium px-2 py-0.5 rounded">
          3 metrics failing
        </span>
      </div>

      {/* Fairness metrics */}
      <div className="px-5 pt-3 pb-1">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">
          Fairness Metrics
        </p>
        <MetricRow label="Demographic Parity Difference" value="0.19" status="FAIL" />
        <MetricRow label="Equal Opportunity Difference" value="0.14" status="FAIL" />
        <MetricRow label="Disparate Impact Ratio" value="0.71" status="FAIL" />
      </div>

      {/* Proxy risk */}
      <div className="px-5 pt-3 pb-1 border-t border-gray-100">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">
          Proxy Risk
        </p>
        <div className="flex items-center justify-between py-2">
          <span className="text-sm text-gray-700 font-mono">zip_code</span>
          <div className="flex items-center gap-2">
            <span className="text-sm font-mono text-gray-900">0.73</span>
            <span className="text-xs font-medium text-red-600 bg-red-50 px-1.5 py-0.5 rounded">
              HIGH RISK
            </span>
          </div>
        </div>
      </div>

      {/* Top SHAP feature */}
      <div className="px-5 pt-3 pb-4 border-t border-gray-100">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">
          Top Feature (SHAP #1)
        </p>
        <div className="flex items-center justify-between py-2">
          <span className="text-sm text-gray-700 font-mono">credit_score</span>
          <span className="text-sm font-mono text-red-600">−0.21 → rejection</span>
        </div>
      </div>

      {/* Footer */}
      <div className="px-5 py-2.5 bg-gray-50 border-t border-gray-200">
        <p className="text-xs text-gray-400 italic">
          Sample output — actual values vary by dataset.
        </p>
      </div>
    </div>
  )
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#F9F9F7]">
      <Navbar />

      {/* ── Hero ─────────────────────────────────────────────────── */}
      <section className="section max-w-5xl mx-auto px-6">
        <div className="max-w-2xl">
          <h1 className="text-4xl font-bold text-gray-900 leading-tight">
            Audit your AI for bias<br />before it ships.
          </h1>
          <p className="mt-5 text-lg text-gray-600 leading-relaxed max-w-xl">
            FairSight measures demographic parity, equal opportunity, and proxy
            discrimination in your model's predictions — and explains each finding
            in plain language your team can act on.
          </p>
          <div className="mt-8 flex items-center gap-4">
            <Link
              to="/upload"
              className="inline-block bg-accent hover:bg-accent-hover text-white
                         font-medium px-6 py-2.5 rounded transition-colors"
            >
              Run your first audit
            </Link>
            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noreferrer"
              className="text-sm text-gray-600 hover:text-gray-900 transition-colors"
            >
              View API docs →
            </a>
          </div>
        </div>
      </section>

      {/* ── Sample output (replaces generic feature-card trio) ───── */}
      <section className="section border-t border-gray-200 bg-white">
        <div className="max-w-5xl mx-auto px-6">
          <div className="flex flex-col lg:flex-row gap-12 items-start">
            {/* Left: explanation */}
            <div className="flex-1 max-w-md">
              <p className="text-xs font-semibold text-accent uppercase tracking-wider">
                What you get
              </p>
              <h2 className="mt-3 text-2xl font-bold text-gray-900">
                A structured audit result, not a score.
              </h2>
              <p className="mt-4 text-gray-600">
                FairSight returns per-group metrics, a ranked list of proxy-risk
                features, SHAP-based feature importance for individual decisions,
                and counterfactual scenarios — all from a single CSV upload.
              </p>
              <p className="mt-3 text-gray-600">
                Every result can be narrated in plain language for an HR manager,
                a developer, or an executive at the click of a button.
              </p>
            </div>

            {/* Right: real sample output card */}
            <div className="flex-1 flex justify-center lg:justify-end">
              <SampleAuditCard />
            </div>
          </div>
        </div>
      </section>

      {/* ── How it works ─────────────────────────────────────────── */}
      <section className="section max-w-5xl mx-auto px-6">
        <p className="text-xs font-semibold text-accent uppercase tracking-wider">
          How it works
        </p>
        <h2 className="mt-3 text-2xl font-bold text-gray-900">Three steps.</h2>

        <div className="mt-8 flex flex-col gap-7 max-w-xl">
          <Step
            n="1"
            title="Upload your dataset"
            body="Provide your training CSV and your model's predictions CSV. Name the protected
                  attribute columns (gender, race, age…) in a text field. No account needed."
          />
          <Step
            n="2"
            title="FairSight runs the audit"
            body="Nine endpoints run in sequence: demographic distribution, per-group performance,
                  DPD / EOD / DIR fairness metrics, proxy detection, SHAP explanation, and
                  DiCE counterfactuals. Takes seconds on datasets up to ~100 k rows."
          />
          <Step
            n="3"
            title="Read the results in your language"
            body="Choose your audience — HR manager, developer, or executive — and FairSight
                  generates a plain-language summary using Gemini 1.5 Flash model via Google AI Studio. Then export
                  a full PDF audit report."
          />
        </div>
      </section>

      {/* ── Concrete numbers ─────────────────────────────────────── */}
      <section className="section border-t border-gray-200 bg-white">
        <div className="max-w-5xl mx-auto px-6">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-8">
            {[
              { n: '9', label: 'audit endpoints' },
              { n: '3', label: 'fairness metrics (DPD, EOD, DIR)' },
              { n: 'SHAP', label: 'feature explanations' },
              { n: 'Gemini 1.5 Flash', label: 'plain-language via Google AI' },
            ].map(({ n, label }) => (
              <div key={label}>
                <p className="text-2xl font-bold text-gray-900">{n}</p>
                <p className="mt-1 text-sm text-gray-500">{label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Footer ───────────────────────────────────────────────── */}
      <footer className="border-t border-gray-200 py-8 mt-0">
        <div className="max-w-5xl mx-auto px-6 flex flex-col sm:flex-row
                        items-start sm:items-center justify-between gap-4">
          <p className="text-sm text-gray-500">
            FairSight · AI fairness auditing
          </p>
          <div className="flex gap-6 text-sm text-gray-500">
            <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer"
              className="hover:text-gray-900 transition-colors">API Docs</a>
            <a href="http://localhost:8000/health" target="_blank" rel="noreferrer"
              className="hover:text-gray-900 transition-colors">Health</a>
          </div>
        </div>
      </footer>
    </div>
  )
}

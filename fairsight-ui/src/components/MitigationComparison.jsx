import React from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Cell, Legend
} from 'recharts'

/**
 * MitigationComparison
 * ====================
 * Displays a before vs after comparison of fairness metrics.
 * 
 * Props:
 * - data: object (The response from /audit/mitigate)
 */
export default function MitigationComparison({ data }) {
  if (!data) return null

  const metrics = [
    {
      name: 'Demographic Parity Diff',
      abbr: 'DPD',
      before: data?.before?.demographic_parity_difference || 0,
      after: data?.after?.demographic_parity_difference || 0,
      threshold: 0.1,
      lowerIsBetter: true
    },
    {
      name: 'Equal Opportunity Diff',
      abbr: 'EOD',
      before: data?.before?.equal_opportunity_difference || 0,
      after: data?.after?.equal_opportunity_difference || 0,
      threshold: 0.1,
      lowerIsBetter: true
    },
    {
      name: 'Disparate Impact Ratio',
      abbr: 'DIR',
      before: data?.before?.disparate_impact_ratio || 0,
      after: data?.after?.disparate_impact_ratio || 0,
      threshold: 0.8,
      lowerIsBetter: false
    }
  ]

  const chartData = metrics.map(m => ({
    name: m.abbr,
    before: m.before,
    after: m.after,
  }))

  const isFair = (val, threshold, lowerIsBetter) => {
    return lowerIsBetter ? val <= threshold : val >= threshold
  }

  const improvementPct = (data.fairness_improvement * 100).toFixed(0)

  return (
    <section className="py-8 border-b border-gray-200 last:border-0 animate-in fade-in slide-in-from-bottom-4 duration-700">
      <div className="mb-6">
        <p className="text-xs font-semibold uppercase tracking-wider text-blue-700">
          Bias Mitigation Analysis
        </p>
        <p className="mt-1 text-sm text-gray-500">
          Comparison between the baseline model and the fairness-optimized model (Reweighing).
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Comparison Table */}
        <div className="lg:col-span-2 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Before Card */}
            <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
              <h3 className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-4">Before Mitigation</h3>
              <div className="space-y-4">
                {metrics.map(m => (
                  <div key={m.abbr} className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">{m.name}</span>
                    <span className={`text-sm font-mono font-bold ${isFair(m.before, m.threshold, m.lowerIsBetter) ? 'text-green-600' : 'text-red-600'}`}>
                      {m.before.toFixed(3)}
                    </span>
                  </div>
                ))}
                <div className="pt-2 border-t border-gray-100 flex justify-between items-center">
                  <span className="text-sm text-gray-900 font-semibold">Model Accuracy</span>
                  <span className="text-sm font-mono font-bold text-gray-900">{(data.before.accuracy * 100).toFixed(1)}%</span>
                </div>
              </div>
            </div>

            {/* After Card */}
            <div className="bg-blue-50 border border-blue-100 rounded-xl p-5 shadow-sm relative overflow-hidden">
              <div className="absolute top-0 right-0 p-2">
                <span className="bg-blue-600 text-white text-[10px] font-bold px-2 py-0.5 rounded-full uppercase">Optimized</span>
              </div>
              <h3 className="text-xs font-bold text-blue-400 uppercase tracking-widest mb-4">After Mitigation</h3>
              <div className="space-y-4">
                {metrics.map(m => (
                  <div key={m.abbr} className="flex justify-between items-center">
                    <span className="text-sm text-blue-800">{m.name}</span>
                    <span className={`text-sm font-mono font-bold ${isFair(m.after, m.threshold, m.lowerIsBetter) ? 'text-green-600' : 'text-red-600'}`}>
                      {m.after.toFixed(3)}
                    </span>
                  </div>
                ))}
                <div className="pt-2 border-t border-blue-100 flex justify-between items-center">
                  <span className="text-sm text-blue-900 font-semibold">Model Accuracy</span>
                  <span className="text-sm font-mono font-bold text-blue-900">{(data.after.accuracy * 100).toFixed(1)}%</span>
                </div>
              </div>
            </div>
          </div>

          {/* Summary Card */}
          <div className="bg-gradient-to-r from-green-50 to-emerald-50 border border-green-100 rounded-xl p-6">
            <h4 className="text-green-900 font-bold text-lg">
              Bias reduced by {improvementPct}%
            </h4>
            <p className="text-green-700 text-sm">
              The model fairness has improved significantly using the {data.algorithm} method. 
              The accuracy cost was only {(data.accuracy_cost * 100).toFixed(1)}%.
            </p>
          </div>
        </div>

        {/* Visual Chart */}
        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm flex flex-col">
          <h3 className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-6 text-center">Metric Comparison</h3>
          <div className="flex-1 min-h-[250px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                <XAxis dataKey="name" axisLine={false} tickLine={false} />
                <YAxis hide domain={[0, 1.2]} />
                <Tooltip 
                  cursor={{fill: '#F3F4F6'}}
                  contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                />
                <Legend iconType="circle" />
                <Bar dataKey="before" fill="#94A3B8" radius={[4, 4, 0, 0]} name="Baseline" />
                <Bar dataKey="after" fill="#2563EB" radius={[4, 4, 0, 0]} name="Mitigated" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-4 text-[10px] text-gray-400 text-center uppercase tracking-tighter">
            Lower DPD/EOD and higher DIR are better
          </p>
        </div>
      </div>
    </section>
  )
}

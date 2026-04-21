/**
 * AuditDashboard
 * ==============
 * Receives structured audit results as props and renders four panels:
 *
 *  1. Group Size Charts  — Recharts BarChart per protected column (demographics)
 *  2. Performance Table  — per-group accuracy / precision / recall, red rows flagged
 *  3. Fairness Metric Cards — DPD & EOD, green = pass / red = fail
 *  4. Proxy Risk List    — features ranked by proxy_risk_score with HIGH RISK badge
 *
 * Props
 * -----
 * demographicsResult  object|null  — POST /audit/demographics response
 * performanceResult   object|null  — POST /audit/performance response
 * fairnessResult      object|null  — POST /audit/fairness response
 * proxyResult         object|null  — POST /audit/proxies response
 *
 * All props are optional; each panel degrades gracefully with a "no data" state.
 */

import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Cell,
} from 'recharts'

/* ── Design tokens (match global design system) ─────────────────────── */
const ACCENT     = '#1D4ED8'
const FAIL_RED   = '#DC2626'
const PASS_GREEN = '#16A34A'
const BAR_BLUE   = '#3B82F6'  // slightly lighter than accent for chart readability

/* ── Accuracy gap threshold to flag a row ───────────────────────────── */
const ACCURACY_GAP_THRESHOLD = 0.10


/* ════════════════════════════════════════════════════════════════════════
   Shared layout primitives
════════════════════════════════════════════════════════════════════════ */

/** Section wrapper with a consistent heading style. */
function Panel({ title, subtitle, children }) {
  return (
    <section className="py-8 border-b border-gray-200 last:border-0">
      <div className="mb-5">
        <p className="text-xs font-semibold uppercase tracking-wider text-blue-700">
          {title}
        </p>
        {subtitle && (
          <p className="mt-1 text-sm text-gray-500">{subtitle}</p>
        )}
      </div>
      {children}
    </section>
  )
}

/** Shown when a panel has no data to display. */
function EmptyState({ message = 'No data — run the relevant audit first.' }) {
  return (
    <p className="text-sm text-gray-400 italic">{message}</p>
  )
}


/* ════════════════════════════════════════════════════════════════════════
   1. Group Size Bar Chart
════════════════════════════════════════════════════════════════════════ */

/** Custom Recharts tooltip — flat, no shadow, no border-radius excess. */
function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-gray-200 rounded px-3 py-2 text-xs shadow-sm">
      <p className="font-semibold text-gray-900">{label}</p>
      <p className="text-gray-600 mt-0.5">
        Count: <span className="font-mono">{payload[0].value.toLocaleString()}</span>
      </p>
    </div>
  )
}

/** One Recharts bar chart for a single protected column. */
function GroupBarChart({ colName, colData }) {
  const data = Object.entries(colData.value_counts ?? {}).map(([name, count]) => ({
    name: String(name),
    count,
  }))

  if (data.length === 0) return <EmptyState message="No groups found in this column." />

  const underRepGroups = new Set(colData.underrepresented_groups ?? [])

  return (
    <div>
      {/* Column label + representation score */}
      <div className="flex items-center gap-3 mb-3">
        <h3 className="text-sm font-semibold text-gray-900 font-mono">{colName}</h3>
        <span className={[
          'text-xs font-medium px-2 py-0.5 rounded',
          colData.has_underrepresentation
            ? 'bg-yellow-50 text-yellow-700'
            : 'bg-green-50 text-green-700',
        ].join(' ')}>
          Balance score: {(colData.representation_score * 100).toFixed(1)}%
        </span>
      </div>

      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data} barSize={32} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
          <XAxis
            dataKey="name"
            tick={{ fontSize: 12, fill: '#6B7280' }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fontSize: 11, fill: '#9CA3AF' }}
            axisLine={false}
            tickLine={false}
            width={45}
            tickFormatter={(v) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v}
          />
          <Tooltip content={<ChartTooltip />} cursor={{ fill: '#F3F4F6' }} />
          <Bar dataKey="count" radius={[3, 3, 0, 0]}>
            {data.map(({ name }) => (
              <Cell
                key={name}
                fill={underRepGroups.has(name) ? '#F59E0B' : BAR_BLUE}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Under-representation callout */}
      {colData.has_underrepresentation && (
        <p className="mt-1 text-xs text-yellow-700">
          ⚠ Under-represented (&lt;10%): {colData.underrepresented_groups.join(', ')}
        </p>
      )}
    </div>
  )
}

function GroupSizeSection({ demographicsResult }) {
  const results = demographicsResult?.results

  return (
    <Panel
      title="Group Distribution"
      subtitle="Bar height = number of rows per group value. Amber bars = under-represented (<10% of column)."
    >
      {!results || Object.keys(results).length === 0 ? (
        <EmptyState />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {Object.entries(results).map(([col, colData]) => (
            <GroupBarChart key={col} colName={col} colData={colData} />
          ))}
        </div>
      )}
    </Panel>
  )
}


/* ════════════════════════════════════════════════════════════════════════
   2. Per-Group Performance Table
════════════════════════════════════════════════════════════════════════ */

/** Metric cell — shows a float as a percentage. */
function MetricCell({ value, flagged }) {
  return (
    <td className={[
      'px-4 py-2.5 text-sm font-mono text-right',
      flagged ? 'text-red-700 font-semibold' : 'text-gray-700',
    ].join(' ')}>
      {value != null ? `${(value * 100).toFixed(1)}%` : '—'}
    </td>
  )
}

/** Table for one protected column. */
function ColumnPerformanceTable({ colName, colData }) {
  const groups = colData.groups ?? {}
  const groupEntries = Object.entries(groups)

  if (groupEntries.length === 0) {
    return <EmptyState message="No group data available." />
  }

  // Find max accuracy across groups to compute 10% gap
  const maxAccuracy = Math.max(...groupEntries.map(([, g]) => g.accuracy ?? 0))
  const gaps = colData.performance_gaps ?? {}
  const accuracyGap = gaps.accuracy

  return (
    <div>
      <div className="flex items-center gap-3 mb-3">
        <h3 className="text-sm font-semibold text-gray-900 font-mono">{colName}</h3>
        {accuracyGap?.flagged && (
          <span className="text-xs bg-red-50 text-red-700 font-medium px-2 py-0.5 rounded">
            Accuracy gap {(accuracyGap.gap * 100).toFixed(1)}pp — flagged
          </span>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm border border-gray-200 rounded-lg overflow-hidden">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200 text-left">
              <th className="px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                Group
              </th>
              <th className="px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide text-right">
                Count
              </th>
              <th className="px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide text-right">
                Accuracy
              </th>
              <th className="px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide text-right">
                Precision
              </th>
              <th className="px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide text-right">
                Recall
              </th>
            </tr>
          </thead>
          <tbody>
            {groupEntries.map(([groupName, metrics]) => {
              const accuracyFlagged = metrics.accuracy != null
                && metrics.accuracy < maxAccuracy - ACCURACY_GAP_THRESHOLD

              return (
                <tr
                  key={groupName}
                  className={[
                    'border-b border-gray-100 last:border-0',
                    accuracyFlagged ? 'bg-red-50' : 'bg-white hover:bg-gray-50',
                  ].join(' ')}
                >
                  {/* Group name */}
                  <td className="px-4 py-2.5 text-sm text-gray-900 font-medium">
                    <span className="font-mono">{groupName}</span>
                    {accuracyFlagged && (
                      <span
                        className="ml-2 inline-block text-[10px] bg-red-100 text-red-700
                                   font-semibold px-1.5 py-0.5 rounded uppercase tracking-wide"
                        title="Accuracy more than 10 percentage points below the best group"
                      >
                        ↓ low accuracy
                      </span>
                    )}
                  </td>

                  {/* Count */}
                  <td className="px-4 py-2.5 text-sm text-right text-gray-500 font-mono">
                    {metrics.count?.toLocaleString() ?? '—'}
                  </td>

                  <MetricCell value={metrics.accuracy}  flagged={accuracyFlagged} />
                  <MetricCell value={metrics.precision} flagged={false} />
                  <MetricCell value={metrics.recall}    flagged={false} />
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {colData.skipped_groups?.length > 0 && (
        <p className="mt-1.5 text-xs text-gray-400">
          Skipped (insufficient samples): {colData.skipped_groups.join(', ')}
        </p>
      )}
    </div>
  )
}

function PerformanceSection({ performanceResult }) {
  const results = performanceResult?.results

  const overall = performanceResult?.overall_metrics
  return (
    <Panel
      title="Per-Group Performance"
      subtitle="Rows highlighted in red have accuracy more than 10 percentage points below the best-performing group."
    >
      {/* Overall baseline */}
      {overall && (
        <div className="mb-5 flex flex-wrap gap-4 text-sm text-gray-600">
          <span>
            Overall accuracy:{' '}
            <strong className="text-gray-900 font-mono">
              {(overall.accuracy * 100).toFixed(1)}%
            </strong>
          </span>
          <span>
            Precision:{' '}
            <strong className="text-gray-900 font-mono">
              {(overall.precision * 100).toFixed(1)}%
            </strong>
          </span>
          <span>
            Recall:{' '}
            <strong className="text-gray-900 font-mono">
              {(overall.recall * 100).toFixed(1)}%
            </strong>
          </span>
        </div>
      )}

      {!results || Object.keys(results).length === 0 ? (
        <EmptyState />
      ) : (
        <div className="flex flex-col gap-8">
          {Object.entries(results).map(([col, colData]) => (
            <ColumnPerformanceTable key={col} colName={col} colData={colData} />
          ))}
        </div>
      )}
    </Panel>
  )
}


/* ════════════════════════════════════════════════════════════════════════
   3. Fairness Metric Cards
════════════════════════════════════════════════════════════════════════ */

const METRIC_META = {
  demographic_parity_difference: {
    label: 'Demographic Parity Difference',
    abbr: 'DPD',
    description:
      'How different are the approval rates between groups? A score near 0 means both groups are offered positive outcomes at similar rates.',
    thresholdNote: 'Fails when > 0.10',
  },
  equal_opportunity_difference: {
    label: 'Equal Opportunity Difference',
    abbr: 'EOD',
    description:
      'Among people who actually deserve approval, are both groups approved equally often? A score near 0 means the model is equally sensitive across groups.',
    thresholdNote: 'Fails when > 0.10',
  },
  disparate_impact_ratio: {
    label: 'Disparate Impact Ratio',
    abbr: 'DIR',
    description:
      'Ratio of the lower group\'s approval rate to the higher group\'s. Below 0.8 violates the 80% rule used in US employment law.',
    thresholdNote: 'Fails when < 0.80',
  },
}

function MetricCard({ metricKey, metricData }) {
  const meta = METRIC_META[metricKey] ?? {
    label: metricKey,
    abbr: metricKey,
    description: '',
    thresholdNote: '',
  }

  const passing = !metricData?.flagged
  const value   = metricData?.value

  return (
    <div className={[
      'border rounded-lg p-5 flex flex-col gap-3',
      passing ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50',
    ].join(' ')}>
      {/* Header row */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">
            {meta.abbr}
          </p>
          <p className="text-sm font-semibold text-gray-900 mt-0.5">{meta.label}</p>
        </div>
        <span className={[
          'flex-shrink-0 text-xs font-semibold px-2.5 py-1 rounded',
          passing
            ? 'bg-green-100 text-green-800'
            : 'bg-red-100 text-red-800',
        ].join(' ')}>
          {passing ? 'PASS' : 'FAIL'}
        </span>
      </div>

      {/* Value */}
      {value != null && (
        <p className={[
          'text-3xl font-bold font-mono',
          passing ? 'text-green-700' : 'text-red-700',
        ].join(' ')}>
          {value.toFixed(3)}
        </p>
      )}

      {/* Plain-English description */}
      <p className="text-xs text-gray-600 leading-relaxed">{meta.description}</p>

      {/* Threshold note */}
      <p className="text-xs text-gray-400">{meta.thresholdNote}</p>
    </div>
  )
}

function FairnessCardsSection({ fairnessResult }) {
  const metrics = fairnessResult?.metrics

  return (
    <Panel
      title="Fairness Metrics"
      subtitle={
        fairnessResult?.warning
          ? `⚠ ${fairnessResult.warning.slice(0, 120)}…`
          : undefined
      }
    >
      {!metrics ? (
        <EmptyState />
      ) : (
        <>
          {/* Overall verdict */}
          <div className="mb-5 flex items-center gap-3">
            <span className={[
              'text-sm font-semibold px-3 py-1 rounded',
              fairnessResult.overall_pass
                ? 'bg-green-100 text-green-800'
                : 'bg-red-100 text-red-800',
            ].join(' ')}>
              {fairnessResult.overall_pass ? '✓ All metrics passing' : '✗ Metrics failing'}
            </span>
            {fairnessResult.failing_metrics?.length > 0 && (
              <span className="text-sm text-gray-500">
                Failing: {fairnessResult.failing_metrics.join(', ')}
              </span>
            )}
          </div>

          {/* Cards grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Object.entries(metrics).map(([key, data]) => (
              <MetricCard key={key} metricKey={key} metricData={data} />
            ))}
          </div>

          {/* Group stats */}
          {fairnessResult.group_stats && (
            <div className="mt-5 grid grid-cols-2 gap-4 max-w-md">
              {Object.entries(fairnessResult.group_stats).map(([grp, stats]) => (
                <div key={grp} className="border border-gray-200 rounded-lg px-4 py-3 bg-white">
                  <p className="text-xs font-semibold text-gray-500 font-mono">{grp}</p>
                  <p className="text-sm text-gray-700 mt-1">
                    Approval: <strong className="font-mono">{(stats.approval_rate * 100).toFixed(1)}%</strong>
                  </p>
                  {stats.tpr != null && (
                    <p className="text-sm text-gray-700">
                      TPR: <strong className="font-mono">{(stats.tpr * 100).toFixed(1)}%</strong>
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </Panel>
  )
}


/* ════════════════════════════════════════════════════════════════════════
   4. Proxy Risk List
════════════════════════════════════════════════════════════════════════ */

/** Score bar — linear fill, no CSS gradient (flat accent color). */
function ScoreBar({ score }) {
  const pct = Math.min(Math.max(score * 100, 0), 100)
  return (
    <div className="flex items-center gap-2 min-w-0">
      <div className="flex-1 bg-gray-100 rounded-full h-1.5 overflow-hidden">
        <div
          className="h-1.5 rounded-full"
          style={{
            width: `${pct}%`,
            backgroundColor: score > 0.3 ? FAIL_RED : BAR_BLUE,
          }}
        />
      </div>
      <span className="text-xs font-mono text-gray-700 flex-shrink-0 w-10 text-right">
        {score.toFixed(2)}
      </span>
    </div>
  )
}

function ProxyRiskSection({ proxyResult }) {
  const features = proxyResult?.features

  return (
    <Panel
      title="Proxy Risk Detection"
      subtitle="Non-protected features that are statistically correlated with protected attributes and may indirectly encode bias."
    >
      {!features || features.length === 0 ? (
        <EmptyState />
      ) : (
        <>
          {/* Summary counts */}
          <p className="text-sm text-gray-600 mb-4">
            <strong className="text-gray-900">{proxyResult.num_high_risk}</strong> of{' '}
            <strong className="text-gray-900">{proxyResult.num_features_analyzed}</strong>{' '}
            features flagged as{' '}
            <span className="text-red-700 font-semibold">HIGH RISK</span>
            {' '}(proxy risk score &gt; {proxyResult.proxy_risk_threshold ?? 0.3}).
          </p>

          {/* Feature list */}
          <div className="flex flex-col divide-y divide-gray-100 border border-gray-200 rounded-lg overflow-hidden">
            {features.map((feat) => (
              <div
                key={feat.feature}
                className={[
                  'flex items-center gap-4 px-4 py-3',
                  feat.flagged ? 'bg-red-50' : 'bg-white',
                ].join(' ')}
              >
                {/* Feature name + badge */}
                <div className="flex items-center gap-2 w-44 flex-shrink-0 min-w-0">
                  <span className="text-sm font-mono text-gray-900 truncate">
                    {feat.feature}
                  </span>
                  {feat.flagged && (
                    <span className="flex-shrink-0 text-[10px] font-semibold uppercase
                                     tracking-wide bg-red-100 text-red-700 px-1.5 py-0.5 rounded">
                      ⚠ HIGH
                    </span>
                  )}
                </div>

                {/* Score bar */}
                <div className="flex-1 min-w-0">
                  <ScoreBar score={feat.proxy_risk_score} />
                </div>

                {/* Protected-column breakdown — first match only to keep it compact */}
                {feat.per_protected_column && (
                  <div className="hidden sm:flex gap-3 text-xs text-gray-400 flex-shrink-0">
                    {Object.entries(feat.per_protected_column)
                      .slice(0, 2)
                      .map(([col, scores]) => (
                        <span key={col}>
                          <span className="font-medium text-gray-600">{col}:</span>{' '}
                          r={scores.pearson_correlation.toFixed(2)}{' '}
                          MI={scores.mutual_information_normalised.toFixed(2)}
                        </span>
                      ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </Panel>
  )
}


/* ════════════════════════════════════════════════════════════════════════
   Root component
════════════════════════════════════════════════════════════════════════ */

/**
 * AuditDashboard
 *
 * Usage example:
 * ```jsx
 * <AuditDashboard
 *   demographicsResult={demoData}
 *   performanceResult={perfData}
 *   fairnessResult={fairData}
 *   proxyResult={proxyData}
 * />
 * ```
 */
export default function AuditDashboard({
  demographicsResult = null,
  performanceResult  = null,
  fairnessResult     = null,
  proxyResult        = null,
}) {
  const hasAnyData = demographicsResult || performanceResult || fairnessResult || proxyResult

  if (!hasAnyData) {
    return (
      <div className="py-12 text-center text-sm text-gray-400">
        No audit data yet. Run an audit from the{' '}
        <a href="/upload" className="text-accent underline">Upload page</a>.
      </div>
    )
  }

  return (
    <div className="font-sans text-gray-900">
      <GroupSizeSection      demographicsResult={demographicsResult} />
      <PerformanceSection    performanceResult={performanceResult}   />
      <FairnessCardsSection  fairnessResult={fairnessResult}         />
      <ProxyRiskSection      proxyResult={proxyResult}               />
    </div>
  )
}

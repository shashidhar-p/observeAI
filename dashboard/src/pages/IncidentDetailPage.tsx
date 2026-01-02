import { useParams, Link } from 'react-router-dom'
import useSWR from 'swr'
import { fetchIncident, fetchReportByIncident, generateLokiExploreLink } from '../api/client'
import type { Alert, RCAReport, Incident } from '../types'

function ConfidenceGauge({ score }: { score: number }) {
  const circumference = 2 * Math.PI * 45
  const strokeDashoffset = circumference - (score / 100) * circumference
  const color = score >= 80 ? '#22c55e' : score >= 50 ? '#eab308' : '#ef4444'

  return (
    <div className="relative w-32 h-32">
      <svg className="w-32 h-32 transform -rotate-90">
        <circle cx="64" cy="64" r="45" stroke="#1f2937" strokeWidth="10" fill="none" />
        <circle
          cx="64" cy="64" r="45"
          stroke={color}
          strokeWidth="10"
          fill="none"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          className="transition-all duration-1000"
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="text-center">
          <span className="text-3xl font-bold text-white">{score}</span>
          <span className="text-lg text-gray-400">%</span>
        </div>
      </div>
    </div>
  )
}

function SeverityBadge({ severity }: { severity: string }) {
  const styles: Record<string, string> = {
    critical: 'bg-red-500/20 text-red-400 border-red-500/30',
    warning: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    info: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  }
  return (
    <span className={`px-3 py-1 rounded-full text-sm font-medium border ${styles[severity] || styles.info}`}>
      {severity.toUpperCase()}
    </span>
  )
}

function StatusBadge({ status, hasRCA }: { status: string; hasRCA: boolean }) {
  if (status === 'analyzing') {
    return (
      <span className="px-3 py-1 rounded-full text-sm font-medium bg-yellow-500/20 text-yellow-400 border border-yellow-500/30 flex items-center space-x-2">
        <div className="w-2 h-2 bg-yellow-500 rounded-full animate-pulse"></div>
        <span>Analyzing</span>
      </span>
    )
  }
  if (status === 'open' && hasRCA) {
    return (
      <span className="px-3 py-1 rounded-full text-sm font-medium bg-blue-500/20 text-blue-400 border border-blue-500/30">
        RCA Complete
      </span>
    )
  }
  if (status === 'resolved') {
    return (
      <span className="px-3 py-1 rounded-full text-sm font-medium bg-green-500/20 text-green-400 border border-green-500/30">
        Resolved
      </span>
    )
  }
  return (
    <span className="px-3 py-1 rounded-full text-sm font-medium bg-red-500/20 text-red-400 border border-red-500/30">
      Open
    </span>
  )
}

function AlertsTable({ alerts, incidentStartTime }: { alerts: Alert[]; incidentStartTime: string }) {
  const sorted = [...alerts].sort(
    (a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime()
  )
  const firstTime = new Date(sorted[0]?.starts_at || incidentStartTime).getTime()

  return (
    <div className="bg-[#161b22] rounded-xl border border-gray-800 overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-800 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white flex items-center space-x-2">
          <svg className="w-5 h-5 text-orange-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          <span>Correlated Alerts</span>
          <span className="ml-2 px-2 py-0.5 bg-orange-500/20 text-orange-400 text-xs font-bold rounded-full">
            {alerts.length}
          </span>
        </h3>
      </div>

      <table className="w-full">
        <thead className="bg-[#1c2128]">
          <tr className="text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
            <th className="px-6 py-3">Timestamp</th>
            <th className="px-6 py-3">Alert</th>
            <th className="px-6 py-3">Severity</th>
            <th className="px-6 py-3">Source</th>
            <th className="px-6 py-3">Offset</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800">
          {sorted.map((alert, idx) => {
            const alertTime = new Date(alert.starts_at).getTime()
            const offsetSeconds = Math.round((alertTime - firstTime) / 1000)
            const isFirst = idx === 0

            return (
              <tr key={alert.id} className="hover:bg-[#1c2128] transition-colors">
                <td className="px-6 py-3 text-sm text-gray-300 whitespace-nowrap">
                  {new Date(alert.starts_at).toLocaleTimeString()}
                </td>
                <td className="px-6 py-3">
                  <div className="flex items-center space-x-2">
                    <span className="text-white font-medium">{alert.alertname}</span>
                    {isFirst && (
                      <span className="px-2 py-0.5 bg-red-500 text-white text-xs font-bold rounded">ROOT</span>
                    )}
                  </div>
                </td>
                <td className="px-6 py-3">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                    alert.severity === 'critical' ? 'bg-red-500/20 text-red-400' :
                    alert.severity === 'warning' ? 'bg-yellow-500/20 text-yellow-400' :
                    'bg-blue-500/20 text-blue-400'
                  }`}>
                    {alert.severity}
                  </span>
                </td>
                <td className="px-6 py-3 text-sm text-gray-400">
                  {alert.labels?.device || alert.labels?.service || '-'}
                </td>
                <td className="px-6 py-3">
                  <span className={`text-sm font-mono ${isFirst ? 'text-red-400 font-bold' : 'text-gray-400'}`}>
                    {isFirst ? 'T+0s' : `T+${offsetSeconds}s`}
                  </span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function TimelineSection({ events }: { events: RCAReport['timeline'] }) {
  if (!events || events.length === 0) return null

  return (
    <div className="bg-[#161b22] rounded-xl border border-gray-800 p-6">
      <h3 className="text-lg font-semibold text-white mb-4 flex items-center space-x-2">
        <svg className="w-5 h-5 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span>Event Timeline</span>
      </h3>
      <div className="space-y-4">
        {events.map((event, idx) => (
          <div key={idx} className="flex items-start space-x-4">
            <div className="flex flex-col items-center">
              <div className={`w-3 h-3 rounded-full ${
                event.source === 'alert' ? 'bg-red-500' :
                event.source === 'log' ? 'bg-purple-500' : 'bg-blue-500'
              }`} />
              {idx < events.length - 1 && <div className="w-0.5 h-full bg-gray-700 mt-1" />}
            </div>
            <div className="flex-1 pb-4">
              <p className="text-white">{event.event}</p>
              <div className="flex items-center space-x-3 mt-1 text-xs text-gray-500">
                <span>{new Date(event.timestamp).toLocaleString()}</span>
                <span className={`px-1.5 py-0.5 rounded ${
                  event.source === 'alert' ? 'bg-red-500/20 text-red-400' :
                  event.source === 'log' ? 'bg-purple-500/20 text-purple-400' : 'bg-blue-500/20 text-blue-400'
                }`}>
                  {event.source}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function EvidenceSection({ report, incident }: { report: RCAReport; incident: Incident }) {
  const logs = report.evidence?.logs || []
  if (logs.length === 0) return null

  const startTime = incident.started_at
  const endTime = incident.resolved_at || new Date().toISOString()

  return (
    <div className="bg-[#161b22] rounded-xl border border-gray-800 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white flex items-center space-x-2">
          <svg className="w-5 h-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <span>Log Evidence</span>
        </h3>
        {logs[0]?.labels && (
          <a
            href={generateLokiExploreLink(logs[0].labels, startTime, endTime)}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center space-x-2 px-3 py-1.5 bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/30 rounded-lg text-blue-400 text-sm transition-colors"
          >
            <span>Open in Grafana</span>
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </a>
        )}
      </div>
      <div className="space-y-2 font-mono text-sm max-h-64 overflow-y-auto">
        {logs.map((log, idx) => (
          <div key={idx} className="bg-[#0d1117] rounded-lg p-3 border border-gray-800">
            <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
              <span>{new Date(log.timestamp).toLocaleTimeString()}</span>
              <span className="text-purple-400">{log.labels?.service}</span>
            </div>
            <p className="text-gray-200 break-all">{log.message}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

function RemediationSection({ steps }: { steps: RCAReport['remediation_steps'] }) {
  if (!steps || steps.length === 0) return null

  const priorityOrder: Record<string, number> = { immediate: 0, short_term: 1, long_term: 2 }
  const sorted = [...steps].sort((a, b) => (priorityOrder[a.priority] || 0) - (priorityOrder[b.priority] || 0))

  return (
    <div className="bg-[#161b22] rounded-xl border border-gray-800 p-6">
      <h3 className="text-lg font-semibold text-white mb-4 flex items-center space-x-2">
        <svg className="w-5 h-5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
        </svg>
        <span>Remediation Steps</span>
      </h3>
      <div className="space-y-3">
        {sorted.map((step, idx) => (
          <div key={idx} className="bg-[#0d1117] rounded-lg p-4 border border-gray-800">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center space-x-2 mb-2">
                  <span className={`px-2 py-0.5 text-xs font-medium rounded ${
                    step.priority === 'immediate' ? 'bg-red-500/20 text-red-400' :
                    step.priority === 'short_term' ? 'bg-yellow-500/20 text-yellow-400' :
                    'bg-gray-500/20 text-gray-400'
                  }`}>
                    {step.priority.replace('_', ' ')}
                  </span>
                  <span className={`px-2 py-0.5 text-xs rounded ${
                    step.risk === 'high' ? 'bg-red-900/50 text-red-300' :
                    step.risk === 'medium' ? 'bg-yellow-900/50 text-yellow-300' :
                    'bg-green-900/50 text-green-300'
                  }`}>
                    {step.risk} risk
                  </span>
                </div>
                <p className="text-white font-medium">{step.action}</p>
                {step.description && (
                  <p className="text-sm text-gray-400 mt-1">{step.description}</p>
                )}
                {step.command && (
                  <code className="block mt-2 text-xs bg-black/50 text-green-400 p-2 rounded font-mono">
                    $ {step.command}
                  </code>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function IncidentDetailPage() {
  const { id } = useParams<{ id: string }>()

  const { data: incident, error: incidentError } = useSWR(
    id ? ['incident', id] : null,
    () => fetchIncident(id!),
    { refreshInterval: 5000 }
  )

  const { data: report } = useSWR(
    id ? ['report', id] : null,
    () => fetchReportByIncident(id!),
    { refreshInterval: 5000 }
  )

  if (incidentError) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6">
        <p className="text-red-400">Failed to load incident</p>
      </div>
    )
  }

  if (!incident) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex flex-col items-center space-y-4">
          <div className="w-12 h-12 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin"></div>
          <span className="text-gray-400">Loading incident...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center space-x-2 text-sm">
        <Link to="/" className="text-gray-400 hover:text-white transition-colors">Incidents</Link>
        <svg className="w-4 h-4 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
        <span className="text-white">{incident.title}</span>
      </div>

      {/* Header Card */}
      <div className="bg-[#161b22] rounded-xl border border-gray-800 p-6">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center space-x-3 mb-3">
              <StatusBadge status={incident.status} hasRCA={!!incident.rca_completed_at} />
              <SeverityBadge severity={incident.severity} />
            </div>
            <h1 className="text-2xl font-bold text-white mb-2">{incident.title}</h1>
            <p className="text-gray-400">{incident.correlation_reason || 'Single alert incident'}</p>

            <div className="flex items-center space-x-6 mt-4 text-sm">
              <div>
                <span className="text-gray-500">Started</span>
                <p className="text-white">{new Date(incident.started_at).toLocaleString()}</p>
              </div>
              {incident.rca_completed_at && (
                <div>
                  <span className="text-gray-500">RCA Completed</span>
                  <p className="text-white">{new Date(incident.rca_completed_at).toLocaleString()}</p>
                </div>
              )}
              {incident.resolved_at && (
                <div>
                  <span className="text-gray-500">Resolved</span>
                  <p className="text-white">{new Date(incident.resolved_at).toLocaleString()}</p>
                </div>
              )}
              <div>
                <span className="text-gray-500">Affected Services</span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {incident.affected_services.map((s: string) => (
                    <span key={s} className="px-2 py-0.5 bg-gray-700/50 text-gray-300 text-xs rounded">{s}</span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* RCA Summary */}
      {report && report.status === 'complete' && (
        <div className="bg-gradient-to-r from-[#161b22] to-[#1c2128] rounded-xl border border-gray-800 p-6">
          <h2 className="text-lg font-semibold text-white mb-6 flex items-center space-x-2">
            <svg className="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            <span>Root Cause Analysis</span>
          </h2>

          <div className="flex items-start space-x-8">
            <div className="flex-shrink-0">
              <ConfidenceGauge score={report.confidence_score} />
              <p className="text-center text-sm text-gray-400 mt-2">Confidence</p>
            </div>

            <div className="flex-1 space-y-4">
              <div>
                <h4 className="text-sm font-medium text-gray-400 mb-1">Root Cause</h4>
                <p className="text-lg text-white">{report.root_cause}</p>
              </div>
              <div>
                <h4 className="text-sm font-medium text-gray-400 mb-1">Summary</h4>
                <p className="text-gray-300">{report.summary}</p>
              </div>

              {report.analysis_metadata && (
                <div className="flex items-center space-x-6 pt-4 border-t border-gray-700 text-sm">
                  <div>
                    <span className="text-gray-500">Model</span>
                    <p className="text-gray-300">{report.analysis_metadata.model}</p>
                  </div>
                  <div>
                    <span className="text-gray-500">Duration</span>
                    <p className="text-gray-300">{report.analysis_metadata.duration_seconds}s</p>
                  </div>
                  <div>
                    <span className="text-gray-500">Tool Calls</span>
                    <p className="text-gray-300">{report.analysis_metadata.tool_calls}</p>
                  </div>
                  <div>
                    <span className="text-gray-500">Tokens</span>
                    <p className="text-gray-300">{report.analysis_metadata.tokens_used?.toLocaleString()}</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Analyzing state */}
      {incident.status === 'analyzing' && (
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-6">
          <div className="flex items-center space-x-4">
            <div className="w-8 h-8 border-4 border-yellow-500/30 border-t-yellow-500 rounded-full animate-spin"></div>
            <div>
              <h3 className="text-lg font-semibold text-yellow-400">RCA Analysis in Progress</h3>
              <p className="text-gray-400 text-sm">The AI is analyzing logs, metrics, and alert patterns...</p>
            </div>
          </div>
        </div>
      )}

      {/* Alerts Table */}
      {incident.alerts && incident.alerts.length > 0 && (
        <AlertsTable alerts={incident.alerts} incidentStartTime={incident.started_at} />
      )}

      {/* Timeline & Evidence Grid */}
      {report && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <TimelineSection events={report.timeline} />
          <EvidenceSection report={report} incident={incident} />
        </div>
      )}

      {/* Remediation */}
      {report && <RemediationSection steps={report.remediation_steps} />}
    </div>
  )
}

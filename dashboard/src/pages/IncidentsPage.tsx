import { useState, useEffect } from 'react'
import useSWR from 'swr'
import { useHistory } from 'react-router-dom'
import { fetchIncidents, fetchIncidentAlerts } from '../api/client'
import type { Incident, Alert } from '../types'

type StatusFilter = 'all' | 'open' | 'analyzing' | 'rca_complete' | 'resolved'
type SeverityFilter = 'all' | 'critical' | 'warning' | 'info'

function StatusIndicator({ status, hasRCA }: { status: string; hasRCA: boolean }) {
  if (status === 'analyzing') {
    return (
      <div className="flex items-center space-x-2">
        <div className="relative">
          <div className="w-3 h-3 bg-yellow-500 rounded-full animate-pulse"></div>
          <div className="absolute inset-0 w-3 h-3 bg-yellow-500 rounded-full animate-ping opacity-75"></div>
        </div>
        <span className="text-yellow-500 text-sm font-medium">Analyzing</span>
      </div>
    )
  }
  if (status === 'open' && hasRCA) {
    return (
      <div className="flex items-center space-x-2">
        <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
        <span className="text-blue-400 text-sm font-medium">RCA Complete</span>
      </div>
    )
  }
  if (status === 'open') {
    return (
      <div className="flex items-center space-x-2">
        <div className="w-3 h-3 bg-red-500 rounded-full"></div>
        <span className="text-red-400 text-sm font-medium">Open</span>
      </div>
    )
  }
  if (status === 'resolved') {
    return (
      <div className="flex items-center space-x-2">
        <div className="w-3 h-3 bg-green-500 rounded-full"></div>
        <span className="text-green-400 text-sm font-medium">Resolved</span>
      </div>
    )
  }
  return (
    <div className="flex items-center space-x-2">
      <div className="w-3 h-3 bg-gray-500 rounded-full"></div>
      <span className="text-gray-400 text-sm font-medium">Closed</span>
    </div>
  )
}

function SeverityBar({ severity }: { severity: string }) {
  const colors: Record<string, string> = {
    critical: 'bg-red-500',
    warning: 'bg-yellow-500',
    info: 'bg-blue-500',
  }
  return <div className={`w-1 h-full ${colors[severity] || 'bg-gray-500'} rounded-full`} />
}

function AlertsModal({ incidentId, onClose, incidentTitle }: { incidentId: string; onClose: () => void; incidentTitle: string }) {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchIncidentAlerts(incidentId)
      .then(setAlerts)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [incidentId])

  const sorted = [...alerts].sort(
    (a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime()
  )
  const firstTime = sorted[0] ? new Date(sorted[0].starts_at).getTime() : 0

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div
        className="bg-[#161b22] rounded-xl border border-gray-700 max-w-4xl w-full max-h-[85vh] overflow-hidden shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="bg-[#1c2128] border-b border-gray-700 px-6 py-4 flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-white">Correlated Alerts</h3>
            <p className="text-sm text-gray-400 mt-0.5">{incidentTitle}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white p-2 hover:bg-gray-700 rounded-lg transition-colors">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="overflow-auto max-h-[calc(85vh-80px)]">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="w-8 h-8 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin"></div>
            </div>
          ) : error ? (
            <div className="text-red-400 text-center py-12">{error}</div>
          ) : (
            <table className="w-full">
              <thead className="bg-[#1c2128] sticky top-0">
                <tr className="text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  <th className="px-6 py-3">Timestamp</th>
                  <th className="px-6 py-3">Alert</th>
                  <th className="px-6 py-3">Severity</th>
                  <th className="px-6 py-3">Source</th>
                  <th className="px-6 py-3">Offset</th>
                  <th className="px-6 py-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {sorted.map((alert, idx) => {
                  const alertTime = new Date(alert.starts_at).getTime()
                  const offsetSeconds = Math.round((alertTime - firstTime) / 1000)
                  const isFirst = idx === 0

                  return (
                    <tr key={alert.id} className="hover:bg-[#1c2128] transition-colors">
                      <td className="px-6 py-4 text-sm text-gray-300 whitespace-nowrap">
                        {new Date(alert.starts_at).toLocaleString()}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center space-x-2">
                          <span className="text-white font-medium">{alert.alertname}</span>
                          {isFirst && (
                            <span className="px-2 py-0.5 bg-red-500/20 text-red-400 text-xs font-bold rounded">ROOT</span>
                          )}
                        </div>
                        <p className="text-xs text-gray-500 mt-1 max-w-md truncate">
                          {alert.annotations?.summary || alert.annotations?.description}
                        </p>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          alert.severity === 'critical' ? 'bg-red-500/20 text-red-400' :
                          alert.severity === 'warning' ? 'bg-yellow-500/20 text-yellow-400' :
                          'bg-blue-500/20 text-blue-400'
                        }`}>
                          {alert.severity}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-400">
                        {alert.labels?.service || alert.labels?.device || '-'}
                      </td>
                      <td className="px-6 py-4">
                        <span className={`text-sm font-mono ${isFirst ? 'text-red-400 font-bold' : 'text-gray-400'}`}>
                          {isFirst ? 'T+0s' : `T+${offsetSeconds}s`}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          alert.status === 'firing' ? 'bg-red-500/20 text-red-400' : 'bg-green-500/20 text-green-400'
                        }`}>
                          {alert.status}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}

interface StatsCardProps {
  label: string
  value: number
  color: string
  active: boolean
  onClick: () => void
}

function StatsCard({ label, value, color, active, onClick }: StatsCardProps) {
  return (
    <button
      onClick={onClick}
      className={`bg-[#161b22] rounded-xl border p-4 text-left transition-all hover:scale-105 ${
        active ? 'border-white ring-2 ring-white/20' : 'border-gray-800 hover:border-gray-600'
      }`}
    >
      <div className="text-2xl font-bold text-white">{value}</div>
      <div className="flex items-center space-x-2 mt-1">
        <div className={`w-2 h-2 rounded-full ${color}`}></div>
        <span className="text-sm text-gray-400">{label}</span>
      </div>
    </button>
  )
}

type RefreshInterval = 0 | 5000 | 10000 | 30000 | 60000

const REFRESH_OPTIONS: { value: RefreshInterval; label: string }[] = [
  { value: 0, label: 'Off' },
  { value: 5000, label: '5s' },
  { value: 10000, label: '10s' },
  { value: 30000, label: '30s' },
  { value: 60000, label: '1m' },
]

export default function IncidentsPage() {
  const history = useHistory()
  const [selectedIncident, setSelectedIncident] = useState<{ id: string; title: string } | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>('all')
  const [refreshInterval, setRefreshInterval] = useState<RefreshInterval>(5000)

  const { data, error, mutate, isValidating } = useSWR('incidents', () => fetchIncidents(50, 0), {
    refreshInterval: refreshInterval,
  })

  const handleRefresh = () => {
    mutate()
  }

  if (!data && !error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex flex-col items-center space-y-4">
          <div className="w-12 h-12 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin"></div>
          <span className="text-gray-400">Loading incidents...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6">
        <div className="flex items-center space-x-3">
          <svg className="w-6 h-6 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-red-400">Failed to load incidents: {error.message}</p>
        </div>
      </div>
    )
  }

  const allIncidents = data?.incidents || []

  // Calculate counts from all incidents (before filtering)
  const openCount = allIncidents.filter((i: Incident) => i.status === 'open' && !i.rca_completed_at).length
  const analyzingCount = allIncidents.filter((i: Incident) => i.status === 'analyzing').length
  const rcaCompleteCount = allIncidents.filter((i: Incident) => i.status === 'open' && i.rca_completed_at).length
  const resolvedCount = allIncidents.filter((i: Incident) => i.status === 'resolved').length

  // Helper to determine incident's display status
  const getIncidentDisplayStatus = (i: Incident): StatusFilter => {
    if (i.status === 'analyzing') return 'analyzing'
    if (i.status === 'resolved') return 'resolved'
    if (i.status === 'open' && i.rca_completed_at) return 'rca_complete'
    return 'open'
  }

  // Apply filters
  let filteredIncidents = allIncidents

  // Status filter
  if (statusFilter !== 'all') {
    filteredIncidents = filteredIncidents.filter((i: Incident) => getIncidentDisplayStatus(i) === statusFilter)
  }

  // Severity filter
  if (severityFilter !== 'all') {
    filteredIncidents = filteredIncidents.filter((i: Incident) => i.severity === severityFilter)
  }

  // Search filter
  if (searchQuery.trim()) {
    const query = searchQuery.toLowerCase()
    filteredIncidents = filteredIncidents.filter((i: Incident) =>
      i.title.toLowerCase().includes(query) ||
      i.correlation_reason?.toLowerCase().includes(query) ||
      i.affected_services.some((s: string) => s.toLowerCase().includes(query))
    )
  }

  const handleStatusCardClick = (status: StatusFilter) => {
    setStatusFilter(statusFilter === status ? 'all' : status)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white">Incidents</h2>
        <p className="text-gray-400 mt-1">Monitor and investigate system incidents</p>
      </div>

      {/* Unified Toolbar: Search, Filters, Refresh */}
      <div className="flex items-center gap-3">
        {/* Search */}
        <div className="flex-1 relative">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="Search incidents..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-8 py-2 bg-[#161b22] border border-gray-700 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>

        {/* Severity Filter */}
        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value as SeverityFilter)}
          className="px-3 py-2 bg-[#161b22] border border-gray-700 rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer"
        >
          <option value="all">All Severities</option>
          <option value="critical">Critical</option>
          <option value="warning">Warning</option>
          <option value="info">Info</option>
        </select>

        {/* Divider */}
        <div className="h-6 w-px bg-gray-700"></div>

        {/* Refresh Button */}
        <button
          onClick={handleRefresh}
          disabled={isValidating}
          title="Refresh now"
          className={`p-2 bg-[#161b22] border border-gray-700 rounded-lg transition-colors ${
            isValidating ? 'opacity-50 cursor-not-allowed' : 'hover:bg-[#1c2128] hover:border-gray-600'
          }`}
        >
          <svg className={`w-4 h-4 text-gray-400 ${isValidating ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>

        {/* Auto-refresh Dropdown */}
        <div className="flex items-center gap-1.5">
          {refreshInterval > 0 && (
            <div className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse"></div>
          )}
          <select
            value={refreshInterval}
            onChange={(e) => setRefreshInterval(Number(e.target.value) as RefreshInterval)}
            title="Auto-refresh interval"
            className="px-2 py-2 bg-[#161b22] border border-gray-700 rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer"
          >
            {REFRESH_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.value === 0 ? 'Auto: Off' : `Auto: ${opt.label}`}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Stats - Clickable */}
      <div className="grid grid-cols-5 gap-4">
        <StatsCard
          label="Total"
          value={allIncidents.length}
          color="bg-gray-500"
          active={statusFilter === 'all'}
          onClick={() => setStatusFilter('all')}
        />
        <StatsCard
          label="Open"
          value={openCount}
          color="bg-red-500"
          active={statusFilter === 'open'}
          onClick={() => handleStatusCardClick('open')}
        />
        <StatsCard
          label="Analyzing"
          value={analyzingCount}
          color="bg-yellow-500"
          active={statusFilter === 'analyzing'}
          onClick={() => handleStatusCardClick('analyzing')}
        />
        <StatsCard
          label="RCA Complete"
          value={rcaCompleteCount}
          color="bg-blue-500"
          active={statusFilter === 'rca_complete'}
          onClick={() => handleStatusCardClick('rca_complete')}
        />
        <StatsCard
          label="Resolved"
          value={resolvedCount}
          color="bg-green-500"
          active={statusFilter === 'resolved'}
          onClick={() => handleStatusCardClick('resolved')}
        />
      </div>

      {/* Active Filters Display */}
      {(statusFilter !== 'all' || severityFilter !== 'all') && (
        <div className="flex items-center space-x-2 text-sm">
          <span className="text-gray-500">Active filters:</span>
          {statusFilter !== 'all' && (
            <span className="px-2 py-1 bg-blue-500/20 text-blue-400 rounded-full flex items-center space-x-1">
              <span>Status: {statusFilter.replace('_', ' ')}</span>
              <button onClick={() => setStatusFilter('all')} className="hover:text-white">
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </span>
          )}
          {severityFilter !== 'all' && (
            <span className="px-2 py-1 bg-orange-500/20 text-orange-400 rounded-full flex items-center space-x-1">
              <span>Severity: {severityFilter}</span>
              <button onClick={() => setSeverityFilter('all')} className="hover:text-white">
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </span>
          )}
          <span className="text-gray-600">({filteredIncidents.length} results)</span>
        </div>
      )}

      {/* Incidents Table */}
      <div className="bg-[#161b22] rounded-xl border border-gray-800 overflow-hidden">
        <table className="w-full">
          <thead className="bg-[#1c2128]">
            <tr className="text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
              <th className="w-1"></th>
              <th className="px-6 py-4">Status</th>
              <th className="px-6 py-4">Incident</th>
              <th className="px-6 py-4">Correlated Alerts</th>
              <th className="px-6 py-4">Affected Services</th>
              <th className="px-6 py-4">Started</th>
              <th className="px-6 py-4">Duration</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {filteredIncidents.map((incident: Incident) => {
              const duration = incident.resolved_at
                ? Math.round((new Date(incident.resolved_at).getTime() - new Date(incident.started_at).getTime()) / 60000)
                : Math.round((Date.now() - new Date(incident.started_at).getTime()) / 60000)

              return (
                <tr
                  key={incident.id}
                  onClick={() => history.push(`/incidents/${incident.id}`)}
                  className="hover:bg-[#1c2128] transition-colors cursor-pointer group"
                >
                  <td className="py-4">
                    <SeverityBar severity={incident.severity} />
                  </td>
                  <td className="px-6 py-4">
                    <StatusIndicator status={incident.status} hasRCA={!!incident.rca_completed_at} />
                  </td>
                  <td className="px-6 py-4">
                    <div className="text-white font-medium group-hover:text-blue-400 transition-colors">
                      {incident.title}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">
                      {incident.correlation_reason || 'Single alert incident'}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    {incident.alert_count > 0 ? (
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          setSelectedIncident({ id: incident.id, title: incident.title })
                        }}
                        className="flex items-center space-x-2 px-3 py-1.5 bg-orange-500/10 hover:bg-orange-500/20 border border-orange-500/30 rounded-lg transition-colors"
                      >
                        <svg className="w-4 h-4 text-orange-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                        <span className="text-orange-400 font-medium">{incident.alert_count}</span>
                      </button>
                    ) : (
                      <span className="text-gray-600">-</span>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-wrap gap-1">
                      {incident.affected_services.slice(0, 2).map((service: string) => (
                        <span
                          key={service}
                          className="px-2 py-0.5 bg-gray-700/50 text-gray-300 text-xs rounded"
                        >
                          {service}
                        </span>
                      ))}
                      {incident.affected_services.length > 2 && (
                        <span className="px-2 py-0.5 bg-gray-700/50 text-gray-400 text-xs rounded">
                          +{incident.affected_services.length - 2}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-400 whitespace-nowrap">
                    {new Date(incident.started_at).toLocaleString()}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-400 whitespace-nowrap">
                    {duration < 60 ? `${duration}m` : `${Math.floor(duration / 60)}h ${duration % 60}m`}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>

        {filteredIncidents.length === 0 && (
          <div className="text-center py-16">
            <svg className="w-16 h-16 mx-auto text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <p className="text-gray-500 mt-4">
              {searchQuery || statusFilter !== 'all' || severityFilter !== 'all'
                ? 'No incidents match your filters'
                : 'No incidents found'}
            </p>
            <p className="text-gray-600 text-sm mt-1">
              {searchQuery || statusFilter !== 'all' || severityFilter !== 'all'
                ? 'Try adjusting your search or filters'
                : 'All systems are operating normally'}
            </p>
          </div>
        )}
      </div>

      {/* Alerts Modal */}
      {selectedIncident && (
        <AlertsModal
          incidentId={selectedIncident.id}
          incidentTitle={selectedIncident.title}
          onClose={() => setSelectedIncident(null)}
        />
      )}
    </div>
  )
}

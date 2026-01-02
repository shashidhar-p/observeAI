import type { Alert, Incident, RCAReport } from '../types';

const API_BASE = '/api/v1';

export async function fetchIncidents(limit = 20, offset = 0): Promise<{ incidents: Incident[]; total: number }> {
  const res = await fetch(`${API_BASE}/incidents?limit=${limit}&offset=${offset}`);
  if (!res.ok) throw new Error('Failed to fetch incidents');
  return res.json();
}

export async function fetchIncident(id: string): Promise<Incident> {
  const res = await fetch(`${API_BASE}/incidents/${id}`);
  if (!res.ok) throw new Error('Failed to fetch incident');
  return res.json();
}

export async function fetchReports(limit = 20, offset = 0): Promise<{ reports: RCAReport[]; total: number }> {
  const res = await fetch(`${API_BASE}/reports?limit=${limit}&offset=${offset}`);
  if (!res.ok) throw new Error('Failed to fetch reports');
  return res.json();
}

export async function fetchReport(id: string): Promise<RCAReport> {
  const res = await fetch(`${API_BASE}/reports/${id}`);
  if (!res.ok) throw new Error('Failed to fetch report');
  return res.json();
}

export async function fetchReportByIncident(incidentId: string): Promise<RCAReport | null> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/report`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error('Failed to fetch report');
  return res.json();
}

export async function fetchIncidentAlerts(incidentId: string): Promise<Alert[]> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/alerts`);
  if (!res.ok) throw new Error('Failed to fetch incident alerts');
  return res.json();
}

// Grafana deep link generators
const GRAFANA_BASE = 'http://localhost:3000';
const LOKI_DATASOURCE = 'loki';

export function generateLokiExploreLink(
  labels: Record<string, string>,
  startTime: string,
  endTime: string
): string {
  const labelSelector = Object.entries(labels)
    .map(([k, v]) => `${k}="${v}"`)
    .join(', ');

  const query = encodeURIComponent(`{${labelSelector}}`);
  const from = new Date(startTime).getTime();
  const to = new Date(endTime).getTime();

  return `${GRAFANA_BASE}/explore?orgId=1&left={"datasource":"${LOKI_DATASOURCE}","queries":[{"expr":"{${labelSelector}}","refId":"A"}],"range":{"from":"${from}","to":"${to}"}}`;
}

export function generateCortexExploreLink(
  query: string,
  startTime: string,
  endTime: string
): string {
  const from = new Date(startTime).getTime();
  const to = new Date(endTime).getTime();

  return `${GRAFANA_BASE}/explore?orgId=1&left={"datasource":"cortex","queries":[{"expr":"${encodeURIComponent(query)}","refId":"A"}],"range":{"from":"${from}","to":"${to}"}}`;
}

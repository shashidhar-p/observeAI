export interface Alert {
  id: string;
  fingerprint: string;
  alertname: string;
  severity: 'critical' | 'warning' | 'info';
  status: string;
  labels: Record<string, string>;
  annotations: Record<string, string>;
  starts_at: string;
  ends_at: string | null;
}

export interface Incident {
  id: string;
  title: string;
  status: 'open' | 'analyzing' | 'resolved';
  severity: 'critical' | 'warning' | 'info';
  affected_services: string[];
  affected_labels: Record<string, string>;
  correlation_reason: string | null;
  started_at: string;
  resolved_at: string | null;
  alerts: Alert[];
}

export interface TimelineEvent {
  timestamp: string;
  event: string;
  source: 'log' | 'alert' | 'metric';
  details: string | null;
}

export interface LogEvidence {
  timestamp: string;
  message: string;
  source: string;
  labels: Record<string, string>;
}

export interface RemediationStep {
  priority: 'immediate' | 'short_term' | 'long_term';
  action: string;
  command: string | null;
  description: string;
  risk: 'low' | 'medium' | 'high';
}

export interface RCAReport {
  id: string;
  incident_id: string;
  root_cause: string;
  confidence_score: number;
  summary: string;
  status: 'pending' | 'analyzing' | 'complete' | 'failed';
  timeline: TimelineEvent[];
  evidence: {
    logs: LogEvidence[];
    metrics: unknown[];
  };
  remediation_steps: RemediationStep[];
  analysis_metadata: {
    model: string;
    tokens_used: number;
    duration_seconds: number;
    tool_calls: number;
  };
  started_at: string;
  completed_at: string | null;
}

export interface IncidentWithReport extends Incident {
  report?: RCAReport;
}

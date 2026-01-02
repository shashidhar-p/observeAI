export interface Alert {
  id: string;
  fingerprint: string;
  alertname: string;
  severity: 'critical' | 'warning' | 'info';
  status: 'firing' | 'resolved';
  labels: Record<string, string>;
  annotations?: Record<string, string>;
  starts_at: string;
  ends_at?: string;
  generator_url?: string;
  incident_id?: string;
  received_at: string;
  created_at: string;
}

export interface Incident {
  id: string;
  title: string;
  status: 'open' | 'analyzing' | 'resolved' | 'closed';
  severity: 'critical' | 'warning' | 'info';
  correlation_reason?: string;
  affected_services: string[];
  primary_alert_id?: string;
  affected_labels?: Record<string, string>;
  started_at: string;
  resolved_at?: string;
  rca_completed_at?: string;
  created_at: string;
  updated_at: string;
  alert_count: number;
  alerts?: Alert[];  // Only populated when fetching single incident
}

export interface TimelineEvent {
  timestamp: string;
  event: string;
  source: 'alert' | 'log' | 'metric';
  details?: Record<string, unknown>;
}

export interface LogEvidence {
  timestamp: string;
  message: string;
  source: string;
  labels: Record<string, string>;
}

export interface MetricEvidence {
  name: string;
  value: number;
  timestamp: string;
  labels: Record<string, string>;
}

export interface Evidence {
  logs: LogEvidence[];
  metrics: MetricEvidence[];
}

export interface RemediationStep {
  priority: 'immediate' | 'short_term' | 'long_term';
  action: string;
  command?: string;
  description?: string;
  risk: 'low' | 'medium' | 'high';
}

export interface AnalysisMetadata {
  model: string;
  tokens_used: number;
  duration_seconds: number;
  tool_calls: number;
}

export interface RCAReport {
  id: string;
  incident_id: string;
  root_cause: string;
  confidence_score: number;
  summary: string;
  status: 'pending' | 'complete' | 'failed';
  timeline: TimelineEvent[];
  evidence: Evidence;
  remediation_steps: RemediationStep[];
  error_message?: string;
  analysis_metadata?: AnalysisMetadata;
  started_at: string;
  completed_at?: string;
  created_at: string;
  updated_at: string;
}

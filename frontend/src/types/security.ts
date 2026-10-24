// ── Enums ──────────────────────────────────────────────────────────────────

export type PropertyType = "home" | "commercial" | "industrial" | "other";

export type SecuritySubscriptionStatus =
  | "active"
  | "suspended"
  | "cancelled"
  | "pending_install";

export type PinType = "normal" | "duress" | "temporary";

export interface TemporaryPin {
  id: number;
  label?: string;
  expires_at: string;
  created_at: string;
}

export type SecurityFeatureName =
  | "entry_secure"
  | "panic_button"
  | "duress_pin"
  | "safe_word"
  | "vacation_mode"
  | "member_access"
  | "camera_access"
  | "elderly_care"
  | "schedule_alerts"
  | "alert_confirmation"
  | "equipment_status"
  | "monitoring_certificate"
  | "tech_survey"
  | "event_history"
  | "monthly_report"
  | "weekly_report"
  | "digital_contract";

export type SecurityAlertType =
  | "PANIC"
  | "ENTRY_TIMEOUT"
  | "DURESS"
  | "INTRUSION"
  | "CHECKIN_MISSED"
  | "INACTIVITY"
  | "SYSTEM_FAULT"
  | "CONNECTION_LOST"
  | "SCHEDULE_VIOLATION";

export type SecurityAlertStatus = "new" | "acknowledged" | "resolved" | "false_alarm";

export type SecurityEventType =
  | "armed"
  | "disarmed"
  | "intrusion"
  | "battery_low"
  | "power_failure"
  | "communication_lost"
  | "tamper"
  | "zone_open"
  | "test"
  | "panic"
  | "duress"
  | "other";

export type EntrySessionStatus = "active" | "cancelled" | "expired";

export type PropertyMemberRole = "owner" | "family" | "employee" | "trusted";

export type SecurityDeviceType =
  | "panel"
  | "sensor_motion"
  | "sensor_magnetic"
  | "sensor_smoke"
  | "sensor_glass"
  | "siren"
  | "keypad"
  | "camera"
  | "communicator"
  | "other";

// ── Models ─────────────────────────────────────────────────────────────────

export interface Property {
  id: number;
  name: string;
  address: string;
  property_type: PropertyType;
  owner_user_id: number;
  internet_client_id?: number;
  notes?: string;
}

export interface SecurityFeature {
  id: number;
  feature_name: SecurityFeatureName;
  enabled: boolean;
}

export interface SecurityPlan {
  id: number;
  name: string;
  description?: string;
  price: number;
  default_features: SecurityFeatureName[];
  is_active: boolean;
  includes_monitoring: boolean;
}

export interface SecuritySubscription {
  id: number;
  property_id: number;
  plan_id: number;
  status: SecuritySubscriptionStatus;
  beat_account_id?: string;
  client_telegram_id?: string;
  portal_token?: string;
  contract_start?: string;
  contract_end?: string;
  billing_day: number;
  notes?: string;
  features: SecurityFeature[];
}

export interface SecurityAlert {
  id: number;
  subscription_id: number;
  alert_type: SecurityAlertType;
  status: SecurityAlertStatus;
  triggered_at: string;
  acknowledged_at?: string;
  resolved_at?: string;
  idempotency_key?: string;
  operator_notes?: string;
  confirmation_sent_at?: string;
  confirmation_expires_at?: string;
}

export interface SecurityEvent {
  id: number;
  subscription_id: number;
  event_type: SecurityEventType;
  occurred_at: string;
  received_at: string;
  zone_number?: number;
  partition?: number;
  user_code?: string;
  description?: string;
  source: "beat" | "mock" | "manual";
  processed: boolean;
  idempotency_key?: string;
}

export interface EntrySession {
  id: number;
  subscription_id: number;
  activated_by_user_id?: number;
  duration_minutes: number;
  status: EntrySessionStatus;
  created_at: string;
  expires_at: string;
  cancelled_at?: string;
  cancel_reason?: string;
}

export interface PropertyMember {
  id: number;
  property_id: number;
  name: string;
  phone?: string;
  email?: string;
  role: PropertyMemberRole;
  can_arm: boolean;
  can_disarm: boolean;
  can_invite: boolean;
  can_view_cameras: boolean;
  notify_on_alarm: boolean;
  notify_on_entry: boolean;
  status: string;
}

export interface ContractTemplate {
  id: number;
  version: string;
  title: string;
  body: string;
  body_hash: string;
  is_active: boolean;
  created_at: string;
}

export interface ContractAcceptance {
  id: number;
  subscription_id: number;
  version: string;
  accepted_at: string;
  signer_name?: string;
  signer_dni?: string;
  acceptance_ip?: string;
  document_hash?: string;
  method?: string;
  has_pdf: boolean;
}

export interface ScheduleDay {
  weekday: number;      // 0 = lunes … 6 = domingo
  open_time: string;    // HH:MM:SS
  close_time: string;   // HH:MM:SS
  tolerance_minutes: number;
  enabled: boolean;
}

export interface DeviceZone {
  id?: number;
  zone_number: number;
  zone_name?: string;
  zone_type?: string;
  enabled: boolean;
}

export interface SecurityDevice {
  id: number;
  subscription_id: number;
  device_type: SecurityDeviceType;
  brand?: string;
  model?: string;
  serial_number?: string;
  firmware_version?: string;
  install_date?: string;  // YYYY-MM-DD
  warranty_months?: number;
  location_description?: string;
  notes?: string;
  is_active: boolean;
  zones: DeviceZone[];
}

export interface ElderlyConfig {
  id: number;
  subscription_id: number;
  check_from: string;   // "HH:MM"
  check_until: string;  // "HH:MM"
  notify_telegram_id?: string;
  enabled: boolean;
}

export interface SecurityCertificate {
  id: number;
  issued_at: string;
  valid_until: string;
  verification_token: string;
  download_url: string;
}

export interface MonthlyReport {
  id: number;
  subscription_id: number;
  period: string;  // YYYY-MM
  status: "generating" | "ready" | "failed";
  generated_at?: string;
  event_count: number;
  alert_count: number;
  test_count: number;
}

export interface NeighborhoodGroup {
  id: number;
  name: string;
  telegram_group_id: string;
  description?: string;
  member_count: number;
}

export interface NeighborhoodMembership {
  id: number;
  group_id: number;
  subscription_id: number;
}

export interface SecurityDashboardData {
  stats: {
    active_subscriptions: number;
    suspended_subscriptions: number;
    pending_subscriptions: number;
    open_alerts: number;
    new_alerts: number;
    acknowledged_alerts: number;
    active_entry_sessions: number;
    vacation_active: number;
    alerts_today: number;
    alerts_this_week: number;
  };
  open_alerts: {
    id: number;
    alert_type: string;
    status: string;
    triggered_at: string;
    subscription_id: number;
    property_name: string;
    property_address: string;
  }[];
  active_entry_sessions: {
    id: number;
    subscription_id: number;
    expires_at: string;
    duration_minutes: number;
    property_name: string;
  }[];
  recent_events: {
    id: number;
    event_type: string;
    occurred_at: string;
    zone_number?: number;
    zone_name?: string;
    subscription_id: number;
    property_name: string;
  }[];
  alerts_by_day: { date: string; count: number }[];
  alerts_by_type: { type: string; count: number }[];
}

export interface VacationMode {
  id: number;
  subscription_id: number;
  start_date: string;  // YYYY-MM-DD
  end_date: string;    // YYYY-MM-DD
  notes?: string;
  active: boolean;
}

export interface AlertPanelItem {
  id: number;
  alert_type: SecurityAlertType;
  status: SecurityAlertStatus;
  triggered_at: string;
  acknowledged_at?: string;
  operator_notes?: string;
  confirmation_sent_at?: string;
  confirmation_expires_at?: string;
  subscription_id: number;
  beat_account_id?: string;
  property_name: string;
  property_address: string;
  plan_name: string;
  zone_number?: number;
  zone_name?: string;
}

export interface BeatAccountStatus {
  account_id: string;
  armed?: boolean;
  last_event_at?: string;
  signal_ok?: boolean;
  battery_ok?: boolean;
  power_ok?: boolean;
  available: boolean;
  error_message?: string;
  is_simulated: boolean;
}

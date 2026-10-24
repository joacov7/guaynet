/**
 * Guaynet Seguridad API stubs — Stage 2 implementation pending.
 * All functions are declared with correct signatures so TypeScript consumers compile.
 * Actual HTTP calls will be wired in Stage 2.
 */
import api from "../api";
import type {
  Property,
  SecuritySubscription,
  SecurityAlert,
  SecurityEvent,
  EntrySession,
  BeatAccountStatus,
  SecurityFeatureName,
  SecurityCertificate,
  ElderlyConfig,
  TemporaryPin,
} from "../../types/security";

// ── Properties ─────────────────────────────────────────────────────────────

export const propertiesApi = {
  list: (): Promise<Property[]> =>
    api.get("/security/properties").then((r) => r.data),

  get: (id: number): Promise<Property> =>
    api.get(`/security/properties/${id}`).then((r) => r.data),

  create: (data: Omit<Property, "id">): Promise<Property> =>
    api.post("/security/properties", data).then((r) => r.data),

  update: (id: number, data: Partial<Property>): Promise<Property> =>
    api.patch(`/security/properties/${id}`, data).then((r) => r.data),
};

// ── Subscriptions ──────────────────────────────────────────────────────────

export const subscriptionsApi = {
  list: (): Promise<SecuritySubscription[]> =>
    api.get("/security/subscriptions").then((r) => r.data),

  get: (id: number): Promise<SecuritySubscription> =>
    api.get(`/security/subscriptions/${id}`).then((r) => r.data),

  create: (data: {
    property_id: number;
    plan_id: number;
    beat_account_id?: string;
    contract_number?: string;
  }): Promise<SecuritySubscription> =>
    api.post("/security/subscriptions", data).then((r) => r.data),

  update: (
    id: number,
    data: Partial<SecuritySubscription>
  ): Promise<SecuritySubscription> =>
    api.patch(`/security/subscriptions/${id}`, data).then((r) => r.data),

  toggleFeature: (
    id: number,
    feature_name: SecurityFeatureName,
    enabled: boolean
  ): Promise<void> =>
    api
      .post(`/security/subscriptions/${id}/features`, { feature_name, enabled })
      .then(() => undefined),

  beatStatus: (id: number): Promise<BeatAccountStatus> =>
    api.get(`/security/subscriptions/${id}/beat-status`).then((r) => r.data),

  regeneratePortalToken: (id: number): Promise<{ portal_token: string; portal_url: string }> =>
    api.post(`/security/subscriptions/${id}/regenerate-portal-token`).then((r) => r.data),
};

// ── Alerts ─────────────────────────────────────────────────────────────────

export const alertsApi = {
  listPanel: (): Promise<import("../../types/security").AlertPanelItem[]> =>
    api.get("/security/alerts/panel").then((r) => r.data),

  list: (): Promise<SecurityAlert[]> =>
    api.get("/security/alerts").then((r) => r.data),

  get: (id: number): Promise<SecurityAlert> =>
    api.get(`/security/alerts/${id}`).then((r) => r.data),

  update: (
    id: number,
    data: { status: SecurityAlert["status"]; operator_notes?: string }
  ): Promise<SecurityAlert> =>
    api.patch(`/security/alerts/${id}`, data).then((r) => r.data),
};

// ── Entry Sessions ─────────────────────────────────────────────────────────

export const entrySessionsApi = {
  start: (data: {
    subscription_id: number;
    member_id?: number;
    duration_minutes?: number;
    notes?: string;
  }): Promise<EntrySession> =>
    api.post("/security/entry-sessions", data).then((r) => r.data),

  listActive: (): Promise<EntrySession[]> =>
    api.get("/security/entry-sessions/active").then((r) => r.data),

  cancel: (id: number, pin: string): Promise<EntrySession> =>
    api.post(`/security/entry-sessions/${id}/cancel`, { pin }).then((r) => r.data),
};

// ── Elderly care ──────────────────────────────────────────────────────────

export const elderlyApi = {
  get: (subscription_id: number): Promise<ElderlyConfig> =>
    api.get(`/security/subscriptions/${subscription_id}/elderly-config`).then((r) => r.data),

  upsert: (
    subscription_id: number,
    data: Omit<ElderlyConfig, "id" | "subscription_id">
  ): Promise<ElderlyConfig> =>
    api
      .put(`/security/subscriptions/${subscription_id}/elderly-config`, data)
      .then((r) => r.data),

  delete: (subscription_id: number): Promise<void> =>
    api
      .delete(`/security/subscriptions/${subscription_id}/elderly-config`)
      .then(() => undefined),
};

// ── Certificates ──────────────────────────────────────────────────────────

export const certificatesApi = {
  generate: (subscription_id: number): Promise<SecurityCertificate> =>
    api.post(`/security/subscriptions/${subscription_id}/certificate`).then((r) => r.data),

  download: (subscription_id: number): Promise<Blob> =>
    api
      .get(`/security/subscriptions/${subscription_id}/certificate/download`, {
        responseType: "blob",
      })
      .then((r) => r.data),
};

// ── PINs ───────────────────────────────────────────────────────────────────

export const pinsApi = {
  setPin: (data: {
    subscription_id: number;
    pin_type: "normal" | "duress" | "temporary";
    new_pin: string;
    current_pin?: string;
    expires_at?: string; // ISO string, required for temporary
    label?: string;
  }): Promise<void> =>
    api.post("/security/pins/set", data).then(() => undefined),

  listTemporary: (subscription_id: number): Promise<TemporaryPin[]> =>
    api.get(`/security/pins/temporary/${subscription_id}`).then((r) => r.data),

  deleteTemporary: (pin_id: number, subscription_id: number): Promise<void> =>
    api
      .delete(`/security/pins/temporary/${pin_id}`, { params: { subscription_id } })
      .then(() => undefined),
};

// ── Monthly Reports ────────────────────────────────────────────────────────

export const monthlyReportsApi = {
  list: (subscription_id: number): Promise<import("../../types/security").MonthlyReport[]> =>
    api.get(`/security/subscriptions/${subscription_id}/monthly-reports`).then((r) => r.data),

  downloadUrl: (subscription_id: number, period: string): string =>
    `/api/v1/security/subscriptions/${subscription_id}/monthly-reports/${period}/download`,
};

// ── Members ────────────────────────────────────────────────────────────────

export const membersApi = {
  list: (property_id: number, include_revoked = false): Promise<import("../../types/security").PropertyMember[]> =>
    api.get("/security/members/", { params: { property_id, include_revoked } }).then((r) => r.data),

  create: (data: {
    property_id: number;
    name: string;
    phone?: string;
    email?: string;
    role: import("../../types/security").PropertyMemberRole;
    can_arm: boolean;
    can_disarm: boolean;
    can_invite: boolean;
    can_view_cameras: boolean;
    notify_on_alarm: boolean;
    notify_on_entry: boolean;
  }): Promise<import("../../types/security").PropertyMember> =>
    api.post("/security/members/", data).then((r) => r.data),

  update: (id: number, data: Partial<import("../../types/security").PropertyMember>): Promise<import("../../types/security").PropertyMember> =>
    api.patch(`/security/members/${id}`, data).then((r) => r.data),

  revoke: (id: number): Promise<import("../../types/security").PropertyMember> =>
    api.delete(`/security/members/${id}`).then((r) => r.data),
};

// ── Neighborhood Groups ────────────────────────────────────────────────────

export const neighborhoodApi = {
  list: (): Promise<import("../../types/security").NeighborhoodGroup[]> =>
    api.get("/security/neighborhood-groups").then((r) => r.data),

  create: (data: { name: string; telegram_group_id: string; description?: string }): Promise<import("../../types/security").NeighborhoodGroup> =>
    api.post("/security/neighborhood-groups", data).then((r) => r.data),

  update: (id: number, data: { name: string; telegram_group_id: string; description?: string }): Promise<import("../../types/security").NeighborhoodGroup> =>
    api.patch(`/security/neighborhood-groups/${id}`, data).then((r) => r.data),

  delete: (id: number): Promise<void> =>
    api.delete(`/security/neighborhood-groups/${id}`).then(() => undefined),

  listMembers: (groupId: number): Promise<import("../../types/security").NeighborhoodMembership[]> =>
    api.get(`/security/neighborhood-groups/${groupId}/members`).then((r) => r.data),

  addMember: (groupId: number, subscription_id: number): Promise<import("../../types/security").NeighborhoodMembership> =>
    api.post(`/security/neighborhood-groups/${groupId}/members`, { subscription_id }).then((r) => r.data),

  removeMember: (groupId: number, subscriptionId: number): Promise<void> =>
    api.delete(`/security/neighborhood-groups/${groupId}/members/${subscriptionId}`).then(() => undefined),
};

// ── Vacation mode ─────────────────────────────────────────────────────────

export const vacationApi = {
  list: (subscription_id: number): Promise<import("../../types/security").VacationMode[]> =>
    api.get("/security/vacation/", { params: { subscription_id } }).then((r) => r.data),

  create: (data: {
    subscription_id: number;
    start_date: string;
    end_date: string;
    notes?: string;
  }): Promise<import("../../types/security").VacationMode> =>
    api.post("/security/vacation/", data).then((r) => r.data),

  cancel: (vacation_id: number): Promise<import("../../types/security").VacationMode> =>
    api.post(`/security/vacation/${vacation_id}/cancel`).then((r) => r.data),
};

// ── Events ─────────────────────────────────────────────────────────────────

export const eventsApi = {
  list: (params: {
    subscription_id: number;
    limit?: number;
    event_type?: string;
    from_date?: string;
    to_date?: string;
  }): Promise<SecurityEvent[]> =>
    api.get("/security/events", { params }).then((r) => r.data),
};

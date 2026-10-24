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
};

// ── Alerts ─────────────────────────────────────────────────────────────────

export const alertsApi = {
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

// ── Events ─────────────────────────────────────────────────────────────────

export const eventsApi = {
  list: (subscription_id: number, limit = 50): Promise<SecurityEvent[]> =>
    api
      .get("/security/events", { params: { subscription_id, limit } })
      .then((r) => r.data),
};

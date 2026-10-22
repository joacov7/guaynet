import axios from "axios";
import type {
  AuditLogEntry,
  BandwidthEntry,
  BandwidthHistoryEntry,
  Client,
  DashboardStats,
  DHCPScanResponse,
  DiscoveredUbiquitiDevice,
  FirewallRule,
  FrequencyRecommendation,
  Invoice,
  IpPoolResponse,
  MangleRule,
  MikrotikQueue,
  OnlineClient,
  OverdueReport,
  PCQQueue,
  Plan,
  Router,
  RouterStats,
  RouterUtilization,
  TemplateResult,
  UbiquitiDevice,
  UbiquitiDeviceInfo,
  UbiquitiLinkInfo,
  UbiquitiStation,
  UbiquitiSurveyScan,
  UbiquitiWirelessConfig,
  User,
  VpnConnection,
  Zone,
  WanInterface,
  WanSchedule,
} from "@/types";

const http = axios.create({
  baseURL: "/api/v1",
  headers: { "Content-Type": "application/json" },
});

// Attach token to every request
http.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Redirect to login on 401 (tech users go to /tech/login)
http.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("access_token");
      const isTech = window.location.pathname.startsWith("/tech");
      window.location.href = isTech ? "/tech/login" : "/login";
    }
    return Promise.reject(err);
  }
);

// ── Auth ──────────────────────────────────────────────────────────────────────
export const authApi = {
  login: async (username: string, password: string) => {
    const form = new URLSearchParams({ username, password });
    const res = await http.post<{ access_token: string }>("/auth/login", form, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
    return res.data;
  },
  me: () => http.get<User>("/auth/me").then((r) => r.data),
};

// ── Users (admin) ─────────────────────────────────────────────────────────────
export const usersApi = {
  list: () => http.get<User[]>("/admin/users").then((r) => r.data),
  create: (data: { username: string; email: string; full_name: string; password: string; role: string }) =>
    http.post<User>("/admin/users", data).then((r) => r.data),
  update: (id: number, data: { email?: string; full_name?: string; role?: string; password?: string; is_active?: boolean }) =>
    http.put<User>(`/admin/users/${id}`, data).then((r) => r.data),
};

// ── VPN ───────────────────────────────────────────────────────────────────────
export const vpnApi = {
  list: () => http.get<VpnConnection[]>("/vpn/").then((r) => r.data),
  create: (data: Partial<VpnConnection>) => http.post<VpnConnection>("/vpn/", data).then((r) => r.data),
  update: (id: number, data: Partial<VpnConnection>) => http.put<VpnConnection>(`/vpn/${id}`, data).then((r) => r.data),
  delete: (id: number) => http.delete(`/vpn/${id}`),
  commands: (id: number) => http.get<{ mikrotik: string; server: string }>(`/vpn/${id}/commands`).then((r) => r.data),
  generateWgKeys: () => http.get<{ private_key: string; public_key: string }>("/vpn/generate-wg-keys").then((r) => r.data),
  generateL2tpCreds: () => http.get<{ password: string; ipsec_secret: string }>("/vpn/generate-l2tp-creds").then((r) => r.data),
};

// ── Dashboard ─────────────────────────────────────────────────────────────────
export const dashboardApi = {
  stats: () => http.get<DashboardStats>("/dashboard/stats").then((r) => r.data),
};

// ── Zones ─────────────────────────────────────────────────────────────────────
export const zonesApi = {
  list: () => http.get<Zone[]>("/zones/").then((r) => r.data),
  create: (data: Partial<Zone>) => http.post<Zone>("/zones/", data).then((r) => r.data),
  update: (id: number, data: Partial<Zone>) => http.put<Zone>(`/zones/${id}`, data).then((r) => r.data),
  delete: (id: number) => http.delete(`/zones/${id}`),
};

// ── Plans ─────────────────────────────────────────────────────────────────────
export const plansApi = {
  list: (activeOnly = false) =>
    http.get<Plan[]>("/plans/", { params: { active_only: activeOnly } }).then((r) => r.data),
  get: (id: number) => http.get<Plan>(`/plans/${id}`).then((r) => r.data),
  create: (data: Partial<Plan>) => http.post<Plan>("/plans/", data).then((r) => r.data),
  update: (id: number, data: Partial<Plan>) =>
    http.put<Plan>(`/plans/${id}`, data).then((r) => r.data),
  delete: (id: number) => http.delete(`/plans/${id}`),
  syncAll: (id: number) =>
    http
      .post<{ synced: number; errors: unknown[]; plan: string }>(`/plans/${id}/sync-all`)
      .then((r) => r.data),
};

// ── Routers ───────────────────────────────────────────────────────────────────
export const routersApi = {
  list: () => http.get<Router[]>("/routers/").then((r) => r.data),
  get: (id: number) => http.get<Router>(`/routers/${id}`).then((r) => r.data),
  create: (data: Partial<Router> & { password: string }) =>
    http.post<Router>("/routers/", data).then((r) => r.data),
  update: (id: number, data: Partial<Router> & { password?: string }) =>
    http.put<Router>(`/routers/${id}`, data).then((r) => r.data),
  delete: (id: number) => http.delete(`/routers/${id}`),
  test: (id: number) => http.post<RouterStats>(`/routers/${id}/test`).then((r) => r.data),
  queues: (id: number) =>
    http.get<MikrotikQueue[]>(`/routers/${id}/queues`).then((r) => r.data),
  syncClients: (id: number) =>
    http
      .post<{ synced: number; errors: unknown[] }>(`/routers/${id}/sync-clients`)
      .then((r) => r.data),
  bandwidth: (id: number) =>
    http.get<BandwidthEntry[]>(`/routers/${id}/bandwidth`).then((r) => r.data),
  onlineClients: (id: number) =>
    http.get<OnlineClient[]>(`/routers/${id}/online-clients`).then((r) => r.data),
  updateClientIp: (routerId: number, clientId: number, newIp: string) =>
    http.post(`/routers/${routerId}/clients/${clientId}/update-ip`, { new_ip: newIp }).then((r) => r.data),
  setupQos: (id: number) =>
    http.post<{ pcq_added: number; mangle_rules_added: number }>(`/routers/${id}/setup-qos`).then((r) => r.data),
  utilization: (id: number) =>
    http.get<RouterUtilization>(`/routers/${id}/utilization`).then((r) => r.data),
  syncPppoe: (id: number) =>
    http.post<{ synced: number; errors: string[] }>(`/routers/${id}/sync-pppoe`).then((r) => r.data),
};

// ── Clients ───────────────────────────────────────────────────────────────────
export const clientsApi = {
  list: (params?: {
    status?: string;
    router_id?: number;
    plan_id?: number;
    search?: string;
    skip?: number;
    limit?: number;
  }) => http.get<Client[]>("/clients/", { params }).then((r) => r.data),
  get: (id: number) => http.get<Client>(`/clients/${id}`).then((r) => r.data),
  create: (data: Partial<Client>) => http.post<Client>("/clients/", data).then((r) => r.data),
  update: (id: number, data: Partial<Client>) =>
    http.put<Client>(`/clients/${id}`, data).then((r) => r.data),
  delete: (id: number) => http.delete(`/clients/${id}`),
  suspend: (id: number) => http.post<Client>(`/clients/${id}/suspend`).then((r) => r.data),
  activate: (id: number) => http.post<Client>(`/clients/${id}/activate`).then((r) => r.data),
  cancel: (id: number) => http.post<Client>(`/clients/${id}/cancel`).then((r) => r.data),
  syncMikrotik: (id: number) =>
    http.post(`/clients/${id}/sync-mikrotik`).then((r) => r.data),
  syncPppoe: (id: number) =>
    http.post<{ status: string }>(`/clients/${id}/sync-pppoe`).then((r) => r.data),
  invoices: (id: number) =>
    http.get<Invoice[]>(`/clients/${id}/invoices`).then((r) => r.data),
};

// ── Invoices ──────────────────────────────────────────────────────────────────
export interface InvoiceItemCreate {
  description: string;
  quantity: number;
  unit_price: number;
}

export interface InvoicePreviewItem {
  client_id: number;
  client_name: string;
  plan_name: string;
  amount: number;
  due_date: string;
  issue_date: string;
}

export interface InvoicePreviewResult {
  period: string;
  count: number;
  skipped: number;
  items: InvoicePreviewItem[];
}

export const invoicesApi = {
  list: (params?: { status?: string; period?: string; client_id?: number }) =>
    http.get<Invoice[]>("/invoices/", { params }).then((r) => r.data),
  get: (id: number) => http.get<Invoice>(`/invoices/${id}`).then((r) => r.data),
  create: (data: { client_id: number; period: string; amount?: number; issue_date: string; due_date: string; notes?: string; items?: InvoiceItemCreate[] }) =>
    http.post<Invoice>("/invoices/", data).then((r) => r.data),
  createCharge: (data: { client_id: number; notes?: string; items: InvoiceItemCreate[] }) => {
    const today = new Date().toISOString().slice(0, 10);
    const period = today.slice(0, 7);
    return http.post<Invoice>("/invoices/", {
      ...data,
      period,
      issue_date: today,
      due_date: today,
    }).then((r) => r.data);
  },
  update: (id: number, data: Partial<Invoice>) =>
    http.put<Invoice>(`/invoices/${id}`, data).then((r) => r.data),
  addPayment: (invoiceId: number, data: object) =>
    http.post(`/invoices/${invoiceId}/payments`, data).then((r) => r.data),
  markOverdue: () => http.post("/invoices/mark-overdue").then((r) => r.data),
  triggerSuspend: () => http.post("/invoices/trigger-suspend").then((r) => r.data),
  previewMonthly: (period: string) =>
    http.get<InvoicePreviewResult>("/invoices/generate-monthly/preview", { params: { period } }).then((r) => r.data),
  generateMonthly: (period: string) =>
    http.post<{ period: string; created: number; skipped: number }>("/invoices/generate-monthly", { period }).then((r) => r.data),
  overdueReport: (minDays = 0) =>
    http
      .get<OverdueReport>("/invoices/overdue-report", { params: { min_days_overdue: minDays } })
      .then((r) => r.data),
  overdueReportCsv: (minDays = 0) => {
    const params = new URLSearchParams({ format: "csv", min_days_overdue: String(minDays) });
    window.open(`/api/v1/invoices/overdue-report?${params}`, "_blank");
  },
  pdfUrl: (id: number) => `/api/v1/invoices/${id}/pdf`,
  mpLink: (id: number) =>
    http.post<{ init_point: string; preference_id: string }>(`/invoices/${id}/mp-link`).then((r) => r.data),
  emitCae: (id: number) =>
    http.post<{ cae: string; cae_fch_vto: string; cbte_nro: number }>(`/invoices/${id}/emit-cae`).then((r) => r.data),
};

// ── Ubiquiti ──────────────────────────────────────────────────────────────────
export const ubiquitiApi = {
  list: () => http.get<UbiquitiDevice[]>("/ubiquiti/").then((r) => r.data),
  listFree: () => http.get<UbiquitiDevice[]>("/ubiquiti/", { params: { free: true } }).then((r) => r.data),
  get: (id: number) => http.get<UbiquitiDevice>(`/ubiquiti/${id}`).then((r) => r.data),
  create: (data: Partial<UbiquitiDevice> & { password?: string }) =>
    http.post<UbiquitiDevice>("/ubiquiti/", data).then((r) => r.data),
  update: (id: number, data: Partial<UbiquitiDevice> & { password?: string }) =>
    http.put<UbiquitiDevice>(`/ubiquiti/${id}`, data).then((r) => r.data),
  delete: (id: number) => http.delete(`/ubiquiti/${id}`),
  test: (id: number) => http.post<UbiquitiDevice>(`/ubiquiti/${id}/test`).then((r) => r.data),
  getInfo: (id: number) =>
    http.get<UbiquitiDeviceInfo>(`/ubiquiti/${id}/info`).then((r) => r.data),
  getWireless: (id: number) =>
    http.get<UbiquitiWirelessConfig>(`/ubiquiti/${id}/wireless`).then((r) => r.data),
  setWireless: (id: number, data: { frequency_mhz?: number; channel_width_mhz?: number; tx_power_dbm?: number }) =>
    http.put<UbiquitiWirelessConfig>(`/ubiquiti/${id}/wireless`, data).then((r) => r.data),
  getLink: (id: number) =>
    http.get<UbiquitiLinkInfo>(`/ubiquiti/${id}/link`).then((r) => r.data),
  getStations: (id: number) =>
    http.get<UbiquitiStation[]>(`/ubiquiti/${id}/stations`).then((r) => r.data),
  survey: (id: number) =>
    http.get<UbiquitiSurveyScan[]>(`/ubiquiti/${id}/survey`).then((r) => r.data),
  recommendations: (id: number) =>
    http.get<FrequencyRecommendation[]>(`/ubiquiti/${id}/recommendations`).then((r) => r.data),
  clients: (id: number) =>
    http.get<Array<{ id: number; full_name: string; ip_address: string; mac_address?: string; status: string }>>(`/ubiquiti/${id}/clients`).then((r) => r.data),
  uploadFirmware: (deviceId: number, file: File) => {
    const fd = new FormData();
    fd.append("firmware", file);
    return http.post<{ status: string; message: string }>(`/ubiquiti/${deviceId}/firmware`, fd, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 120000,
    }).then((r) => r.data);
  },
  importCsv: (file: File) =>
    http.post<{ created: number; errors: { row: number; error: string }[] }>(
      "/ubiquiti/import",
      (() => { const fd = new FormData(); fd.append("file", file); return fd; })(),
      { headers: { "Content-Type": "multipart/form-data" } }
    ).then(r => r.data),
  probe: (host: string, username: string, password: string, deviceType = "airmax_ac_ap") =>
    http.post<DiscoveredUbiquitiDevice>("/ubiquiti/probe", {
      subnet: host,
      username,
      password,
      device_type: deviceType,
    }, { timeout: 30000 }).then(r => r.data),
  discover: (subnet: string, username: string, password: string, deviceType = "airmax_ac_ap") =>
    http.post<DiscoveredUbiquitiDevice[]>("/ubiquiti/discover", {
      subnet,
      username,
      password,
      device_type: deviceType,
    }, { timeout: 300000 }).then(r => r.data),
};

// ── Firewall & QoS ────────────────────────────────────────────────────────────
export const firewallApi = {
  dhcpScan: (routerId: number) =>
    http.get<DHCPScanResponse>(`/firewall/${routerId}/dhcp-scan`).then((r) => r.data),
  getFilterRules: (routerId: number) =>
    http.get<FirewallRule[]>(`/firewall/${routerId}/filter`).then((r) => r.data),
  deleteFilterRule: (routerId: number, ruleId: string) =>
    http.delete(`/firewall/${routerId}/filter/${ruleId}`).then((r) => r.data),
  getMangleRules: (routerId: number) =>
    http.get<MangleRule[]>(`/firewall/${routerId}/mangle`).then((r) => r.data),
  deleteMangleRule: (routerId: number, ruleId: string) =>
    http.delete(`/firewall/${routerId}/mangle/${ruleId}`).then((r) => r.data),
  applyTemplate: (routerId: number, template: string) =>
    http.post<TemplateResult>(`/firewall/${routerId}/templates/${template}`).then((r) => r.data),
  getPCQQueues: (routerId: number) =>
    http.get<PCQQueue[]>(`/firewall/${routerId}/pcq`).then((r) => r.data),
  setupPCQ: (routerId: number) =>
    http.post<{ added: number }>(`/firewall/${routerId}/pcq/setup`).then((r) => r.data),
  dhcpImport: (routerId: number, items: { address: string; mac_address: string; hostname?: string }[], plan_id: number) =>
    http.post<{ created: number; skipped: number }>(`/firewall/${routerId}/dhcp-import`, { items, plan_id }).then((r) => r.data),
};

// ── Tickets ───────────────────────────────────────────────────────────────────
export const ticketsApi = {
  list: (params?: { status?: string; priority?: string; category?: string; client_id?: number; assigned_to_id?: number }) =>
    http.get<import("@/types").Ticket[]>("/tickets/", { params }).then((r) => r.data),
  get: (id: number) => http.get<import("@/types").Ticket>(`/tickets/${id}`).then((r) => r.data),
  create: (data: { title: string; description?: string; client_id?: number; assigned_to_id?: number; priority?: string; category?: string }) =>
    http.post<import("@/types").Ticket>("/tickets/", data).then((r) => r.data),
  update: (id: number, data: { title?: string; description?: string; status?: string; priority?: string; category?: string; assigned_to_id?: number; client_id?: number }) =>
    http.put<import("@/types").Ticket>(`/tickets/${id}`, data).then((r) => r.data),
  delete: (id: number) => http.delete(`/tickets/${id}`),
  addComment: (ticketId: number, body: string) =>
    http.post<import("@/types").TicketComment>(`/tickets/${ticketId}/comments`, { body }).then((r) => r.data),
  uploadAttachment: (ticketId: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return http.post<{ url: string }>(`/tickets/${ticketId}/attachments`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    }).then((r) => r.data);
  },
};

// ── Work Orders ──────────────────────────────────────────────────────────────
export const workOrdersApi = {
  list: (params?: { status?: string; assigned_to_id?: number }) =>
    http.get<import("@/types").WorkOrder[]>("/work-orders/", { params }).then((r) => r.data),
  get: (id: number) => http.get<import("@/types").WorkOrder>(`/work-orders/${id}`).then((r) => r.data),
  create: (data: Partial<import("@/types").WorkOrder>) =>
    http.post<import("@/types").WorkOrder>("/work-orders/", data).then((r) => r.data),
  update: (id: number, data: Partial<import("@/types").WorkOrder>) =>
    http.put<import("@/types").WorkOrder>(`/work-orders/${id}`, data).then((r) => r.data),
  delete: (id: number) => http.delete(`/work-orders/${id}`),
};

// ── Reports ───────────────────────────────────────────────────────────────────
export const reportsApi = {
  monthlyRevenue: (months = 12) =>
    http.get<Array<{ period: string; revenue: number; count: number }>>("/reports/monthly-revenue", { params: { months } }).then((r) => r.data),
  invoiceStatusBreakdown: () =>
    http.get<Array<{ status: string; count: number; total: number }>>("/reports/invoice-status-breakdown").then((r) => r.data),
  clientsByPlan: () =>
    http.get<Array<{ plan: string; count: number }>>("/reports/clients-by-plan").then((r) => r.data),
  paymentMethods: () =>
    http.get<Array<{ method: string; count: number; total: number }>>("/reports/payment-methods").then((r) => r.data),
  arpu: () =>
    http.get<Array<{ plan_name: string; client_count: number; total_revenue: number; avg_invoice: number }>>("/reports/arpu-by-plan").then((r) => r.data),
  churn: (months = 12) =>
    http.get<Array<{ period: string; suspended: number; cancelled: number; total_active: number }>>("/reports/churn", { params: { months } }).then((r) => r.data),
  revenueByZone: () =>
    http.get<Array<{ zone_name: string; color: string; client_count: number; total_revenue: number }>>("/reports/revenue-by-zone").then((r) => r.data),
  oversubscription: () =>
    http.get<Array<{
      router_id: number; router_name: string; location?: string;
      uplink_download_mbps?: number; uplink_upload_mbps?: number;
      subscribed_download_mbps: number; subscribed_upload_mbps: number;
      active_clients: number; oversubscription_dl?: number; oversubscription_ul?: number;
    }>>("/reports/oversubscription").then((r) => r.data),
  upgradeCandidates: (days = 30, threshold_pct = 80) =>
    http.get<Array<{
      client_id: number; client_name: string; plan_name: string;
      plan_download_mbps: number; plan_upload_mbps: number;
      peak_download_pct: number; peak_upload_pct: number; peak_pct: number;
    }>>("/reports/upgrade-candidates", { params: { days, threshold_pct } }).then((r) => r.data),
};

// ── Inventory ─────────────────────────────────────────────────────────────────
export const inventoryApi = {
  list: (params?: { status?: string; category?: string; search?: string }) =>
    http.get<import("@/types").InventoryItem[]>("/inventory/", { params }).then((r) => r.data),
  summary: () =>
    http.get<Array<{ category: string; status: string; count: number; qty: number }>>("/inventory/summary").then((r) => r.data),
  create: (data: Partial<import("@/types").InventoryItem>) =>
    http.post<import("@/types").InventoryItem>("/inventory/", data).then((r) => r.data),
  update: (id: number, data: Partial<import("@/types").InventoryItem>) =>
    http.put<import("@/types").InventoryItem>(`/inventory/${id}`, data).then((r) => r.data),
  delete: (id: number) => http.delete(`/inventory/${id}`),
};

// ── Notifications ─────────────────────────────────────────────────────────────
export const notificationsApi = {
  sendOne: (client_id: number, message: string, phone?: string) =>
    http.post("/notifications/whatsapp/send", { client_id, message, phone }).then((r) => r.data),
  bulkReminder: (params?: { template?: string; min_days_overdue?: number; dry_run?: boolean }) =>
    http.post<{ sent: number; failed: number; skipped_no_phone: number; details: any[] }>("/notifications/whatsapp/bulk-reminder", params ?? {}).then((r) => r.data),
};

// ── Push notifications ────────────────────────────────────────────────────────
export const pushApi = {
  getVapidKey: () => http.get<{ public_key: string }>("/push/vapid-key").then((r) => r.data),
  subscribe: (sub: { endpoint: string; keys: { p256dh: string; auth: string } }) =>
    http.post("/push/subscribe", sub),
  unsubscribe: (sub: { endpoint: string; keys: { p256dh: string; auth: string } }) =>
    http.delete("/push/subscribe", { data: sub }),
};

// ── Admin ─────────────────────────────────────────────────────────────────────
export const adminApi = {
  auditLogs: (params?: { entity_type?: string; entity_id?: number; limit?: number }) =>
    http.get<AuditLogEntry[]>("/admin/audit-logs", { params }).then((r) => r.data),
  ipPool: (subnet: string) =>
    http.get<IpPoolResponse>("/admin/ip-pool", { params: { subnet } }).then((r) => r.data),
  bandwidthHistory: (routerId: number, hours = 24) =>
    http.get<BandwidthHistoryEntry[]>("/admin/bandwidth-history", {
      params: { router_id: routerId, hours },
    }).then((r) => r.data),
  mapData: () => http.get("/admin/map-data").then((r) => r.data),
  getConfig: () => http.get<Record<string, string>>("/admin/config").then((r) => r.data),
  updateConfig: (data: Record<string, string>) => http.put<Record<string, string>>("/admin/config", data).then((r) => r.data),
  testEmail: () => http.post<{ ok: boolean; message: string }>("/admin/test-email").then((r) => r.data),
};

export interface MyPermissions {
  role: string;
  is_admin: boolean;
  permissions: Record<string, { can_view: boolean; can_edit: boolean }>;
}

export interface RolePermission {
  role: string;
  section: string;
  can_view: boolean;
  can_edit: boolean;
}

export interface UserPermissionEntry {
  section: string;
  can_view: boolean;
  can_edit: boolean;
  is_override: boolean;
}

export const permissionsApi = {
  my: () => http.get<MyPermissions>("/permissions/my").then((r) => r.data),
  list: () => http.get<RolePermission[]>("/permissions/").then((r) => r.data),
  update: (role: string, section: string, can_view: boolean, can_edit: boolean) =>
    http.put<RolePermission>(`/permissions/${role}/${section}`, { can_view, can_edit }).then((r) => r.data),
  getUserPerms: (userId: number) =>
    http.get<UserPermissionEntry[]>(`/permissions/users/${userId}`).then((r) => r.data),
  setUserPerm: (userId: number, section: string, can_view: boolean, can_edit: boolean) =>
    http.put<UserPermissionEntry>(`/permissions/users/${userId}/${section}`, { can_view, can_edit }).then((r) => r.data),
  deleteUserPerm: (userId: number, section: string) =>
    http.delete(`/permissions/users/${userId}/${section}`),
};

export const alarmsApi = {
  list: (status?: string) =>
    http.get<import("@/types").Alarm[]>("/alarms/", { params: status ? { status } : {} }).then(r => r.data),
  countActive: () =>
    http.get<{ count: number }>("/alarms/count-active").then(r => r.data),
};

export const wanApi = {
  list: (routerId: number) =>
    http.get<WanInterface[]>(`/routers/${routerId}/wan`).then(r => r.data),
  create: (routerId: number, data: { interface_name: string; display_name?: string; weight?: number; cap_gb?: number; enabled?: boolean }) =>
    http.post<WanInterface>(`/routers/${routerId}/wan`, data).then(r => r.data),
  update: (routerId: number, wanId: number, data: Partial<{ display_name: string; weight: number; cap_gb: number; enabled: boolean }>) =>
    http.put<WanInterface>(`/routers/${routerId}/wan/${wanId}`, data).then(r => r.data),
  remove: (routerId: number, wanId: number) =>
    http.delete(`/routers/${routerId}/wan/${wanId}`),
  toggle: (routerId: number, wanId: number) =>
    http.post<{ enabled: boolean; manual_override: boolean }>(`/routers/${routerId}/wan/${wanId}/toggle`).then(r => r.data),
  clearOverride: (routerId: number, wanId: number) =>
    http.post(`/routers/${routerId}/wan/${wanId}/clear-override`).then(r => r.data),
  createSchedule: (routerId: number, wanId: number, data: { action: string; days: string; time_start: string; time_end: string }) =>
    http.post<WanSchedule>(`/routers/${routerId}/wan/${wanId}/schedules`, data).then(r => r.data),
  deleteSchedule: (routerId: number, wanId: number, schedId: number) =>
    http.delete(`/routers/${routerId}/wan/${wanId}/schedules/${schedId}`),
  updateSchedule: (routerId: number, wanId: number, schedId: number, data: { action?: string; days?: string; time_start?: string; time_end?: string }) =>
    http.put<WanSchedule>(`/routers/${routerId}/wan/${wanId}/schedules/${schedId}`, data).then(r => r.data),
  applyLoadBalance: (routerId: number, wans: { wan_interface_id: number; gateway: string }[]) =>
    http.post(`/routers/${routerId}/wan/apply-load-balance`, { wans }).then(r => r.data),
  removeLoadBalance: (routerId: number) =>
    http.post(`/routers/${routerId}/wan/remove-load-balance`).then(r => r.data),
};

export default http;

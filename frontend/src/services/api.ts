import axios from "axios";
import type {
  Client,
  DashboardStats,
  DHCPScanResponse,
  FirewallRule,
  Invoice,
  MangleRule,
  MikrotikQueue,
  PCQQueue,
  Plan,
  Router,
  RouterStats,
  TemplateResult,
  User,
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

// Redirect to login on 401
http.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("access_token");
      window.location.href = "/login";
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

// ── Dashboard ─────────────────────────────────────────────────────────────────
export const dashboardApi = {
  stats: () => http.get<DashboardStats>("/dashboard/stats").then((r) => r.data),
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
  syncMikrotik: (id: number) =>
    http.post(`/clients/${id}/sync-mikrotik`).then((r) => r.data),
  invoices: (id: number) =>
    http.get<Invoice[]>(`/clients/${id}/invoices`).then((r) => r.data),
};

// ── Invoices ──────────────────────────────────────────────────────────────────
export const invoicesApi = {
  list: (params?: { status?: string; period?: string; client_id?: number }) =>
    http.get<Invoice[]>("/invoices/", { params }).then((r) => r.data),
  get: (id: number) => http.get<Invoice>(`/invoices/${id}`).then((r) => r.data),
  create: (data: Partial<Invoice>) =>
    http.post<Invoice>("/invoices/", data).then((r) => r.data),
  update: (id: number, data: Partial<Invoice>) =>
    http.put<Invoice>(`/invoices/${id}`, data).then((r) => r.data),
  addPayment: (invoiceId: number, data: object) =>
    http.post(`/invoices/${invoiceId}/payments`, data).then((r) => r.data),
  markOverdue: () => http.post("/invoices/mark-overdue").then((r) => r.data),
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
};

export default http;

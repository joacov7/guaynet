export type ClientStatus = "active" | "suspended" | "cancelled";
export type DeviceStatus = "online" | "offline" | "unknown";
export type InvoiceStatus = "draft" | "pending" | "paid" | "overdue" | "cancelled";
export type PaymentMethod = "cash" | "transfer" | "mercadopago" | "other";
export type UbiquitiDeviceType =
  | "airmax_ap"
  | "airmax_station"
  | "unifi_ap"
  | "unifi_switch"
  | "unifi_gateway";

export interface Plan {
  id: number;
  name: string;
  description?: string;
  download_mbps: number;
  upload_mbps: number;
  burst_download_mbps?: number;
  burst_upload_mbps?: number;
  burst_threshold_mbps?: number;
  burst_time_seconds: number;
  price: number;
  is_active: boolean;
  mikrotik_max_limit: string;
  mikrotik_burst_limit?: string;
  client_count: number;
}

export interface Router {
  id: number;
  name: string;
  host: string;
  port: number;
  username: string;
  location?: string;
  notes?: string;
  status: DeviceStatus;
  last_seen?: string;
  client_count: number;
}

export interface RouterStats {
  identity: string;
  version: string;
  uptime: string;
  cpu_load: string;
  free_memory: string;
  total_memory: string;
  board_name: string;
}

export interface MikrotikQueue {
  id: string;
  name: string;
  target: string;
  max_limit: string;
  burst_limit?: string;
  disabled: boolean;
  comment?: string;
  bytes?: string;
  packets?: string;
}

export interface Client {
  id: number;
  first_name: string;
  last_name: string;
  full_name: string;
  dni?: string;
  cuit?: string;
  phone?: string;
  email?: string;
  address?: string;
  notes?: string;
  ip_address: string;
  mac_address?: string;
  plan_id: number;
  router_id: number;
  ubiquiti_device_id?: number;
  status: ClientStatus;
  service_start_date?: string;
  billing_day: number;
  mikrotik_queue_name: string;
  plan?: Pick<Plan, "id" | "name" | "download_mbps" | "upload_mbps" | "price">;
  router?: Pick<Router, "id" | "name" | "location">;
  created_at: string;
}

export interface Invoice {
  id: number;
  client_id: number;
  period: string;
  amount: number;
  issue_date: string;
  due_date: string;
  paid_date?: string;
  status: InvoiceStatus;
  notes?: string;
  afip_cae?: string;
  invoice_number?: number;
  payments: Payment[];
  created_at: string;
}

export interface Payment {
  id: number;
  amount: number;
  payment_date: string;
  method: PaymentMethod;
  reference?: string;
  notes?: string;
  created_at: string;
}

export interface DashboardStats {
  total_clients: number;
  active_clients: number;
  suspended_clients: number;
  cancelled_clients: number;
  invoices_pending: number;
  invoices_overdue: number;
  revenue_this_month: number;
  revenue_last_month: number;
  total_routers: number;
  routers_online: number;
  routers_offline: number;
  router_statuses: Array<{
    id: number;
    name: string;
    location?: string;
    status: string;
    client_count: number;
  }>;
}

export interface User {
  id: number;
  username: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_superuser: boolean;
}

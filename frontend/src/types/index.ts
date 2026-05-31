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
  latitude?: number;
  longitude?: number;
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
  latitude?: number;
  longitude?: number;
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
  role: string;
  is_active: boolean;
  is_superuser: boolean;
}

export interface VpnConnection {
  id: number;
  name: string;
  vpn_type: "wireguard" | "l2tp";
  router_id?: number;
  router_name?: string;
  wg_server_endpoint?: string;
  wg_server_port?: number;
  wg_server_public_key?: string;
  wg_client_private_key?: string;
  wg_client_public_key?: string;
  wg_client_ip?: string;
  wg_server_wg_ip?: string;
  wg_keepalive?: number;
  l2tp_server_host?: string;
  l2tp_username?: string;
  l2tp_password?: string;
  l2tp_ipsec_secret?: string;
  l2tp_local_ip?: string;
  l2tp_remote_ip?: string;
  notes?: string;
  created_at?: string;
}

export interface DHCPLease {
  address: string;
  mac_address: string;
  hostname?: string;
  comment?: string;
  status: string;
  is_registered: boolean;
  client_id?: number;
  client_name?: string;
}

export interface DHCPScanResponse {
  total: number;
  registered: number;
  unregistered: number;
  leases: DHCPLease[];
}

export interface FirewallRule {
  id: string;
  chain: string;
  action: string;
  src_address?: string;
  dst_address?: string;
  protocol?: string;
  src_port?: string;
  dst_port?: string;
  in_interface?: string;
  out_interface?: string;
  comment?: string;
  disabled: boolean;
  bytes?: string;
  packets?: string;
}

export interface MangleRule {
  id: string;
  chain: string;
  action: string;
  new_packet_mark?: string;
  new_connection_mark?: string;
  src_address?: string;
  dst_address?: string;
  protocol?: string;
  dst_port?: string;
  comment?: string;
  disabled: boolean;
  passthrough: boolean;
}

export interface PCQQueue {
  id: string;
  name: string;
  kind: string;
  pcq_rate?: string;
  pcq_limit?: string;
  pcq_classifier?: string;
}

export interface TemplateResult {
  template: string;
  rules_added: number;
  message: string;
}

export interface BandwidthEntry {
  queue_name: string;
  client_id?: number;
  client_name?: string;
  ip_address: string;
  max_limit: string;
  disabled: boolean;
  upload_bytes: number;
  download_bytes: number;
}

export interface OnlineClient {
  client_id?: number;
  client_name?: string;
  ip_address: string;
  mac_address: string;
  status?: string;
  online: boolean;
}

export interface OverdueEntry {
  client_id: number;
  client_name: string;
  phone: string;
  email: string;
  address: string;
  invoice_id: number;
  period: string;
  amount: number;
  due_date: string;
  days_overdue: number;
}

export interface OverdueReport {
  total: number;
  total_amount: number;
  items: OverdueEntry[];
}

export interface UbiquitiDevice {
  id: number;
  name: string;
  host: string;
  device_type: UbiquitiDeviceType;
  username?: string;
  mac_address?: string;
  mikrotik_router_id?: number;
  location?: string;
  notes?: string;
  latitude?: number;
  longitude?: number;
  status: "online" | "offline" | "unknown";
  last_seen?: string;
  model_name?: string;
  firmware_version?: string;
  ssid?: string;
  frequency_mhz?: number;
  channel_width_mhz?: number;
  signal_dbm?: number;
  ccq?: number;
  client_count: number;
}

export interface UbiquitiDeviceInfo {
  model: string;
  firmware: string;
  hostname: string;
  uptime_seconds: number;
  cpu_load: number;
  ram_used_pct: number;
}

export interface UbiquitiWirelessConfig {
  mode: string;
  ssid: string;
  frequency_mhz?: number;
  channel_width_mhz?: number;
  tx_power_dbm?: number;
  security: string;
}

export interface UbiquitiLinkInfo {
  remote_name: string;
  remote_mac: string;
  signal_dbm?: number;
  noise_dbm?: number;
  snr_db?: number;
  ccq?: number;
  rx_rate_mbps?: number;
  tx_rate_mbps?: number;
  distance_m?: number;
}

export interface UbiquitiStation {
  mac: string;
  ip: string;
  name: string;
  signal_dbm?: number;
  noise_dbm?: number;
  ccq?: number;
  rx_rate_mbps?: number;
  tx_rate_mbps?: number;
  uptime_seconds?: number;
}

export interface UbiquitiSurveyScan {
  ssid: string;
  mac: string;
  frequency_mhz?: number;
  channel_width_mhz?: number;
  signal_dbm?: number;
  security: string;
}

export interface FrequencyRecommendation {
  frequency_mhz: number;
  network_count: number;
  congestion_score: number;
  recommendation: string;
  networks: string[];
}

export interface AuditLogEntry {
  id: number;
  username: string;
  action: string;
  entity_type: string;
  entity_id?: number;
  entity_name: string;
  details?: string;
  created_at: string;
}

export interface BandwidthHistoryEntry {
  sampled_at: string;
  client_id?: number;
  ip_address: string;
  queue_name: string;
  upload_bytes: number;
  download_bytes: number;
}

export interface IpPoolEntry {
  ip: string;
  free: boolean;
  client_id?: number;
  client_name?: string;
  status?: string;
}

export interface IpPoolResponse {
  subnet: string;
  total_hosts: number;
  used: number;
  free: number;
  ips: IpPoolEntry[];
}

export interface MapDataPoint {
  id: number;
  name?: string;
  full_name?: string;
  host?: string;
  ip_address?: string;
  status: string;
  latitude: number;
  longitude: number;
  location?: string;
  client_count?: number;
  ssid?: string;
  frequency_mhz?: number;
  device_type?: string;
}

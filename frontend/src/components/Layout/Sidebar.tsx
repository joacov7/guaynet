import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Menu } from "antd";
import {
  ApartmentOutlined,
  AuditOutlined,
  BellOutlined,
  SwapOutlined,
  DashboardOutlined,
  DollarOutlined,
  EnvironmentOutlined,
  FileTextOutlined,
  GlobalOutlined,
  MonitorOutlined,
  SafetyOutlined,
  ScanOutlined,
  TagsOutlined,
  TeamOutlined,
  ToolOutlined,
  WifiOutlined,
  ClusterOutlined,
  AreaChartOutlined,
  SettingOutlined,
  UserOutlined,
  LockOutlined,
  CustomerServiceOutlined,
  DatabaseOutlined,
  BarChartOutlined,
  QuestionCircleOutlined,
  SafetyCertificateOutlined,
  UnorderedListOutlined,
  UsergroupAddOutlined,
  UserSwitchOutlined,
  FileProtectOutlined,
  HomeOutlined,
  ThunderboltOutlined,
  WalletOutlined,
  ControlOutlined,
} from "@ant-design/icons";
import { usePermissions } from "@/contexts/PermissionsContext";

export interface NavItem {
  key: string;
  icon: ReactNode;
  label: string;
  /** null = every logged-in user */
  section: string | null;
  adminOnly?: boolean;
}
interface NavGroup {
  key: string;
  icon: ReactNode;
  label: string;
  children: NavItem[];
}

const TOP_FIRST: NavItem = { key: "/", icon: <DashboardOutlined />, label: "Dashboard", section: null };
const TOP_LAST: NavItem = { key: "/help", icon: <QuestionCircleOutlined />, label: "Ayuda", section: null };

export const NAV_GROUPS: NavGroup[] = [
  {
    key: "g-clients", icon: <TeamOutlined />, label: "Clientes", children: [
      { key: "/clients", icon: <TeamOutlined />, label: "Clientes", section: "clients" },
      { key: "/dhcp", icon: <ScanOutlined />, label: "Dispositivos DHCP", section: "clients" },
      { key: "/plans", icon: <TagsOutlined />, label: "Planes", section: "plans" },
      { key: "/zones", icon: <EnvironmentOutlined />, label: "Zonas", section: "zones" },
    ],
  },
  {
    key: "g-money", icon: <WalletOutlined />, label: "Cobranza", children: [
      { key: "/billing", icon: <FileTextOutlined />, label: "Facturación", section: "billing" },
      { key: "/billing/cobros", icon: <DollarOutlined />, label: "Cobros (caja)", section: "billing" },
      { key: "/expenses", icon: <DollarOutlined />, label: "Gastos", section: "expenses" },
      { key: "/reports", icon: <BarChartOutlined />, label: "Reportes", section: "reports" },
    ],
  },
  {
    key: "g-support", icon: <CustomerServiceOutlined />, label: "Soporte", children: [
      { key: "/tickets", icon: <CustomerServiceOutlined />, label: "Tickets", section: "tickets" },
      { key: "/work-orders", icon: <ToolOutlined />, label: "Órdenes de Trabajo", section: "work_orders" },
      { key: "/inventory", icon: <DatabaseOutlined />, label: "Inventario", section: "inventory" },
    ],
  },
  {
    key: "g-network", icon: <ApartmentOutlined />, label: "Red", children: [
      { key: "/monitoring", icon: <MonitorOutlined />, label: "Monitoreo", section: "monitoring" },
      { key: "/alarms", icon: <BellOutlined />, label: "Alarmas", section: "alarms" },
      { key: "/routers", icon: <ApartmentOutlined />, label: "Routers", section: "routers" },
      { key: "/wan", icon: <SwapOutlined />, label: "Gestión WAN", section: "routers" },
      { key: "/firewall", icon: <SafetyOutlined />, label: "Firewall & QoS", section: "firewall" },
      { key: "/ubiquiti", icon: <WifiOutlined />, label: "Ubiquiti", section: "ubiquiti" },
      { key: "/map", icon: <GlobalOutlined />, label: "Mapa de Red", section: "map" },
      { key: "/ip-pool", icon: <ClusterOutlined />, label: "Pool de IPs", section: "ip_pool" },
      { key: "/bandwidth", icon: <AreaChartOutlined />, label: "Ancho de Banda", section: "bandwidth" },
      { key: "/vpn", icon: <LockOutlined />, label: "VPN", section: null, adminOnly: true },
    ],
  },
  {
    key: "g-security", icon: <SafetyCertificateOutlined />, label: "Seguridad", children: [
      { key: "/security", icon: <SafetyCertificateOutlined />, label: "Resumen", section: "security_alerts" },
      { key: "/security/operator-panel", icon: <MonitorOutlined />, label: "Central Monitoreo", section: "security_alerts" },
      { key: "/security/properties", icon: <HomeOutlined />, label: "Propiedades", section: "security_properties" },
      { key: "/security/plans", icon: <TagsOutlined />, label: "Planes Seguridad", section: "security_plans" },
      { key: "/security/subscriptions", icon: <SafetyCertificateOutlined />, label: "Abonados Seguridad", section: "security_subscriptions" },
      { key: "/security/alerts", icon: <BellOutlined />, label: "Historial Alertas", section: "security_alerts" },
      { key: "/security/entry-secure", icon: <SafetyOutlined />, label: "Entrada Segura", section: "security_entry_sessions" },
      { key: "/security/events", icon: <UnorderedListOutlined />, label: "Historial Eventos", section: "security_events" },
      { key: "/security/neighborhood", icon: <UsergroupAddOutlined />, label: "Grupos Vecinales", section: "security_neighborhood" },
      { key: "/security/members", icon: <UserSwitchOutlined />, label: "Miembros", section: "security_members" },
      { key: "/security/contracts", icon: <FileProtectOutlined />, label: "Contratos", section: "security_contracts" },
      { key: "/security/settings", icon: <SettingOutlined />, label: "Config. Seguridad", section: "security_settings" },
    ],
  },
  {
    key: "g-admin", icon: <ControlOutlined />, label: "Administración", children: [
      { key: "/users", icon: <UserOutlined />, label: "Usuarios", section: null, adminOnly: true },
      { key: "/permissions", icon: <SettingOutlined />, label: "Permisos", section: null, adminOnly: true },
      { key: "/settings", icon: <SettingOutlined />, label: "Configuración", section: null, adminOnly: true },
      { key: "/automations", icon: <ThunderboltOutlined />, label: "Automatizaciones", section: null, adminOnly: true },
      { key: "/audit", icon: <AuditOutlined />, label: "Auditoría", section: "audit" },
    ],
  },
];

/** Screens this user can open, with their group name (also used by the global search). */
export function useVisibleNav() {
  const { canView, isAdmin } = usePermissions();
  return useMemo(() => {
    const allowed = (i: NavItem) => (i.adminOnly ? isAdmin : !i.section || canView(i.section));
    const groups = NAV_GROUPS.map((g) => ({ ...g, children: g.children.filter(allowed) })).filter((g) => g.children.length);
    const flat = [
      { ...TOP_FIRST, group: "" },
      ...groups.flatMap((g) => g.children.map((c) => ({ ...c, group: g.label }))),
      { ...TOP_LAST, group: "" },
    ];
    return { groups, flat };
  }, [canView, isAdmin]);
}

/** Longest menu path that is a prefix of the current location ("/security/alerts" beats "/security"). */
function selectedFor(pathname: string, keys: string[]) {
  return keys
    .filter((k) => k !== "/" && (pathname === k || pathname.startsWith(k + "/")))
    .sort((a, b) => b.length - a.length)[0] ?? (pathname === "/" ? "/" : "");
}

export default function Sidebar({ collapsed = false, onNavigate }: { collapsed?: boolean; onNavigate?: () => void }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { groups, flat } = useVisibleNav();

  const selected = selectedFor(location.pathname, flat.map((i) => i.key));
  const currentGroup = groups.find((g) => g.children.some((c) => c.key === selected))?.key;
  const [openKeys, setOpenKeys] = useState<string[]>(currentGroup ? [currentGroup] : []);

  // Opening another screen opens its group (the others the user opened stay as they are)
  useEffect(() => {
    if (currentGroup) setOpenKeys((keys) => (keys.includes(currentGroup) ? keys : [...keys, currentGroup]));
  }, [currentGroup]);

  const items = [
    { key: TOP_FIRST.key, icon: TOP_FIRST.icon, label: TOP_FIRST.label },
    ...groups.map((g) => ({
      key: g.key,
      icon: g.icon,
      label: g.label,
      children: g.children.map((c) => ({ key: c.key, icon: c.icon, label: c.label })),
    })),
    { key: TOP_LAST.key, icon: TOP_LAST.icon, label: TOP_LAST.label },
  ];

  return (
    <Menu
      theme="dark"
      mode="inline"
      inlineCollapsed={collapsed}
      selectedKeys={[selected]}
      {...(collapsed ? {} : { openKeys, onOpenChange: setOpenKeys })}
      items={items}
      onClick={({ key }) => {
        navigate(key);
        onNavigate?.();
      }}
      style={{ borderRight: 0, marginTop: 8 }}
    />
  );
}

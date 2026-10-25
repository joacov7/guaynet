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
} from "@ant-design/icons";
import { usePermissions } from "@/contexts/PermissionsContext";

const ALL_ITEMS = [
  { key: "/",          icon: <DashboardOutlined />,  label: "Dashboard",       section: null },
  { key: "/clients",   icon: <TeamOutlined />,        label: "Clientes",        section: "clients" },
  { key: "/plans",     icon: <TagsOutlined />,        label: "Planes",          section: "plans" },
  { key: "/zones",     icon: <EnvironmentOutlined />, label: "Zonas",           section: null },
  { key: "/routers",   icon: <ApartmentOutlined />,   label: "Routers",         section: "routers" },
  { key: "/billing",   icon: <FileTextOutlined />,    label: "Facturación",     section: "billing" },
  { key: "/expenses",  icon: <DollarOutlined />,      label: "Gastos",          section: null },
  { key: "/monitoring",icon: <MonitorOutlined />,     label: "Monitoreo",       section: "monitoring" },
  { key: "/alarms",    icon: <BellOutlined />,        label: "Alarmas",         section: null },
  { key: "/wan",       icon: <SwapOutlined />,        label: "Gestión WAN",     section: null },
  { key: "/firewall",  icon: <SafetyOutlined />,      label: "Firewall & QoS",  section: "firewall" },
  { key: "/ubiquiti",  icon: <WifiOutlined />,        label: "Ubiquiti",        section: "ubiquiti" },
  { key: "/map",       icon: <GlobalOutlined />,      label: "Mapa de Red",     section: "map" },
  { key: "/ip-pool",   icon: <ClusterOutlined />,     label: "Pool de IPs",     section: "ip_pool" },
  { key: "/bandwidth", icon: <AreaChartOutlined />,   label: "Ancho de Banda",  section: "bandwidth" },
  { key: "/audit",     icon: <AuditOutlined />,       label: "Auditoría",       section: "audit" },
  { key: "/tickets",    icon: <CustomerServiceOutlined />, label: "Soporte",       section: null, adminOnly: false },
  { key: "/work-orders", icon: <ToolOutlined />,           label: "Órdenes de Trabajo", section: null, adminOnly: false },
  { key: "/inventory",  icon: <DatabaseOutlined />,      label: "Inventario",      section: null, adminOnly: false },
  { key: "/reports",    icon: <BarChartOutlined />,      label: "Reportes",        section: null, adminOnly: false },
  { key: "/automations", icon: <ThunderboltOutlined />,  label: "Automatizaciones", section: null, adminOnly: true },
  { key: "/vpn",        icon: <LockOutlined />,        label: "VPN",             section: null, adminOnly: true },
  { key: "/users",      icon: <UserOutlined />,        label: "Usuarios",        section: null, adminOnly: true },
  { key: "/permissions",icon: <SettingOutlined />,    label: "Permisos",        section: null, adminOnly: true },
  { key: "/settings",   icon: <SettingOutlined />,    label: "Configuración",   section: null, adminOnly: true },
  { key: "/security",                  icon: <SafetyCertificateOutlined />,        label: "Seguridad",           section: null },
  { key: "/security/operator-panel",   icon: <MonitorOutlined />,       label: "Central Monitoreo",   section: "security_alerts" },
  { key: "/security/properties",       icon: <HomeOutlined />,           label: "Propiedades",         section: "security_subscriptions" },
  { key: "/security/plans",            icon: <TagsOutlined />,           label: "Planes Seguridad",    section: "security_subscriptions" },
  { key: "/security/subscriptions",    icon: <SafetyCertificateOutlined />,        label: "Abonados Seguridad",  section: "security_subscriptions" },
  { key: "/security/alerts",           icon: <BellOutlined />,          label: "Historial Alertas",   section: "security_alerts" },
  { key: "/security/entry-secure",icon: <SafetyOutlined />,        label: "Entrada Segura",     section: "security_entry_sessions" },
  { key: "/security/events",        icon: <UnorderedListOutlined />,  label: "Historial Eventos",   section: "security_events" },
  { key: "/security/neighborhood",  icon: <UsergroupAddOutlined />,   label: "Grupos Vecinales",    section: "security_neighborhood" },
  { key: "/security/members",       icon: <UserSwitchOutlined />,     label: "Miembros",            section: "security_members" },
  { key: "/security/contracts",       icon: <FileProtectOutlined />,     label: "Contratos",           section: "security_subscriptions" },
  { key: "/security/settings",        icon: <SettingOutlined />,        label: "Config. Seguridad",   section: "security_subscriptions" },
  { key: "/help",       icon: <QuestionCircleOutlined />, label: "Ayuda",          section: null, adminOnly: false },
];

export default function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { canView, isAdmin } = usePermissions();

  const visibleItems = ALL_ITEMS.filter((item) => {
    if (item.adminOnly) return isAdmin;
    if (!item.section) return true;
    return canView(item.section);
  });

  const selectedKey = visibleItems
    .map((i) => i.key)
    .filter((k) => k !== "/")
    .find((k) => location.pathname.startsWith(k)) ?? "/";

  return (
    <Menu
      theme="dark"
      mode="inline"
      selectedKeys={[selectedKey]}
      items={visibleItems}
      onClick={({ key }) => navigate(key)}
      style={{ borderRight: 0, marginTop: 8 }}
    />
  );
}

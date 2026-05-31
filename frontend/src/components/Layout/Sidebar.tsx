import { useLocation, useNavigate } from "react-router-dom";
import { Menu } from "antd";
import {
  ApartmentOutlined,
  AuditOutlined,
  DashboardOutlined,
  FileTextOutlined,
  GlobalOutlined,
  MonitorOutlined,
  SafetyOutlined,
  TagsOutlined,
  TeamOutlined,
  WifiOutlined,
  ClusterOutlined,
  AreaChartOutlined,
  SettingOutlined,
  UserOutlined,
  LockOutlined,
} from "@ant-design/icons";
import { usePermissions } from "@/contexts/PermissionsContext";

const ALL_ITEMS = [
  { key: "/",          icon: <DashboardOutlined />,  label: "Dashboard",       section: null },
  { key: "/clients",   icon: <TeamOutlined />,        label: "Clientes",        section: "clients" },
  { key: "/plans",     icon: <TagsOutlined />,        label: "Planes",          section: "plans" },
  { key: "/routers",   icon: <ApartmentOutlined />,   label: "Routers",         section: "routers" },
  { key: "/billing",   icon: <FileTextOutlined />,    label: "Facturación",     section: "billing" },
  { key: "/monitoring",icon: <MonitorOutlined />,     label: "Monitoreo",       section: "monitoring" },
  { key: "/firewall",  icon: <SafetyOutlined />,      label: "Firewall & QoS",  section: "firewall" },
  { key: "/ubiquiti",  icon: <WifiOutlined />,        label: "Ubiquiti",        section: "ubiquiti" },
  { key: "/map",       icon: <GlobalOutlined />,      label: "Mapa de Red",     section: "map" },
  { key: "/ip-pool",   icon: <ClusterOutlined />,     label: "Pool de IPs",     section: "ip_pool" },
  { key: "/bandwidth", icon: <AreaChartOutlined />,   label: "Ancho de Banda",  section: "bandwidth" },
  { key: "/audit",     icon: <AuditOutlined />,       label: "Auditoría",       section: "audit" },
  { key: "/vpn",        icon: <LockOutlined />,        label: "VPN",             section: null, adminOnly: true },
  { key: "/users",      icon: <UserOutlined />,        label: "Usuarios",        section: null, adminOnly: true },
  { key: "/permissions",icon: <SettingOutlined />,    label: "Permisos",        section: null, adminOnly: true },
  { key: "/settings",   icon: <SettingOutlined />,    label: "Configuración",   section: null, adminOnly: true },
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

import { useLocation, useNavigate } from "react-router-dom";
import { Menu } from "antd";
import {
  DashboardOutlined,
  TeamOutlined,
  TagsOutlined,
  ApartmentOutlined,
  FileTextOutlined,
  SafetyOutlined,
  MonitorOutlined,
} from "@ant-design/icons";

const menuItems = [
  { key: "/", icon: <DashboardOutlined />, label: "Dashboard" },
  { key: "/clients", icon: <TeamOutlined />, label: "Clientes" },
  { key: "/plans", icon: <TagsOutlined />, label: "Planes" },
  { key: "/routers", icon: <ApartmentOutlined />, label: "Routers" },
  { key: "/billing", icon: <FileTextOutlined />, label: "Facturación" },
  { key: "/monitoring", icon: <MonitorOutlined />, label: "Monitoreo" },
  { key: "/firewall", icon: <SafetyOutlined />, label: "Firewall & QoS" },
];

export default function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();

  const selectedKey = menuItems
    .map((i) => i.key)
    .filter((k) => k !== "/")
    .find((k) => location.pathname.startsWith(k)) ?? "/";

  return (
    <Menu
      theme="dark"
      mode="inline"
      selectedKeys={[selectedKey]}
      items={menuItems}
      onClick={({ key }) => navigate(key)}
      style={{ borderRight: 0, marginTop: 8 }}
    />
  );
}

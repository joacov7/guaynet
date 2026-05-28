import { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ConfigProvider, theme, Layout, Menu, Button, Avatar } from "antd";
import { PlayCircleOutlined, SettingOutlined, LogoutOutlined } from "@ant-design/icons";
import { useNavigate, useLocation } from "react-router-dom";
import Login from "./pages/Login";
import Watch from "./pages/Watch";
import Admin from "./pages/Admin";

const { Header, Content } = Layout;

function AppLayout({ role, onLogout }: { role: string; onLogout: () => void }) {
  const navigate = useNavigate();
  const location = useLocation();

  const menuItems = [
    { key: "/", icon: <PlayCircleOutlined />, label: "Ver canales" },
    ...(role === "admin" ? [{ key: "/admin", icon: <SettingOutlined />, label: "Administración" }] : []),
  ];

  return (
    <Layout style={{ minHeight: "100vh", background: "#0a0a0a" }}>
      <Header style={{ background: "#141414", borderBottom: "1px solid #303030", display: "flex", alignItems: "center", padding: "0 24px", gap: 16 }}>
        <span style={{ color: "#fff", fontWeight: 700, fontSize: 18, marginRight: 24 }}>IPTV</span>
        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ flex: 1, background: "transparent", borderBottom: "none" }}
        />
        <Avatar style={{ background: "#1677ff" }}>{role[0].toUpperCase()}</Avatar>
        <Button type="text" icon={<LogoutOutlined />} onClick={onLogout} style={{ color: "#888" }} />
      </Header>
      <Content>
        <Routes>
          <Route path="/" element={<Watch />} />
          {role === "admin" && <Route path="/admin" element={<Admin />} />}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Content>
    </Layout>
  );
}

export default function App() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("iptv_token"));
  const [role, setRole] = useState<string>(() => localStorage.getItem("iptv_role") ?? "viewer");

  useEffect(() => {
    const stored = localStorage.getItem("iptv_token");
    if (stored !== token) setToken(stored);
  }, [token]);

  function handleLogin(r: string) {
    setToken(localStorage.getItem("iptv_token"));
    setRole(r);
  }

  function handleLogout() {
    localStorage.removeItem("iptv_token");
    localStorage.removeItem("iptv_role");
    setToken(null);
    setRole("viewer");
  }

  return (
    <ConfigProvider theme={{ algorithm: theme.darkAlgorithm }}>
      <BrowserRouter>
        {!token ? (
          <Login onLogin={handleLogin} />
        ) : (
          <AppLayout role={role} onLogout={handleLogout} />
        )}
      </BrowserRouter>
    </ConfigProvider>
  );
}

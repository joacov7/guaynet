import { useState } from "react";
import { Outlet, useNavigate } from "react-router-dom";
import { Avatar, Dropdown, Layout, theme } from "antd";
import { LogoutOutlined, UserOutlined } from "@ant-design/icons";
import { useAuth } from "@/hooks/useAuth";
import Sidebar from "./Sidebar";

const { Header, Content, Sider } = Layout;

function HeaderUser() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const items = [
    {
      key: "logout",
      icon: <LogoutOutlined />,
      label: "Cerrar sesión",
      onClick: () => {
        logout();
        navigate("/login");
      },
    },
  ];

  return (
    <Dropdown menu={{ items }} placement="bottomRight">
      <div style={{ cursor: "pointer", display: "flex", alignItems: "center", gap: 8 }}>
        <Avatar size="small" icon={<UserOutlined />} />
        <span style={{ fontSize: 14 }}>{user?.username}</span>
      </div>
    </Dropdown>
  );
}

export default function MainLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const { token } = theme.useToken();

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        theme="dark"
        width={220}
        style={{ position: "fixed", height: "100vh", left: 0, top: 0, zIndex: 100 }}
      >
        <div
          style={{
            height: 48,
            display: "flex",
            alignItems: "center",
            justifyContent: collapsed ? "center" : "flex-start",
            padding: collapsed ? 0 : "0 16px",
            color: "#fff",
            fontWeight: 700,
            fontSize: collapsed ? 18 : 20,
            letterSpacing: 1,
            overflow: "hidden",
            whiteSpace: "nowrap",
          }}
        >
          {collapsed ? "G" : "Guaynet WISP"}
        </div>
        <Sidebar />
      </Sider>

      <Layout style={{ marginLeft: collapsed ? 80 : 220, transition: "margin-left 0.2s" }}>
        <Header
          style={{
            background: token.colorBgContainer,
            padding: "0 24px",
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
            height: 52,
            lineHeight: "52px",
            position: "sticky",
            top: 0,
            zIndex: 99,
            display: "flex",
            justifyContent: "flex-end",
            alignItems: "center",
          }}
        >
          <HeaderUser />
        </Header>
        <Content
          style={{
            padding: 24,
            background: token.colorBgLayout,
            minHeight: "calc(100vh - 52px)",
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}

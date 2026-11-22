import { useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { Avatar, Button, Drawer, Dropdown, Grid, Layout, Space, theme } from "antd";
import { LogoutOutlined, MenuOutlined, UserOutlined } from "@ant-design/icons";
import { useAuth } from "@/hooks/useAuth";
import Sidebar from "./Sidebar";
import GlobalSearch from "./GlobalSearch";
import AttentionBell from "./AttentionBell";

const { Header, Content, Sider } = Layout;
const COLLAPSED_KEY = "guaynet.sidebarCollapsed";

function HeaderUser({ compact }: { compact: boolean }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const items = [
    ...(compact ? [{ key: "who", label: user?.username, disabled: true }] : []),
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
    <Dropdown menu={{ items }} placement="bottomRight" trigger={["click"]}>
      <div style={{ cursor: "pointer", display: "flex", alignItems: "center", gap: 8 }}>
        <Avatar size="small" icon={<UserOutlined />} />
        {!compact && <span style={{ fontSize: 14 }}>{user?.username}</span>}
      </div>
    </Dropdown>
  );
}

function Brand({ short }: { short: boolean }) {
  return (
    <div
      style={{
        height: 48,
        display: "flex",
        alignItems: "center",
        justifyContent: short ? "center" : "flex-start",
        padding: short ? 0 : "0 16px",
        color: "#fff",
        fontWeight: 700,
        fontSize: short ? 18 : 20,
        letterSpacing: 1,
        overflow: "hidden",
        whiteSpace: "nowrap",
      }}
    >
      {short ? "G" : "Guaynet WISP"}
    </div>
  );
}

export default function MainLayout() {
  const screens = Grid.useBreakpoint();
  // Until antd measures the screen, `md` is undefined: treat as desktop so nothing jumps on large screens
  const mobile = screens.md === false;
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem(COLLAPSED_KEY) === "1"; } catch { return false; }
  });
  const [drawer, setDrawer] = useState(false);
  const location = useLocation();
  const { token } = theme.useToken();

  useEffect(() => setDrawer(false), [location.pathname]);
  const toggle = (c: boolean) => {
    setCollapsed(c);
    try { localStorage.setItem(COLLAPSED_KEY, c ? "1" : "0"); } catch { /* private mode */ }
  };

  const siderWidth = mobile ? 0 : collapsed ? 80 : 220;

  return (
    <Layout style={{ minHeight: "100vh" }}>
      {mobile ? (
        <Drawer
          open={drawer}
          onClose={() => setDrawer(false)}
          placement="left"
          width={260}
          closable={false}
          styles={{ body: { padding: 0, background: "#001529" }, header: { display: "none" } }}
        >
          <Brand short={false} />
          <Sidebar onNavigate={() => setDrawer(false)} />
        </Drawer>
      ) : (
        <Sider
          collapsible
          collapsed={collapsed}
          onCollapse={toggle}
          theme="dark"
          width={220}
          style={{ position: "fixed", height: "100vh", left: 0, top: 0, zIndex: 100 }}
        >
          <Brand short={collapsed} />
          <div style={{ height: "calc(100vh - 96px)", overflowY: "auto" }}>
            <Sidebar collapsed={collapsed} />
          </div>
        </Sider>
      )}

      <Layout style={{ marginLeft: siderWidth, transition: "margin-left 0.2s", minWidth: 0 }}>
        <Header
          style={{
            background: token.colorBgContainer,
            padding: mobile ? "0 8px" : "0 24px",
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
            height: 52,
            lineHeight: "52px",
            position: "sticky",
            top: 0,
            zIndex: 99,
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          {mobile && (
            <>
              <Button type="text" icon={<MenuOutlined />} aria-label="Menú" onClick={() => setDrawer(true)} />
              <span style={{ fontWeight: 700, fontSize: 16 }}>Guaynet</span>
            </>
          )}
          {!mobile && <GlobalSearch />}
          <Space size={mobile ? 0 : 12} style={{ marginLeft: "auto" }} align="center">
            {mobile && <GlobalSearch compact />}
            <AttentionBell />
            <HeaderUser compact={mobile} />
          </Space>
        </Header>
        <Content
          className="guaynet-content"
          style={{
            padding: mobile ? 12 : 24,
            background: token.colorBgLayout,
            minHeight: "calc(100vh - 52px)",
            minWidth: 0,
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}

import { useEffect, useState } from "react";
import { Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Spin } from "antd";
import { portalApi } from "@/services/api";

export type PortalClient = {
  id: number;
  full_name: string;
  email: string | null;
  phone: string | null;
  address: string | null;
  status: string;
  plan_name: string | null;
  ip_address: string;
};

export const PortalContext = { client: null as PortalClient | null };

const PORTAL_TOKEN_KEY = "portal_access_token";

export function getPortalToken() {
  return localStorage.getItem(PORTAL_TOKEN_KEY);
}
export function setPortalToken(t: string) {
  localStorage.setItem(PORTAL_TOKEN_KEY, t);
}
export function clearPortalToken() {
  localStorage.removeItem(PORTAL_TOKEN_KEY);
}

export default function PortalLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [client, setClient] = useState<PortalClient | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getPortalToken();
    if (!token) { setLoading(false); return; }
    portalApi.me()
      .then((c) => { setClient(c); PortalContext.client = c; })
      .catch(() => clearPortalToken())
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div style={{ height: "100dvh", display: "flex", alignItems: "center", justifyContent: "center", background: "#f0f2f5" }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!client && location.pathname !== "/portal/login") {
    return <Navigate to="/portal/login" replace />;
  }
  if (client && location.pathname === "/portal/login") {
    return <Navigate to="/portal" replace />;
  }
  if (location.pathname === "/portal/login") {
    return <Outlet context={{ client, setClient }} />;
  }

  const tabs = [
    { path: "/portal", label: "Inicio", icon: "🏠", exact: true },
    { path: "/portal/invoices", label: "Facturas", icon: "📄" },
    { path: "/portal/tickets", label: "Soporte", icon: "🎫" },
  ];

  return (
    <div style={{ minHeight: "100dvh", display: "flex", flexDirection: "column", background: "#f0f2f5", maxWidth: 560, margin: "0 auto" }}>
      {/* Header */}
      <div style={{
        background: "#1677ff", color: "#fff",
        padding: "12px 16px",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        boxShadow: "0 2px 8px rgba(0,0,0,.15)",
      }}>
        <span style={{ fontWeight: 700, fontSize: 17 }}>Guaynet · Portal</span>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 13, opacity: 0.85 }}>{client?.full_name}</span>
          <button
            onClick={() => { clearPortalToken(); PortalContext.client = null; navigate("/portal/login"); }}
            style={{ background: "rgba(255,255,255,.2)", border: "none", color: "#fff", borderRadius: 6, padding: "4px 10px", cursor: "pointer", fontSize: 12 }}
          >
            Salir
          </button>
        </div>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        <Outlet context={{ client, setClient }} />
      </div>

      {/* Bottom nav */}
      <div style={{
        background: "#fff", borderTop: "1px solid #e8e8e8",
        display: "flex", flexShrink: 0,
        paddingBottom: "env(safe-area-inset-bottom)",
      }}>
        {tabs.map((item) => {
          const active = item.exact
            ? location.pathname === item.path
            : location.pathname.startsWith(item.path);
          return (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              style={{
                flex: 1, border: "none", background: "none", padding: "10px 0",
                cursor: "pointer", display: "flex", flexDirection: "column",
                alignItems: "center", gap: 2,
                color: active ? "#1677ff" : "#8c8c8c",
                fontWeight: active ? 600 : 400, fontSize: 12,
              }}
            >
              <span style={{ fontSize: 22 }}>{item.icon}</span>
              {item.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

import { useEffect, useState } from "react";
import { Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Spin } from "antd";
import { authApi } from "@/services/api";
import type { User } from "@/types";

export const TechContext = { user: null as User | null };

export default function TechLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      setLoading(false);
      return;
    }
    authApi.me()
      .then((u) => { setUser(u); TechContext.user = u; })
      .catch(() => { localStorage.removeItem("access_token"); })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div style={{ height: "100dvh", display: "flex", alignItems: "center", justifyContent: "center", background: "#0f172a" }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!user && location.pathname !== "/tech/login") {
    return <Navigate to="/tech/login" replace />;
  }

  if (user && location.pathname === "/tech/login") {
    return <Navigate to="/tech/tickets" replace />;
  }

  if (location.pathname === "/tech/login") {
    return <Outlet context={{ user, setUser }} />;
  }

  return (
    <div style={{ height: "100dvh", display: "flex", flexDirection: "column", background: "#f0f2f5", maxWidth: 480, margin: "0 auto" }}>
      {/* Header */}
      <div style={{
        background: "#1677ff",
        color: "#fff",
        padding: "12px 16px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        flexShrink: 0,
        boxShadow: "0 2px 8px rgba(0,0,0,.15)",
      }}>
        <span style={{ fontWeight: 700, fontSize: 17 }}>Guaynet Técnicos</span>
        <span style={{ fontSize: 13, opacity: 0.85 }}>{user?.full_name || user?.username}</span>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: "auto", WebkitOverflowScrolling: "touch" }}>
        <Outlet context={{ user, setUser }} />
      </div>

      {/* Bottom nav */}
      <div style={{
        background: "#fff",
        borderTop: "1px solid #e8e8e8",
        display: "flex",
        flexShrink: 0,
        paddingBottom: "env(safe-area-inset-bottom)",
      }}>
        {[
          { path: "/tech/tickets", label: "Mis tickets", icon: "🎫" },
          { path: "/tech/history", label: "Historial", icon: "📋" },
        ].map((item) => {
          const active = location.pathname.startsWith(item.path);
          return (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              style={{
                flex: 1,
                border: "none",
                background: "none",
                padding: "10px 0",
                cursor: "pointer",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 2,
                color: active ? "#1677ff" : "#8c8c8c",
                fontWeight: active ? 600 : 400,
                fontSize: 12,
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

import { useEffect, useState } from "react";
import { Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Spin } from "antd";
import { authApi, pushApi } from "@/services/api";
import type { User } from "@/types";

export const TechContext = { user: null as User | null };

async function registerPush(user: User) {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) return;
  try {
    const permission = await Notification.requestPermission();
    if (permission !== "granted") return;

    const reg = await navigator.serviceWorker.ready;
    const { public_key } = await pushApi.getVapidKey();

    // Convert base64url to Uint8Array
    const padding = "=".repeat((4 - (public_key.length % 4)) % 4);
    const base64 = (public_key + padding).replace(/-/g, "+").replace(/_/g, "/");
    const rawKey = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));

    const existing = await reg.pushManager.getSubscription();
    if (existing) {
      // Already subscribed — re-register in case server lost it
      await pushApi.subscribe(existing.toJSON() as any);
      return;
    }

    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: rawKey,
    });
    await pushApi.subscribe(sub.toJSON() as any);
  } catch {
    // Push is optional — never break the app
  }
}

function useOnline() {
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => { window.removeEventListener("online", on); window.removeEventListener("offline", off); };
  }, []);
  return online;
}

export default function TechLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const online = useOnline();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      setLoading(false);
      return;
    }
    authApi.me()
      .then((u) => {
        setUser(u);
        TechContext.user = u;
        registerPush(u);
      })
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

      {/* Offline banner */}
      {!online && (
        <div style={{
          background: "#faad14",
          color: "#000",
          textAlign: "center",
          padding: "6px 12px",
          fontSize: 13,
          fontWeight: 600,
          flexShrink: 0,
        }}>
          Sin conexión — mostrando datos guardados
        </div>
      )}

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

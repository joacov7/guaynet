import { useState } from "react";
import { useNavigate, useOutletContext } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Spin, Tag, Typography } from "antd";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import "dayjs/locale/es";
import { workOrdersApi } from "@/services/api";
import type { User, WorkOrder } from "@/types";

dayjs.extend(relativeTime);
dayjs.locale("es");

const { Text } = Typography;

const STATUS_COLOR: Record<string, string> = {
  pending: "#1677ff",
  in_progress: "#fa8c16",
  completed: "#52c41a",
  cancelled: "#8c8c8c",
};
const STATUS_LABEL: Record<string, string> = {
  pending: "Pendiente",
  in_progress: "En progreso",
  completed: "Completada",
  cancelled: "Cancelada",
};
const TYPE_LABEL: Record<string, string> = {
  installation: "Instalación",
  repair: "Reparación",
  maintenance: "Mantenimiento",
  inspection: "Inspección",
  other: "Otro",
};
const PRIORITY_COLOR: Record<string, string> = {
  low: "#8c8c8c",
  medium: "#fa8c16",
  high: "#ff4d4f",
};

const TABS = [
  { key: "pending", label: "Pendiente" },
  { key: "in_progress", label: "En progreso" },
  { key: "completed", label: "Completada" },
] as const;

export default function TechWorkOrders() {
  const navigate = useNavigate();
  const { user } = useOutletContext<{ user: User }>();
  const [tab, setTab] = useState<string>("pending");

  const { data: orders = [], isLoading, isError, refetch } = useQuery({
    queryKey: ["tech-work-orders", user?.id],
    queryFn: () => workOrdersApi.list({ assigned_to_id: user?.id }),
    enabled: !!user?.id,
    refetchInterval: 30000,
    retry: 2,
  });

  const filtered = orders.filter((o) => o.status === tab);

  if (isLoading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: 60 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (isError) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 60, gap: 12 }}>
        <div style={{ fontSize: 36 }}>⚠️</div>
        <Text type="secondary" style={{ textAlign: "center" }}>No se pudieron cargar las órdenes.</Text>
        <button
          onClick={() => refetch()}
          style={{ background: "#1677ff", color: "#fff", border: "none", borderRadius: 8, padding: "10px 24px", fontSize: 14, fontWeight: 600, cursor: "pointer" }}
        >
          Reintentar
        </button>
      </div>
    );
  }

  return (
    <div style={{ padding: "12px 12px 0" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
        <Text style={{ fontWeight: 700, fontSize: 16 }}>Órdenes asignadas</Text>
        <button
          onClick={() => refetch()}
          style={{ background: "none", border: "none", fontSize: 20, cursor: "pointer", padding: 4 }}
        >
          🔄
        </button>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 6, marginBottom: 12, overflowX: "auto" }}>
        {TABS.map((t) => {
          const count = orders.filter((o) => o.status === t.key).length;
          const active = tab === t.key;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              style={{
                background: active ? STATUS_COLOR[t.key] : "#f0f0f0",
                color: active ? "#fff" : "#595959",
                border: "none",
                borderRadius: 20,
                padding: "6px 14px",
                fontSize: 13,
                fontWeight: active ? 700 : 400,
                cursor: "pointer",
                whiteSpace: "nowrap",
                flexShrink: 0,
              }}
            >
              {t.label} {count > 0 && `(${count})`}
            </button>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <div style={{
          background: "#fff", borderRadius: 12, padding: 32, textAlign: "center",
          border: "2px dashed #e8e8e8", marginBottom: 12,
        }}>
          <div style={{ fontSize: 40, marginBottom: 8 }}>✅</div>
          <Text type="secondary">Sin órdenes {STATUS_LABEL[tab].toLowerCase()}s</Text>
        </div>
      )}

      {filtered.map((wo) => (
        <WorkOrderCard key={wo.id} wo={wo} onClick={() => navigate(`/tech/work-orders/${wo.id}`)} />
      ))}
      <div style={{ height: 12 }} />
    </div>
  );
}

function WorkOrderCard({ wo, onClick }: { wo: WorkOrder; onClick: () => void }) {
  return (
    <div
      onClick={onClick}
      style={{
        background: "#fff",
        borderRadius: 12,
        padding: 16,
        marginBottom: 10,
        boxShadow: "0 2px 8px rgba(0,0,0,.08)",
        border: `2px solid ${PRIORITY_COLOR[wo.priority]}22`,
        cursor: "pointer",
        WebkitTapHighlightColor: "transparent",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
        <Tag color={STATUS_COLOR[wo.status]} style={{ margin: 0, borderRadius: 6, fontSize: 12 }}>
          {STATUS_LABEL[wo.status]}
        </Tag>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <span style={{
            background: PRIORITY_COLOR[wo.priority] + "22",
            color: PRIORITY_COLOR[wo.priority],
            borderRadius: 6, padding: "1px 8px", fontSize: 12, fontWeight: 600,
          }}>
            {wo.priority === "high" ? "Alta" : wo.priority === "medium" ? "Media" : "Baja"}
          </span>
          <Text type="secondary" style={{ fontSize: 11 }}>#{wo.id}</Text>
        </div>
      </div>

      <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 4, lineHeight: 1.3 }}>
        {wo.title}
      </div>

      {wo.client_name && (
        <div style={{ fontSize: 13, color: "#555", marginBottom: 2 }}>👤 {wo.client_name}</div>
      )}

      {wo.address && (
        <div style={{ fontSize: 13, color: "#555", marginBottom: 2 }}>📍 {wo.address}</div>
      )}

      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          {TYPE_LABEL[wo.type] || wo.type}
        </Text>
        <Text type="secondary" style={{ fontSize: 12 }}>
          {wo.scheduled_date ? dayjs(wo.scheduled_date).format("DD/MM HH:mm") : dayjs(wo.created_at).fromNow()}
        </Text>
      </div>
    </div>
  );
}

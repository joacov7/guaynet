import { useNavigate, useOutletContext } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Input, Select, Spin, Tag, Typography } from "antd";
import { useState } from "react";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import "dayjs/locale/es";
import { ticketsApi } from "@/services/api";
import type { Ticket, User } from "@/types";

dayjs.extend(relativeTime);
dayjs.locale("es");

const { Text } = Typography;

const STATUS_COLOR: Record<string, string> = { open: "#1677ff", in_progress: "#fa8c16", resolved: "#52c41a", closed: "#8c8c8c" };
const STATUS_LABEL: Record<string, string> = { open: "Abierto", in_progress: "En curso", resolved: "Resuelto", closed: "Cerrado" };

export default function TechHistory() {
  const navigate = useNavigate();
  const { user } = useOutletContext<{ user: User }>();
  const [statusFilter, setStatusFilter] = useState<string | undefined>();

  const { data: tickets = [], isLoading } = useQuery({
    queryKey: ["tech-history", user?.id, statusFilter],
    queryFn: () => ticketsApi.list({ assigned_to_id: user?.id, status: statusFilter as any }),
    enabled: !!user?.id,
  });

  return (
    <div style={{ padding: "12px 12px 0" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <Text style={{ fontWeight: 700, fontSize: 16 }}>Historial de tickets</Text>
        <Select
          placeholder="Estado"
          size="small"
          style={{ width: 130 }}
          allowClear
          value={statusFilter}
          onChange={setStatusFilter}
          options={Object.entries(STATUS_LABEL).map(([k, v]) => ({ value: k, label: v }))}
        />
      </div>

      {isLoading && (
        <div style={{ display: "flex", justifyContent: "center", padding: 40 }}>
          <Spin />
        </div>
      )}

      {!isLoading && tickets.length === 0 && (
        <div style={{ textAlign: "center", padding: 40 }}>
          <Text type="secondary">No hay tickets.</Text>
        </div>
      )}

      {tickets.map((ticket) => (
        <div
          key={ticket.id}
          onClick={() => navigate(`/tech/tickets/${ticket.id}`)}
          style={{
            background: "#fff",
            borderRadius: 10,
            padding: "12px 14px",
            marginBottom: 8,
            cursor: "pointer",
            border: "1px solid #f0f0f0",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
            <Tag color={STATUS_COLOR[ticket.status]} style={{ margin: 0, borderRadius: 6, fontSize: 12 }}>
              {STATUS_LABEL[ticket.status]}
            </Tag>
            <Text type="secondary" style={{ fontSize: 11 }}>
              {dayjs(ticket.created_at).format("DD/MM/YY")}
            </Text>
          </div>
          <div style={{ fontWeight: 600, fontSize: 14 }}>{ticket.title}</div>
          {ticket.client_name && (
            <Text type="secondary" style={{ fontSize: 12 }}>👤 {ticket.client_name}</Text>
          )}
        </div>
      ))}
      <div style={{ height: 12 }} />
    </div>
  );
}

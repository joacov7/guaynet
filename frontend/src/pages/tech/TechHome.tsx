import { useNavigate, useOutletContext } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Badge, Spin, Tag, Typography } from "antd";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import "dayjs/locale/es";
import { ticketsApi } from "@/services/api";
import type { Ticket, User } from "@/types";

dayjs.extend(relativeTime);
dayjs.locale("es");

const { Text } = Typography;

const PRIORITY_COLOR: Record<string, string> = { low: "#8c8c8c", medium: "#fa8c16", high: "#ff4d4f" };
const PRIORITY_LABEL: Record<string, string> = { low: "Baja", medium: "Media", high: "Alta" };
const STATUS_COLOR: Record<string, string> = { open: "#1677ff", in_progress: "#fa8c16", resolved: "#52c41a", closed: "#8c8c8c" };
const STATUS_LABEL: Record<string, string> = { open: "Abierto", in_progress: "En curso", resolved: "Resuelto", closed: "Cerrado" };
const CATEGORY_LABEL: Record<string, string> = {
  connectivity: "Conectividad", speed: "Velocidad", billing: "Facturación",
  equipment: "Equipo", installation: "Instalación", other: "Otro",
};

export default function TechHome() {
  const navigate = useNavigate();
  const { user } = useOutletContext<{ user: User }>();

  const { data: myTickets = [], isLoading, refetch } = useQuery({
    queryKey: ["tech-tickets", user?.id],
    queryFn: () => ticketsApi.list({ assigned_to_id: user?.id }),
    enabled: !!user?.id,
    refetchInterval: 30000,
  });

  const active = myTickets.filter((t) => t.status === "open" || t.status === "in_progress");
  const resolved = myTickets.filter((t) => t.status === "resolved" || t.status === "closed");

  if (isLoading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: 60 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div style={{ padding: "12px 12px 0" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <Text style={{ fontWeight: 700, fontSize: 16 }}>
          Tickets asignados ({active.length} activos)
        </Text>
        <button
          onClick={() => refetch()}
          style={{ background: "none", border: "none", fontSize: 20, cursor: "pointer", padding: 4 }}
        >
          🔄
        </button>
      </div>

      {active.length === 0 && (
        <div style={{
          background: "#fff", borderRadius: 12, padding: 32, textAlign: "center",
          border: "2px dashed #e8e8e8", marginBottom: 12,
        }}>
          <div style={{ fontSize: 40, marginBottom: 8 }}>✅</div>
          <Text type="secondary">No tenés tickets activos asignados</Text>
        </div>
      )}

      {active.map((ticket) => (
        <TicketCard key={ticket.id} ticket={ticket} onClick={() => navigate(`/tech/tickets/${ticket.id}`)} />
      ))}

      {resolved.length > 0 && (
        <>
          <Text style={{ fontWeight: 600, fontSize: 14, color: "#8c8c8c", display: "block", margin: "16px 0 8px" }}>
            Resueltos recientemente
          </Text>
          {resolved.slice(0, 5).map((ticket) => (
            <TicketCard key={ticket.id} ticket={ticket} onClick={() => navigate(`/tech/tickets/${ticket.id}`)} dim />
          ))}
        </>
      )}
      <div style={{ height: 12 }} />
    </div>
  );
}

function TicketCard({ ticket, onClick, dim }: { ticket: Ticket; onClick: () => void; dim?: boolean }) {
  return (
    <div
      onClick={onClick}
      style={{
        background: dim ? "#fafafa" : "#fff",
        borderRadius: 12,
        padding: 16,
        marginBottom: 10,
        boxShadow: dim ? "none" : "0 2px 8px rgba(0,0,0,.08)",
        border: dim ? "1px solid #f0f0f0" : `2px solid ${PRIORITY_COLOR[ticket.priority]}22`,
        cursor: "pointer",
        opacity: dim ? 0.7 : 1,
        WebkitTapHighlightColor: "transparent",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
        <Tag
          color={STATUS_COLOR[ticket.status]}
          style={{ margin: 0, borderRadius: 6, fontSize: 12 }}
        >
          {STATUS_LABEL[ticket.status]}
        </Tag>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <span style={{
            background: PRIORITY_COLOR[ticket.priority] + "22",
            color: PRIORITY_COLOR[ticket.priority],
            borderRadius: 6,
            padding: "1px 8px",
            fontSize: 12,
            fontWeight: 600,
          }}>
            {PRIORITY_LABEL[ticket.priority]}
          </span>
          <Text type="secondary" style={{ fontSize: 11 }}>#{ticket.id}</Text>
        </div>
      </div>

      <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 4, lineHeight: 1.3 }}>
        {ticket.title}
      </div>

      {ticket.client_name && (
        <div style={{ fontSize: 13, color: "#555", marginBottom: 2 }}>
          👤 {ticket.client_name}
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          {CATEGORY_LABEL[ticket.category]}
        </Text>
        <Text type="secondary" style={{ fontSize: 12 }}>
          {dayjs(ticket.created_at).fromNow()}
        </Text>
      </div>
    </div>
  );
}

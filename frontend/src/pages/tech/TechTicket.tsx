import { useRef, useState } from "react";
import { useNavigate, useOutletContext, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Spin, Tag, Typography, message } from "antd";
import dayjs from "dayjs";
import { ticketsApi, clientsApi } from "@/services/api";
import type { Ticket, User } from "@/types";

const { Text } = Typography;

const STATUS_NEXT: Record<string, { label: string; value: string; color: string }[]> = {
  open:        [{ label: "▶ Iniciar", value: "in_progress", color: "#fa8c16" }],
  in_progress: [
    { label: "✅ Resolver", value: "resolved", color: "#52c41a" },
    { label: "⏸ Pausar", value: "open", color: "#1677ff" },
  ],
  resolved:    [{ label: "🔒 Cerrar", value: "closed", color: "#8c8c8c" }],
  closed:      [],
};

const STATUS_LABEL: Record<string, string> = { open: "Abierto", in_progress: "En curso", resolved: "Resuelto", closed: "Cerrado" };
const STATUS_COLOR: Record<string, string> = { open: "blue", in_progress: "orange", resolved: "green", closed: "default" };
const PRIORITY_LABEL: Record<string, string> = { low: "Baja", medium: "Media", high: "Alta" };
const PRIORITY_COLOR: Record<string, string> = { low: "default", medium: "gold", high: "red" };
const CATEGORY_LABEL: Record<string, string> = {
  connectivity: "Conectividad", speed: "Velocidad", billing: "Facturación",
  equipment: "Equipo", installation: "Instalación", other: "Otro",
};

export default function TechTicket() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { user } = useOutletContext<{ user: User }>();
  const [comment, setComment] = useState("");
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const { data: ticket, isLoading, isError, refetch } = useQuery({
    queryKey: ["tech-ticket", id],
    queryFn: () => ticketsApi.get(Number(id)),
    enabled: !!id,
    retry: 2,
  });

  const updateMutation = useMutation({
    mutationFn: ({ status }: { status: string }) => ticketsApi.update(Number(id), { status }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tech-ticket", id] });
      qc.invalidateQueries({ queryKey: ["tech-tickets"] });
      message.success("Estado actualizado");
    },
    onError: () => message.error("Error al actualizar"),
  });

  const commentMutation = useMutation({
    mutationFn: (body: string) => ticketsApi.addComment(Number(id), body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tech-ticket", id] });
      setComment("");
      message.success("Comentario agregado");
    },
    onError: () => message.error("No se pudo agregar el comentario"),
  });

  async function handlePhoto(file: File) {
    setUploading(true);
    try {
      const { url } = await ticketsApi.uploadAttachment(Number(id), file);
      setComment((prev) => (prev ? prev + "\n" + url : url));
    } catch {
      message.error("No se pudo subir la imagen");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  if (isLoading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: 60 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (isError || !ticket) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 60, gap: 12 }}>
        <div style={{ fontSize: 36 }}>⚠️</div>
        <Text type="secondary" style={{ textAlign: "center" }}>No se pudo cargar el ticket.</Text>
        <div style={{ display: "flex", gap: 10 }}>
          <button
            onClick={() => refetch()}
            style={{
              background: "#1677ff", color: "#fff", border: "none",
              borderRadius: 8, padding: "10px 20px", fontSize: 14,
              fontWeight: 600, cursor: "pointer",
            }}
          >
            Reintentar
          </button>
          <button
            onClick={() => navigate(-1)}
            style={{
              background: "none", color: "#595959", border: "1px solid #d9d9d9",
              borderRadius: 8, padding: "10px 20px", fontSize: 14, cursor: "pointer",
            }}
          >
            Volver
          </button>
        </div>
      </div>
    );
  }

  const nextActions = STATUS_NEXT[ticket.status] ?? [];
  const clientPhone = ticket.client_id ? null : null; // fetched below via ticket

  function mapsUrl(address: string) {
    return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(address)}`;
  }

  return (
    <div style={{ padding: "0 0 80px" }}>
      {/* Back button + header */}
      <div style={{
        background: "#fff",
        padding: "12px 16px",
        display: "flex",
        alignItems: "center",
        gap: 10,
        borderBottom: "1px solid #f0f0f0",
        position: "sticky",
        top: 0,
        zIndex: 10,
      }}>
        <button
          onClick={() => navigate(-1)}
          style={{ background: "none", border: "none", fontSize: 22, cursor: "pointer", padding: 0, lineHeight: 1 }}
        >
          ‹
        </button>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 15, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            #{ticket.id} {ticket.title}
          </div>
          <div style={{ display: "flex", gap: 6, marginTop: 2 }}>
            <Tag color={STATUS_COLOR[ticket.status]} style={{ margin: 0, fontSize: 11 }}>
              {STATUS_LABEL[ticket.status]}
            </Tag>
            <Tag color={PRIORITY_COLOR[ticket.priority]} style={{ margin: 0, fontSize: 11 }}>
              {PRIORITY_LABEL[ticket.priority]}
            </Tag>
          </div>
        </div>
      </div>

      <div style={{ padding: "12px 14px" }}>
        {/* Status action buttons */}
        {nextActions.length > 0 && (
          <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
            {nextActions.map((action) => (
              <button
                key={action.value}
                onClick={() => updateMutation.mutate({ status: action.value })}
                disabled={updateMutation.isPending}
                style={{
                  flex: 1,
                  background: action.color,
                  color: "#fff",
                  border: "none",
                  borderRadius: 10,
                  padding: "14px 8px",
                  fontSize: 15,
                  fontWeight: 700,
                  cursor: "pointer",
                  opacity: updateMutation.isPending ? 0.6 : 1,
                  WebkitTapHighlightColor: "transparent",
                }}
              >
                {action.label}
              </button>
            ))}
          </div>
        )}

        {/* Client info */}
        {ticket.client_name && (
          <div style={{ background: "#fff", borderRadius: 12, padding: 14, marginBottom: 12, boxShadow: "0 1px 4px rgba(0,0,0,.06)" }}>
            <Text type="secondary" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 1 }}>
              Cliente
            </Text>
            <ClientInfo clientId={ticket.client_id!} clientName={ticket.client_name} />
          </div>
        )}

        {/* Description */}
        {ticket.description && (
          <div style={{ background: "#fff", borderRadius: 12, padding: 14, marginBottom: 12, boxShadow: "0 1px 4px rgba(0,0,0,.06)" }}>
            <Text type="secondary" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 1, display: "block", marginBottom: 6 }}>
              Descripción
            </Text>
            <Text style={{ fontSize: 14, lineHeight: 1.5 }}>{ticket.description}</Text>
          </div>
        )}

        {/* Meta */}
        <div style={{ background: "#fff", borderRadius: 12, padding: 14, marginBottom: 12, boxShadow: "0 1px 4px rgba(0,0,0,.06)" }}>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <div>
              <Text type="secondary" style={{ fontSize: 11 }}>Categoría</Text>
              <div style={{ fontWeight: 600, fontSize: 14 }}>{CATEGORY_LABEL[ticket.category]}</div>
            </div>
            <div style={{ textAlign: "right" }}>
              <Text type="secondary" style={{ fontSize: 11 }}>Creado</Text>
              <div style={{ fontWeight: 600, fontSize: 14 }}>{dayjs(ticket.created_at).format("DD/MM/YY HH:mm")}</div>
            </div>
          </div>
        </div>

        {/* Comments */}
        <div style={{ background: "#fff", borderRadius: 12, padding: 14, marginBottom: 12, boxShadow: "0 1px 4px rgba(0,0,0,.06)" }}>
          <Text type="secondary" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 1, display: "block", marginBottom: 8 }}>
            Comentarios ({ticket.comments.length})
          </Text>
          {ticket.comments.map((c) => (
            <div key={c.id} style={{
              borderLeft: "3px solid #1677ff",
              paddingLeft: 10,
              marginBottom: 10,
            }}>
              <Text type="secondary" style={{ fontSize: 11 }}>
                {c.author_name ?? "Sistema"} · {dayjs(c.created_at).format("DD/MM HH:mm")}
              </Text>
              <CommentBody body={c.body} />
            </div>
          ))}

          {/* Add comment */}
          <div style={{ marginTop: 10, display: "flex", gap: 8 }}>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Agregar un comentario..."
              rows={2}
              style={{
                flex: 1,
                border: "1px solid #d9d9d9",
                borderRadius: 8,
                padding: "8px 10px",
                fontSize: 14,
                resize: "none",
                fontFamily: "inherit",
                outline: "none",
              }}
            />
            {/* Photo button */}
            <button
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              style={{
                background: uploading ? "#d9d9d9" : "#f0f0f0",
                color: "#595959",
                border: "none",
                borderRadius: 8,
                padding: "0 12px",
                fontSize: 20,
                cursor: "pointer",
              }}
              title="Adjuntar foto"
            >
              {uploading ? "⏳" : "📷"}
            </button>
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              capture="environment"
              style={{ display: "none" }}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handlePhoto(file);
              }}
            />
            {/* Send button */}
            <button
              onClick={() => comment.trim() && commentMutation.mutate(comment.trim())}
              disabled={!comment.trim() || commentMutation.isPending}
              style={{
                background: "#1677ff",
                color: "#fff",
                border: "none",
                borderRadius: 8,
                padding: "0 14px",
                fontSize: 20,
                cursor: "pointer",
                opacity: !comment.trim() || commentMutation.isPending ? 0.4 : 1,
              }}
            >
              ↑
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

const IMAGE_RE = /^(https?:\/\/\S+|\/uploads\/\S+)\.(jpg|jpeg|png|webp|gif)(\?\S*)?$/i;

function CommentBody({ body }: { body: string }) {
  const lines = body.split("\n");
  return (
    <div style={{ fontSize: 14, marginTop: 2 }}>
      {lines.map((line, i) => {
        if (IMAGE_RE.test(line.trim())) {
          return (
            <a key={i} href={line.trim()} target="_blank" rel="noopener noreferrer">
              <img
                src={line.trim()}
                alt="foto"
                style={{ maxWidth: "100%", borderRadius: 8, marginTop: 4, display: "block" }}
              />
            </a>
          );
        }
        return <div key={i}>{line || " "}</div>;
      })}
    </div>
  );
}

function ClientInfo({ clientId, clientName }: { clientId: number; clientName: string }) {
  const { data: client, isError } = useQuery({
    queryKey: ["client-brief", clientId],
    queryFn: () => clientsApi.get(clientId),
    staleTime: 300_000,
    retry: 1,
  });

  return (
    <div style={{ marginTop: 6 }}>
      <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 8 }}>{clientName}</div>
      {isError && (
        <Text type="secondary" style={{ fontSize: 12 }}>No se pudieron cargar los datos de contacto.</Text>
      )}
      {client?.phone && (
        <a
          href={`tel:${client.phone}`}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            background: "#f6ffed",
            border: "1px solid #b7eb8f",
            borderRadius: 10,
            padding: "10px 14px",
            textDecoration: "none",
            color: "#389e0d",
            fontWeight: 600,
            fontSize: 15,
            marginBottom: 8,
            WebkitTapHighlightColor: "transparent",
          }}
        >
          <span style={{ fontSize: 20 }}>📞</span>
          {client.phone}
        </a>
      )}
      {client?.address && (
        <a
          href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(client.address)}`}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            background: "#e6f4ff",
            border: "1px solid #91caff",
            borderRadius: 10,
            padding: "10px 14px",
            textDecoration: "none",
            color: "#0958d9",
            fontWeight: 500,
            fontSize: 14,
            WebkitTapHighlightColor: "transparent",
          }}
        >
          <span style={{ fontSize: 20 }}>📍</span>
          {client.address}
        </a>
      )}
      {client?.ip_address && (
        <div style={{ marginTop: 6, fontSize: 13, color: "#8c8c8c" }}>
          IP: <span style={{ fontFamily: "monospace" }}>{client.ip_address}</span>
        </div>
      )}
    </div>
  );
}

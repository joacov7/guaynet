import { useState } from "react";
import { useNavigate, useOutletContext, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Spin, Tag, Typography, message } from "antd";
import dayjs from "dayjs";
import { workOrdersApi, clientsApi } from "@/services/api";
import type { User } from "@/types";

const { Text } = Typography;

const STATUS_COLOR: Record<string, string> = {
  pending: "blue",
  in_progress: "orange",
  completed: "green",
  cancelled: "default",
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

export default function TechWorkOrderDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { user } = useOutletContext<{ user: User }>();
  const [completionNotes, setCompletionNotes] = useState("");
  const [showNotes, setShowNotes] = useState(false);

  const { data: wo, isLoading, isError, refetch } = useQuery({
    queryKey: ["tech-work-order", id],
    queryFn: () => workOrdersApi.get(Number(id)),
    enabled: !!id,
    retry: 2,
  });

  const updateMutation = useMutation({
    mutationFn: ({ status, notes }: { status: string; notes?: string }) =>
      workOrdersApi.update(Number(id), { status, completion_notes: notes }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tech-work-order", id] });
      qc.invalidateQueries({ queryKey: ["tech-work-orders"] });
      setShowNotes(false);
      setCompletionNotes("");
      message.success("Estado actualizado");
    },
    onError: () => message.error("Error al actualizar"),
  });

  const { data: client } = useQuery({
    queryKey: ["client-brief", wo?.client_id],
    queryFn: () => clientsApi.get(wo!.client_id!),
    enabled: !!wo?.client_id,
    staleTime: 300_000,
  });

  if (isLoading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: 60 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (isError || !wo) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 60, gap: 12 }}>
        <div style={{ fontSize: 36 }}>⚠️</div>
        <Text type="secondary" style={{ textAlign: "center" }}>No se pudo cargar la orden.</Text>
        <div style={{ display: "flex", gap: 10 }}>
          <button onClick={() => refetch()} style={{ background: "#1677ff", color: "#fff", border: "none", borderRadius: 8, padding: "10px 20px", fontSize: 14, fontWeight: 600, cursor: "pointer" }}>
            Reintentar
          </button>
          <button onClick={() => navigate(-1)} style={{ background: "none", color: "#595959", border: "1px solid #d9d9d9", borderRadius: 8, padding: "10px 20px", fontSize: 14, cursor: "pointer" }}>
            Volver
          </button>
        </div>
      </div>
    );
  }

  function handleStart() {
    updateMutation.mutate({ status: "in_progress" });
  }

  function handleComplete() {
    if (showNotes) {
      updateMutation.mutate({ status: "completed", notes: completionNotes });
    } else {
      setShowNotes(true);
    }
  }

  return (
    <div style={{ padding: "0 0 80px" }}>
      {/* Header */}
      <div style={{
        background: "#fff", padding: "12px 16px", display: "flex", alignItems: "center",
        gap: 10, borderBottom: "1px solid #f0f0f0", position: "sticky", top: 0, zIndex: 10,
      }}>
        <button
          onClick={() => navigate(-1)}
          style={{ background: "none", border: "none", fontSize: 22, cursor: "pointer", padding: 0, lineHeight: 1 }}
        >
          ‹
        </button>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 15, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            #{wo.id} {wo.title}
          </div>
          <div style={{ display: "flex", gap: 6, marginTop: 2 }}>
            <Tag color={STATUS_COLOR[wo.status]} style={{ margin: 0, fontSize: 11 }}>
              {STATUS_LABEL[wo.status]}
            </Tag>
            <Tag style={{ margin: 0, fontSize: 11 }}>{TYPE_LABEL[wo.type] || wo.type}</Tag>
          </div>
        </div>
      </div>

      <div style={{ padding: "12px 14px" }}>
        {/* Action buttons */}
        {wo.status === "pending" && (
          <button
            onClick={handleStart}
            disabled={updateMutation.isPending}
            style={{
              width: "100%", background: "#fa8c16", color: "#fff", border: "none",
              borderRadius: 10, padding: "14px", fontSize: 15, fontWeight: 700,
              cursor: "pointer", marginBottom: 14, opacity: updateMutation.isPending ? 0.6 : 1,
            }}
          >
            ▶ Iniciar orden
          </button>
        )}

        {wo.status === "in_progress" && (
          <div style={{ marginBottom: 14 }}>
            {showNotes && (
              <textarea
                value={completionNotes}
                onChange={(e) => setCompletionNotes(e.target.value)}
                placeholder="Notas de cierre (opcional)..."
                rows={3}
                style={{
                  width: "100%", border: "1px solid #d9d9d9", borderRadius: 8,
                  padding: "8px 10px", fontSize: 14, resize: "none", fontFamily: "inherit",
                  outline: "none", marginBottom: 8, boxSizing: "border-box",
                }}
              />
            )}
            <button
              onClick={handleComplete}
              disabled={updateMutation.isPending}
              style={{
                width: "100%", background: "#52c41a", color: "#fff", border: "none",
                borderRadius: 10, padding: "14px", fontSize: 15, fontWeight: 700,
                cursor: "pointer", opacity: updateMutation.isPending ? 0.6 : 1,
              }}
            >
              ✅ {showNotes ? "Confirmar completado" : "Completar orden"}
            </button>
          </div>
        )}

        {/* Client info */}
        {wo.client_name && (
          <div style={{ background: "#fff", borderRadius: 12, padding: 14, marginBottom: 12, boxShadow: "0 1px 4px rgba(0,0,0,.06)" }}>
            <Text type="secondary" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 1 }}>Cliente</Text>
            <div style={{ fontWeight: 700, fontSize: 16, marginTop: 6, marginBottom: 8 }}>{wo.client_name}</div>
            {client?.phone && (
              <a
                href={`tel:${client.phone}`}
                style={{
                  display: "flex", alignItems: "center", gap: 10, background: "#f6ffed",
                  border: "1px solid #b7eb8f", borderRadius: 10, padding: "10px 14px",
                  textDecoration: "none", color: "#389e0d", fontWeight: 600, fontSize: 15,
                  marginBottom: 8, WebkitTapHighlightColor: "transparent",
                }}
              >
                <span style={{ fontSize: 20 }}>📞</span>{client.phone}
              </a>
            )}
          </div>
        )}

        {/* Address */}
        {wo.address && (
          <div style={{ background: "#fff", borderRadius: 12, padding: 14, marginBottom: 12, boxShadow: "0 1px 4px rgba(0,0,0,.06)" }}>
            <Text type="secondary" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 1, display: "block", marginBottom: 6 }}>Dirección</Text>
            <a
              href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(wo.address)}`}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: "flex", alignItems: "center", gap: 10, background: "#e6f4ff",
                border: "1px solid #91caff", borderRadius: 10, padding: "10px 14px",
                textDecoration: "none", color: "#0958d9", fontWeight: 500, fontSize: 14,
                WebkitTapHighlightColor: "transparent",
              }}
            >
              <span style={{ fontSize: 20 }}>📍</span>{wo.address}
            </a>
          </div>
        )}

        {/* Description */}
        {wo.description && (
          <div style={{ background: "#fff", borderRadius: 12, padding: 14, marginBottom: 12, boxShadow: "0 1px 4px rgba(0,0,0,.06)" }}>
            <Text type="secondary" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 1, display: "block", marginBottom: 6 }}>Descripción</Text>
            <Text style={{ fontSize: 14, lineHeight: 1.5 }}>{wo.description}</Text>
          </div>
        )}

        {/* Meta */}
        <div style={{ background: "#fff", borderRadius: 12, padding: 14, marginBottom: 12, boxShadow: "0 1px 4px rgba(0,0,0,.06)" }}>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <div>
              <Text type="secondary" style={{ fontSize: 11 }}>Programada</Text>
              <div style={{ fontWeight: 600, fontSize: 14 }}>
                {wo.scheduled_date ? dayjs(wo.scheduled_date).format("DD/MM/YY HH:mm") : "Sin fecha"}
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <Text type="secondary" style={{ fontSize: 11 }}>Creada</Text>
              <div style={{ fontWeight: 600, fontSize: 14 }}>{dayjs(wo.created_at).format("DD/MM/YY HH:mm")}</div>
            </div>
          </div>
        </div>

        {/* Completion notes */}
        {wo.completion_notes && (
          <div style={{ background: "#f6ffed", border: "1px solid #b7eb8f", borderRadius: 12, padding: 14, marginBottom: 12 }}>
            <Text type="secondary" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 1, display: "block", marginBottom: 6 }}>Notas de cierre</Text>
            <Text style={{ fontSize: 14 }}>{wo.completion_notes}</Text>
          </div>
        )}
      </div>
    </div>
  );
}

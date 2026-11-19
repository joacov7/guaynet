import { useOutletContext } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Card, Col, Row, Statistic, Tag, Typography } from "antd";
import dayjs from "dayjs";
import { portalApi } from "@/services/api";
import type { PortalClient } from "./PortalLayout";

const STATUS_COLOR: Record<string, string> = { active: "green", suspended: "orange", cancelled: "red" };
const STATUS_LABEL: Record<string, string> = { active: "Activo", suspended: "Suspendido", cancelled: "Cancelado" };
const INV_COLOR: Record<string, string> = { pending: "blue", paid: "green", overdue: "red", cancelled: "default", draft: "default" };
const INV_LABEL: Record<string, string> = { pending: "Pendiente", paid: "Pagada", overdue: "Vencida", cancelled: "Cancelada", draft: "Borrador" };

export default function PortalDashboard() {
  const { client } = useOutletContext<{ client: PortalClient }>();

  const { data: invoices = [] } = useQuery({
    queryKey: ["portal-invoices"],
    queryFn: portalApi.getInvoices,
  });

  const pendingInvoices = invoices.filter((i: any) => i.status === "pending" || i.status === "overdue");
  const lastInvoice = invoices[0];

  return (
    <div style={{ padding: 16 }}>
      {/* Welcome */}
      <div style={{ background: "#fff", borderRadius: 12, padding: 16, marginBottom: 12, boxShadow: "0 1px 4px rgba(0,0,0,.06)" }}>
        <Typography.Text type="secondary" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 1 }}>Bienvenido</Typography.Text>
        <div style={{ fontSize: 20, fontWeight: 700, marginTop: 2 }}>{client.full_name}</div>
        <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
          <Tag color={STATUS_COLOR[client.status]}>{STATUS_LABEL[client.status]}</Tag>
          {client.plan_name && <Tag color="blue">{client.plan_name}</Tag>}
        </div>
      </div>

      {/* Stats */}
      <Row gutter={10} style={{ marginBottom: 12 }}>
        <Col span={12}>
          <Card size="small" style={{ borderRadius: 10 }}>
            <Statistic
              title="Facturas pendientes"
              value={pendingInvoices.length}
              valueStyle={{ color: pendingInvoices.length > 0 ? "#ff4d4f" : "#52c41a" }}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card size="small" style={{ borderRadius: 10 }}>
            <Statistic title="Total de facturas" value={invoices.length} />
          </Card>
        </Col>
      </Row>

      {/* Service info */}
      <div style={{ background: "#fff", borderRadius: 12, padding: 14, marginBottom: 12, boxShadow: "0 1px 4px rgba(0,0,0,.06)" }}>
        <Typography.Text type="secondary" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 1, display: "block", marginBottom: 8 }}>
          Datos del servicio
        </Typography.Text>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px 0" }}>
          {client.ip_address && (
            <>
              <Typography.Text type="secondary" style={{ fontSize: 13 }}>IP asignada</Typography.Text>
              <Typography.Text strong style={{ fontSize: 13, fontFamily: "monospace" }}>{client.ip_address}</Typography.Text>
            </>
          )}
          {client.plan_name && (
            <>
              <Typography.Text type="secondary" style={{ fontSize: 13 }}>Plan</Typography.Text>
              <Typography.Text strong style={{ fontSize: 13 }}>{client.plan_name}</Typography.Text>
            </>
          )}
          {client.address && (
            <>
              <Typography.Text type="secondary" style={{ fontSize: 13 }}>Dirección</Typography.Text>
              <Typography.Text strong style={{ fontSize: 13 }}>{client.address}</Typography.Text>
            </>
          )}
          {client.phone && (
            <>
              <Typography.Text type="secondary" style={{ fontSize: 13 }}>Teléfono</Typography.Text>
              <a href={`tel:${client.phone}`} style={{ fontSize: 13 }}>{client.phone}</a>
            </>
          )}
        </div>
      </div>

      {/* Last invoice */}
      {lastInvoice && (
        <div style={{ background: "#fff", borderRadius: 12, padding: 14, boxShadow: "0 1px 4px rgba(0,0,0,.06)" }}>
          <Typography.Text type="secondary" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 1, display: "block", marginBottom: 8 }}>
            Última factura
          </Typography.Text>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <div style={{ fontSize: 22, fontWeight: 700 }}>${Number(lastInvoice.amount).toFixed(2)}</div>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                Vence: {lastInvoice.due_date ? dayjs(lastInvoice.due_date).format("DD/MM/YYYY") : "—"}
              </Typography.Text>
            </div>
            <Tag color={INV_COLOR[lastInvoice.status]}>{INV_LABEL[lastInvoice.status]}</Tag>
          </div>
        </div>
      )}
    </div>
  );
}

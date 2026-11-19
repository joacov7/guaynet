import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button, Spin, Space, Tag, Typography, message } from "antd";
import dayjs from "dayjs";
import { portalApi } from "@/services/api";

const STATUS_COLOR: Record<string, string> = { pending: "blue", paid: "green", overdue: "red", cancelled: "default", draft: "default" };
const STATUS_LABEL: Record<string, string> = { pending: "Pendiente", paid: "Pagada", overdue: "Vencida", cancelled: "Cancelada", draft: "Borrador" };

export default function PortalInvoices() {
  const [payingId, setPayingId] = useState<number | null>(null);
  const [downloadingId, setDownloadingId] = useState<number | null>(null);

  const { data: invoices = [], isLoading, isError } = useQuery({
    queryKey: ["portal-invoices"],
    queryFn: portalApi.getInvoices,
    retry: 2,
  });

  async function handlePay(invoiceId: number) {
    setPayingId(invoiceId);
    try {
      const pref = await portalApi.getMpPreference(invoiceId);
      window.location.href = pref.init_point;
    } catch {
      message.error("No se pudo iniciar el pago. Intentá más tarde.");
    } finally {
      setPayingId(null);
    }
  }

  async function handleDownloadPdf(invoiceId: number) {
    setDownloadingId(invoiceId);
    try {
      await portalApi.downloadInvoicePdf(invoiceId);
    } catch {
      message.error("No se pudo descargar el PDF.");
    } finally {
      setDownloadingId(null);
    }
  }

  if (isLoading) return (
    <div style={{ display: "flex", justifyContent: "center", padding: 60 }}>
      <Spin size="large" />
    </div>
  );

  if (isError) return (
    <div style={{ textAlign: "center", padding: 60 }}>
      <Typography.Text type="secondary">No se pudieron cargar las facturas.</Typography.Text>
    </div>
  );

  return (
    <div style={{ padding: 16 }}>
      <Typography.Text strong style={{ fontSize: 15, display: "block", marginBottom: 12 }}>
        Historial de facturas ({invoices.length})
      </Typography.Text>

      {invoices.length === 0 && (
        <div style={{ textAlign: "center", padding: 40 }}>
          <Typography.Text type="secondary">No tenés facturas todavía.</Typography.Text>
        </div>
      )}

      {invoices.map((inv: any) => (
        <div
          key={inv.id}
          style={{
            background: "#fff",
            borderRadius: 12,
            padding: 14,
            marginBottom: 10,
            boxShadow: "0 1px 4px rgba(0,0,0,.06)",
            borderLeft: `4px solid ${inv.status === "overdue" ? "#ff4d4f" : inv.status === "paid" ? "#52c41a" : "#1677ff"}`,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 18 }}>${Number(inv.amount).toFixed(2)}</div>
              {inv.period && (
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  Período: {inv.period}
                </Typography.Text>
              )}
            </div>
            <Tag color={STATUS_COLOR[inv.status]}>{STATUS_LABEL[inv.status]}</Tag>
          </div>
          <div style={{ marginTop: 6, fontSize: 12, color: "#8c8c8c", display: "flex", gap: 16 }}>
            {inv.due_date && <span>Vence: {dayjs(inv.due_date).format("DD/MM/YYYY")}</span>}
            {inv.paid_date && <span>Pagado: {dayjs(inv.paid_date).format("DD/MM/YYYY")}</span>}
          </div>
          <div style={{ marginTop: 10, display: "flex", gap: 8 }}>
            {(inv.status === "pending" || inv.status === "overdue") && (
              <Button
                type="primary"
                size="small"
                loading={payingId === inv.id}
                onClick={() => handlePay(inv.id)}
              >
                💳 Pagar
              </Button>
            )}
            <Button
              size="small"
              loading={downloadingId === inv.id}
              onClick={() => handleDownloadPdf(inv.id)}
            >
              📄 PDF
            </Button>
          </div>
        </div>
      ))}
      <div style={{ height: 16 }} />
    </div>
  );
}

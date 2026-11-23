import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Col, DatePicker, Form, Input, InputNumber, Modal, Row, Select, Space, Typography, message } from "antd";
import dayjs from "dayjs";
import { accountApi, clientsApi, invoicesApi, type CollectResult } from "@/services/api";
import ClientSelect from "@/components/common/ClientSelect";
import type { Invoice } from "@/types";

const { Text } = Typography;

export const METHODS: Record<string, string> = {
  cash: "Efectivo",
  transfer: "Transferencia",
  mercadopago: "MercadoPago",
  other: "Otro",
};
export const money = (n: number) => n.toLocaleString("es-AR", { style: "currency", currency: "ARS" });
export const validPaid = (inv: Invoice) =>
  inv.payments.filter((p) => !p.voided_at).reduce((sum, p) => sum + Number(p.amount), 0);
const unpaid = (inv: Invoice) => inv.status === "pending" || inv.status === "overdue";

/** What the cobro did, in words, for the success message. */
export function describeCobro(r: CollectResult) {
  const parts = r.applied.map((a) => `${a.period} (${money(a.amount)})`);
  let text = parts.length ? `Aplicado a ${parts.join(", ")}` : "Sin facturas para pagar";
  if (r.to_credit > 0) text += `; quedan ${money(r.to_credit)} a favor`;
  if (r.reactivated) text += ". Servicio reactivado";
  return text;
}

/**
 * Registrar un cobro. With `clientId` it is for that client (ficha); without it the
 * person picks the client (Cobros). The cobro pays the chosen invoice first, then
 * the oldest ones, and leaves the rest as saldo a favor.
 */
export default function CollectModal({ open, clientId, invoiceId, onClose }: {
  open: boolean;
  clientId?: number;
  invoiceId?: number;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [form] = Form.useForm();
  const [picked, setPicked] = useState<number | undefined>(clientId);
  const cid = clientId ?? picked;

  const { data: summary } = useQuery({
    queryKey: ["client-summary", cid],
    queryFn: () => clientsApi.summary(cid!),
    enabled: open && !!cid,
  });
  const { data: page } = useQuery({
    queryKey: ["invoices", { client: cid, page: 1, pageSize: 100 }],
    queryFn: () => invoicesApi.listPage({ client_id: cid!, skip: 0, limit: 100 }),
    enabled: open && !!cid,
  });
  const owed = useMemo(
    () => (page?.items ?? []).filter(unpaid).sort((a, b) => a.due_date.localeCompare(b.due_date)),
    [page],
  );

  useEffect(() => {
    if (!open) return;
    setPicked(clientId);
    form.resetFields();
    form.setFieldsValue({ payment_date: dayjs(), method: "cash", invoice_id: invoiceId ?? "auto" });
  }, [open, clientId, invoiceId, form]);

  // Proposed amount: what the chosen invoice still needs, or all the debt
  const target = Form.useWatch("invoice_id", form);
  useEffect(() => {
    if (!open || !cid) return;
    const inv = owed.find((i) => i.id === target);
    const amount = inv ? Number(inv.amount) - validPaid(inv) : Math.max(0, summary?.balance ?? 0);
    form.setFieldValue("amount", amount > 0 ? Math.round(amount * 100) / 100 : undefined);
  }, [target, owed, summary, open, cid, form]);

  const save = useMutation({
    mutationFn: (v: any) =>
      accountApi.collect(cid!, {
        amount: v.amount,
        method: v.method,
        payment_date: v.payment_date.format("YYYY-MM-DD"),
        reference: v.reference || undefined,
        notes: v.notes || undefined,
        invoice_id: v.invoice_id === "auto" ? undefined : v.invoice_id,
      }),
    onSuccess: (r) => {
      ["invoices", "client", "client-summary", "client-history", "statement", "cobros", "clients", "attention"].forEach((k) =>
        qc.invalidateQueries({ queryKey: [k] }),
      );
      message.success(`Cobro registrado. ${describeCobro(r)}`, 6);
      if (r.reactivated && r.router_ok === false) {
        message.warning(`MikroTik: ${r.router_message}`, 8);
      }
      onClose();
    },
    onError: (e: any) => {
      message.error(e?.response?.data?.detail ?? "No se pudo registrar el cobro");
    },
  });

  const balance = summary?.balance ?? null;

  return (
    <Modal
      open={open}
      title="Registrar cobro"
      okText="Registrar"
      cancelText="Cancelar"
      onCancel={onClose}
      onOk={() => form.submit()}
      confirmLoading={save.isPending}
      okButtonProps={{ disabled: !cid }}
      destroyOnClose
    >
      <Form form={form} layout="vertical" onFinish={(v) => save.mutate(v)}>
        {!clientId && (
          <Form.Item label="Cliente" required>
            <ClientSelect value={picked} onChange={(v) => setPicked(v as number | undefined)} />
          </Form.Item>
        )}
        {cid && balance !== null && (
          <Alert
            style={{ marginBottom: 16 }}
            type={balance > 0 ? "warning" : "success"}
            showIcon
            message={
              balance > 0
                ? `Debe ${money(balance)} en ${summary?.unpaid_count ?? 0} factura(s)`
                : balance < 0
                  ? `Tiene ${money(-balance)} a favor`
                  : "Está al día"
            }
          />
        )}
        <Form.Item name="invoice_id" label="Aplicar a">
          <Select
            options={[
              { value: "auto", label: "Automático: primero las facturas más viejas" },
              ...owed.map((i) => ({
                value: i.id,
                label: `${i.period} · vence ${dayjs(i.due_date).format("DD/MM/YYYY")} · resta ${money(Number(i.amount) - validPaid(i))}`,
              })),
            ]}
          />
        </Form.Item>
        <Row gutter={12}>
          <Col span={12}>
            <Form.Item name="amount" label="Monto" rules={[{ required: true, message: "Poné el monto" }]}>
              <InputNumber min={0.01} step={100} style={{ width: "100%" }} prefix="$" />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="payment_date" label="Fecha" rules={[{ required: true }]}>
              <DatePicker format="DD/MM/YYYY" style={{ width: "100%" }} disabledDate={(d) => d.isAfter(dayjs().add(1, "day"))} />
            </Form.Item>
          </Col>
        </Row>
        <Row gutter={12}>
          <Col span={12}>
            <Form.Item name="method" label="Medio" rules={[{ required: true }]}>
              <Select options={Object.entries(METHODS).map(([value, label]) => ({ value, label }))} />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="reference" label="Referencia (opcional)">
              <Input placeholder="N° de operación, recibo…" maxLength={255} />
            </Form.Item>
          </Col>
        </Row>
        <Form.Item name="notes" label="Nota (opcional)">
          <Input.TextArea rows={2} maxLength={2000} />
        </Form.Item>
        <Space direction="vertical" size={0}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Si pagás más de lo que se debe, el resto queda a favor y se usa en las próximas facturas.
          </Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Si con el cobro no le quedan facturas vencidas y estaba cortado, se reconecta solo.
          </Text>
        </Space>
      </Form>
    </Modal>
  );
}

/** Anular un cobro (all its parts). The service is not cut by this. */
export function VoidCobroModal({ paymentId, total, onClose }: { paymentId: number | null; total?: number; onClose: () => void }) {
  const qc = useQueryClient();
  const [reason, setReason] = useState("");
  useEffect(() => setReason(""), [paymentId]);
  const run = useMutation({
    mutationFn: () => accountApi.void(paymentId!, reason.trim()),
    onSuccess: (r) => {
      ["invoices", "client", "client-summary", "client-history", "statement", "cobros", "clients", "attention"].forEach((k) =>
        qc.invalidateQueries({ queryKey: [k] }),
      );
      message.success(`Cobro de ${money(r.total)} anulado`);
      onClose();
    },
    onError: (e: any) => {
      message.error(e?.response?.data?.detail ?? "No se pudo anular");
    },
  });
  return (
    <Modal
      open={paymentId !== null}
      title={`Anular cobro${total ? ` de ${money(total)}` : ""}`}
      okText="Anular cobro"
      okButtonProps={{ danger: true, disabled: reason.trim().length < 3 }}
      cancelText="Cancelar"
      onCancel={onClose}
      onOk={() => run.mutate()}
      confirmLoading={run.isPending}
      destroyOnClose
    >
      <Alert
        type="warning"
        showIcon
        style={{ marginBottom: 12 }}
        message="Las facturas que pagaba vuelven a quedar impagas."
        description="El cobro queda registrado como anulado, con tu nombre y el motivo. No se corta el servicio desde acá: el corte automático decide con sus reglas."
      />
      <Input.TextArea
        rows={3}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder="Motivo (obligatorio). Ej: transferencia rebotada, cargado dos veces"
        maxLength={500}
        autoFocus
      />
    </Modal>
  );
}

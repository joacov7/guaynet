import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  DatePicker,
  Drawer,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import {
  CheckCircleOutlined,
  DownloadOutlined,
  FileTextOutlined,
  PauseCircleOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";
import { invoicesApi } from "@/services/api";
import type { Invoice, InvoiceStatus, OverdueEntry } from "@/types";

const { Title } = Typography;

const statusConfig: Record<InvoiceStatus, { color: string; label: string }> = {
  draft: { color: "default", label: "Borrador" },
  pending: { color: "blue", label: "Pendiente" },
  paid: { color: "green", label: "Pagada" },
  overdue: { color: "red", label: "Vencida" },
  cancelled: { color: "default", label: "Cancelada" },
};

const methodLabel: Record<string, string> = {
  cash: "Efectivo",
  transfer: "Transferencia",
  mercadopago: "MercadoPago",
  other: "Otro",
};

export default function Invoices() {
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<InvoiceStatus | undefined>();
  const [payModal, setPayModal] = useState<Invoice | null>(null);
  const [payForm] = Form.useForm();
  const [overdueDrawer, setOverdueDrawer] = useState(false);

  const { data = [], isLoading } = useQuery({
    queryKey: ["invoices", { status: statusFilter }],
    queryFn: () => invoicesApi.list({ status: statusFilter }),
  });

  const markOverdueMutation = useMutation({
    mutationFn: invoicesApi.markOverdue,
    onSuccess: (res: any) => {
      qc.invalidateQueries({ queryKey: ["invoices"] });
      message.success(`${res.updated} facturas marcadas como vencidas`);
    },
  });

  const triggerSuspendMutation = useMutation({
    mutationFn: invoicesApi.triggerSuspend,
    onSuccess: () => message.success("Tarea de auto-suspensión enviada a la cola"),
    onError: () => message.error("Error al lanzar tarea"),
  });

  const triggerGenerateMutation = useMutation({
    mutationFn: invoicesApi.triggerGenerate,
    onSuccess: () => message.success("Generación de facturas enviada a la cola"),
    onError: () => message.error("Error al lanzar tarea"),
  });

  const { data: overdueData, isLoading: overdueLoading } = useQuery({
    queryKey: ["overdue-report"],
    queryFn: () => invoicesApi.overdueReport(0),
    enabled: overdueDrawer,
  });

  const addPaymentMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: any }) => invoicesApi.addPayment(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["invoices"] });
      message.success("Pago registrado");
      setPayModal(null);
      payForm.resetFields();
    },
    onError: () => message.error("Error al registrar pago"),
  });

  const formatARS = (v: number) =>
    new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS" }).format(v);

  const columns = [
    { title: "ID", dataIndex: "id", key: "id", width: 60 },
    { title: "Período", dataIndex: "period", key: "period" },
    {
      title: "Monto",
      dataIndex: "amount",
      key: "amount",
      render: (v: number) => formatARS(v),
    },
    {
      title: "Vencimiento",
      dataIndex: "due_date",
      key: "due_date",
      render: (v: string) => dayjs(v).format("DD/MM/YYYY"),
    },
    {
      title: "Estado",
      dataIndex: "status",
      key: "status",
      render: (s: InvoiceStatus) => (
        <Tag color={statusConfig[s].color}>{statusConfig[s].label}</Tag>
      ),
    },
    {
      title: "",
      key: "actions",
      align: "right" as const,
      render: (_: unknown, r: Invoice) =>
        r.status !== "paid" && r.status !== "cancelled" ? (
          <Button
            size="small"
            type="primary"
            icon={<CheckCircleOutlined />}
            onClick={() => {
              setPayModal(r);
              payForm.setFieldsValue({ payment_date: dayjs(), amount: r.amount, method: "cash" });
            }}
          >
            Registrar pago
          </Button>
        ) : null,
    },
  ];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>Facturación</Title>
        <Space wrap>
          <Tooltip title="Ver reporte de morosidad y exportar CSV">
            <Button icon={<FileTextOutlined />} onClick={() => setOverdueDrawer(true)}>
              Reporte de morosidad
            </Button>
          </Tooltip>
          <Popconfirm
            title="¿Marcar como vencidas todas las facturas pendientes pasadas de fecha?"
            onConfirm={() => markOverdueMutation.mutate()}
          >
            <Button icon={<WarningOutlined />}>Marcar vencidas</Button>
          </Popconfirm>
          <Popconfirm
            title="¿Generar facturas del mes para todos los clientes activos?"
            onConfirm={() => triggerGenerateMutation.mutate()}
          >
            <Button icon={<FileTextOutlined />} loading={triggerGenerateMutation.isPending}>
              Generar facturas
            </Button>
          </Popconfirm>
          <Popconfirm
            title="¿Ejecutar auto-suspensión? Se suspenderán clientes con facturas vencidas hace más de 3 días."
            onConfirm={() => triggerSuspendMutation.mutate()}
          >
            <Button icon={<PauseCircleOutlined />} danger loading={triggerSuspendMutation.isPending}>
              Auto-suspender
            </Button>
          </Popconfirm>
        </Space>
      </div>

      <Space style={{ marginBottom: 16 }}>
        <Select
          placeholder="Filtrar por estado"
          style={{ width: 160 }}
          allowClear
          value={statusFilter}
          onChange={setStatusFilter}
          options={Object.entries(statusConfig).map(([k, v]) => ({ value: k, label: v.label }))}
        />
      </Space>

      <Table
        loading={isLoading}
        dataSource={data}
        rowKey="id"
        columns={columns}
        size="small"
        pagination={{ pageSize: 50, showTotal: (t) => `${t} facturas` }}
        expandable={{
          expandedRowRender: (r: Invoice) =>
            r.payments.length > 0 ? (
              <div style={{ paddingLeft: 24 }}>
                {r.payments.map((p) => (
                  <div key={p.id} style={{ marginBottom: 4, fontSize: 13 }}>
                    {dayjs(p.payment_date).format("DD/MM/YYYY")} — {formatARS(p.amount)} —{" "}
                    {methodLabel[p.method] ?? p.method}
                    {p.reference ? ` — Ref: ${p.reference}` : ""}
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ paddingLeft: 24, color: "#999" }}>Sin pagos registrados</div>
            ),
        }}
      />

      <Drawer
        title="Reporte de morosidad"
        open={overdueDrawer}
        onClose={() => setOverdueDrawer(false)}
        width={800}
        extra={
          <Button
            icon={<DownloadOutlined />}
            onClick={() => invoicesApi.overdueReportCsv(0)}
          >
            Exportar CSV
          </Button>
        }
      >
        {overdueData && (
          <Space style={{ marginBottom: 16 }}>
            <Statistic title="Facturas vencidas" value={overdueData.total} />
            <Statistic
              title="Monto total"
              value={overdueData.total_amount}
              prefix="$"
              precision={2}
            />
          </Space>
        )}
        <Table
          loading={overdueLoading}
          dataSource={overdueData?.items ?? []}
          rowKey="invoice_id"
          size="small"
          pagination={{ pageSize: 25 }}
          columns={[
            {
              title: "Cliente",
              dataIndex: "client_name",
              key: "client_name",
            },
            { title: "Teléfono", dataIndex: "phone", key: "phone", render: (v: string) => v || "—" },
            { title: "Período", dataIndex: "period", key: "period" },
            {
              title: "Monto",
              dataIndex: "amount",
              key: "amount",
              render: (v: number) => formatARS(v),
            },
            {
              title: "Vencimiento",
              dataIndex: "due_date",
              key: "due_date",
              render: (v: string) => dayjs(v).format("DD/MM/YYYY"),
            },
            {
              title: "Días vencido",
              dataIndex: "days_overdue",
              key: "days_overdue",
              render: (v: number) => (
                <Tag color={v > 30 ? "red" : v > 15 ? "orange" : "gold"}>{v} días</Tag>
              ),
            },
          ]}
        />
      </Drawer>

      <Modal
        title="Registrar pago"
        open={payModal != null}
        onCancel={() => { setPayModal(null); payForm.resetFields(); }}
        onOk={() => payForm.submit()}
        confirmLoading={addPaymentMutation.isPending}
      >
        <Form form={payForm} layout="vertical" onFinish={(v) => addPaymentMutation.mutate({
          id: payModal!.id,
          data: { ...v, payment_date: v.payment_date.format("YYYY-MM-DD") },
        })}>
          <Form.Item name="amount" label="Monto" rules={[{ required: true }]}>
            <InputNumber min={0} precision={2} style={{ width: "100%" }} prefix="$" />
          </Form.Item>
          <Form.Item name="payment_date" label="Fecha de pago" rules={[{ required: true }]}>
            <DatePicker style={{ width: "100%" }} format="DD/MM/YYYY" />
          </Form.Item>
          <Form.Item name="method" label="Método" rules={[{ required: true }]}>
            <Select options={Object.entries(methodLabel).map(([k, v]) => ({ value: k, label: v }))} />
          </Form.Item>
          <Form.Item name="reference" label="Referencia / N° transferencia">
            <Input />
          </Form.Item>
          <Form.Item name="notes" label="Notas">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

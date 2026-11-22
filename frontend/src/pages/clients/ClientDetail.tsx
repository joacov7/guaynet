import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Col,
  DatePicker,
  Descriptions,
  Dropdown,
  Empty,
  Form,
  Input,
  InputNumber,
  List,
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Spin,
  Statistic,
  Table,
  Tabs,
  Tag,
  Timeline,
  Tooltip,
  Typography,
  message,
} from "antd";
import {
  ArrowLeftOutlined,
  DollarOutlined,
  EditOutlined,
  EnvironmentOutlined,
  FilePdfOutlined,
  LinkOutlined,
  MoreOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
  StopOutlined,
  SyncOutlined,
  ToolOutlined,
  WhatsAppOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";
import { MapContainer, Marker, TileLayer } from "react-leaflet";
import { clientsApi, invoicesApi, plansApi, ticketsApi, workOrdersApi } from "@/services/api";
import { usePermissions } from "@/contexts/PermissionsContext";
import type { ClientStatus, Invoice, InvoiceStatus, PaymentMethod, TicketCategory, TicketPriority } from "@/types";

const { Title, Text, Paragraph } = Typography;

const pin = new L.Icon({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});

const STATUS: Record<ClientStatus, { color: string; label: string }> = {
  active: { color: "green", label: "Activo" },
  suspended: { color: "orange", label: "Cortado" },
  cancelled: { color: "red", label: "Dado de baja" },
};
const INVOICE_STATUS: Record<InvoiceStatus, { color: string; label: string }> = {
  draft: { color: "default", label: "Borrador" },
  pending: { color: "blue", label: "Pendiente" },
  paid: { color: "green", label: "Pagada" },
  overdue: { color: "red", label: "Vencida" },
  cancelled: { color: "default", label: "Anulada" },
};
const METHODS: Record<PaymentMethod, string> = {
  cash: "Efectivo",
  transfer: "Transferencia",
  mercadopago: "MercadoPago",
  other: "Otro",
};
const TICKET_STATUS: Record<string, { color: string; label: string }> = {
  open: { color: "red", label: "Abierto" },
  in_progress: { color: "blue", label: "En curso" },
  resolved: { color: "green", label: "Resuelto" },
  closed: { color: "default", label: "Cerrado" },
};
const WO_STATUS: Record<string, { color: string; label: string }> = {
  pending: { color: "gold", label: "Pendiente" },
  in_progress: { color: "blue", label: "En curso" },
  completed: { color: "green", label: "Completada" },
  cancelled: { color: "default", label: "Cancelada" },
};
const CATEGORIES: Record<TicketCategory, string> = {
  connectivity: "Sin conexión",
  speed: "Velocidad",
  billing: "Facturación",
  equipment: "Equipo",
  installation: "Instalación",
  other: "Otro",
};
const PRIORITIES: Record<TicketPriority, string> = { low: "Baja", medium: "Media", high: "Alta" };
const ACTIONS: Record<string, string> = {
  create: "Alta",
  update: "Edición",
  suspend: "Corte",
  activate: "Reactivación",
  cancel: "Baja",
  delete: "Eliminado",
  plan_change: "Cambio de plan",
  replace_device: "Cambio de equipo",
};

const money = (n: number) => n.toLocaleString("es-AR", { style: "currency", currency: "ARS" });
const day = (d?: string | null) => (d ? dayjs(d).format("DD/MM/YYYY") : "—");
const when = (d?: string | null) => (d ? dayjs(d).format("DD/MM/YYYY HH:mm") : "—");
const paidOf = (inv: Invoice) => inv.payments.reduce((sum, p) => sum + Number(p.amount), 0);
const isUnpaid = (inv: Invoice) => inv.status === "pending" || inv.status === "overdue";
const apiError = (e: any, fallback: string) => e?.response?.data?.detail ?? fallback;

export default function ClientDetail() {
  const { id } = useParams<{ id: string }>();
  const clientId = Number(id);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { canEdit, canView, isAdmin } = usePermissions();
  const can = {
    edit: canEdit("clients"),
    cut: canEdit("clients") && canView("act_client_service"),
    pay: canEdit("billing") && canView("act_payments"),
    bill: canEdit("billing"),
    ticket: canEdit("tickets"),
    order: canEdit("work_orders"),
    seeBilling: isAdmin || canView("billing"),
  };

  const [modal, setModal] = useState<null | "pay" | "plan" | "ticket" | "order" | "link">(null);
  const [payInvoice, setPayInvoice] = useState<Invoice | null>(null);
  const [link, setLink] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [payForm] = Form.useForm();
  const [planForm] = Form.useForm();
  const [ticketForm] = Form.useForm();
  const [orderForm] = Form.useForm();

  const { data: client, isLoading, error } = useQuery({
    queryKey: ["client", clientId],
    queryFn: () => clientsApi.get(clientId),
  });
  const { data: summary } = useQuery({
    queryKey: ["client-summary", clientId],
    queryFn: () => clientsApi.summary(clientId),
  });
  const { data: conn, isFetching: connLoading, refetch: refreshConn } = useQuery({
    queryKey: ["client-connection", clientId],
    queryFn: () => clientsApi.connection(clientId),
    staleTime: 60_000,
  });
  const { data: invoicePage } = useQuery({
    queryKey: ["invoices", { client: clientId, page: 1, pageSize: 100 }],
    queryFn: () => invoicesApi.listPage({ client_id: clientId, skip: 0, limit: 100 }),
    enabled: can.seeBilling,
  });
  const invoices = invoicePage?.items ?? [];
  const unpaid = useMemo(
    () => invoices.filter(isUnpaid).sort((a, b) => a.due_date.localeCompare(b.due_date)),
    [invoices],
  );

  const refresh = () => {
    ["client", "client-summary", "client-history", "invoices", "clients"].forEach((k) =>
      qc.invalidateQueries({ queryKey: [k] }),
    );
  };
  const routerResult = (data: { mikrotik_error?: string; mikrotik_sync?: string }, ok: string) => {
    if (data.mikrotik_error) message.warning(`${ok}. MikroTik: ${data.mikrotik_error}`, 8);
    else message.success(`${ok}${data.mikrotik_sync ? ` · MikroTik: ${data.mikrotik_sync}` : ""}`);
  };

  const cut = useMutation({
    mutationFn: () => clientsApi.suspend(clientId),
    onSuccess: (d) => {
      refresh();
      routerResult(d, "Servicio cortado");
    },
    onError: (e) => {
      message.error(apiError(e, "No se pudo cortar"));
    },
  });
  const reactivate = useMutation({
    mutationFn: () => clientsApi.activate(clientId),
    onSuccess: (d) => {
      refresh();
      routerResult(d, "Servicio reactivado");
    },
    onError: (e) => {
      message.error(apiError(e, "No se pudo reactivar"));
    },
  });
  const cancel = useMutation({
    mutationFn: () => clientsApi.cancel(clientId),
    onSuccess: () => {
      refresh();
      message.success("Cliente dado de baja");
    },
    onError: (e) => {
      message.error(apiError(e, "No se pudo dar de baja"));
    },
  });
  const sync = useMutation({
    mutationFn: () => clientsApi.syncMikrotik(clientId),
    onSuccess: (d: any) => {
      message.success(`Aplicado en el MikroTik: ${d.message}`);
    },
    onError: (e) => {
      message.error(apiError(e, "No se pudo sincronizar"), 8);
    },
  });
  const pay = useMutation({
    mutationFn: (v: any) =>
      invoicesApi.addPayment(v.invoice_id, {
        amount: v.amount,
        payment_date: v.payment_date.format("YYYY-MM-DD"),
        method: v.method,
        reference: v.reference || undefined,
      }),
    onSuccess: () => {
      refresh();
      setModal(null);
      message.success("Pago registrado");
    },
    onError: (e) => {
      message.error(apiError(e, "No se pudo registrar el pago"));
    },
  });
  const changePlan = useMutation({
    mutationFn: (planId: number) => clientsApi.update(clientId, { plan_id: planId }),
    onSuccess: (d) => {
      refresh();
      setModal(null);
      routerResult(d, "Plan cambiado");
    },
    onError: (e) => {
      message.error(apiError(e, "No se pudo cambiar el plan"));
    },
  });
  const newTicket = useMutation({
    mutationFn: (v: any) => ticketsApi.create({ ...v, client_id: clientId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["client-tickets", clientId] });
      qc.invalidateQueries({ queryKey: ["client-summary", clientId] });
      setModal(null);
      message.success("Ticket creado");
    },
    onError: (e) => {
      message.error(apiError(e, "No se pudo crear el ticket"));
    },
  });
  const newOrder = useMutation({
    mutationFn: (v: any) =>
      workOrdersApi.create({
        ...v,
        scheduled_date: v.scheduled_date ? v.scheduled_date.toISOString() : undefined,
        client_id: clientId,
        address: client?.address,
        latitude: client?.latitude,
        longitude: client?.longitude,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["client-orders", clientId] });
      qc.invalidateQueries({ queryKey: ["client-summary", clientId] });
      setModal(null);
      message.success("Orden de trabajo creada");
    },
    onError: (e) => {
      message.error(apiError(e, "No se pudo crear la orden"));
    },
  });
  const makeLink = useMutation({
    mutationFn: (invoiceId: number) => invoicesApi.mpLink(invoiceId),
    onSuccess: (d) => {
      setLink(d.init_point);
      setModal("link");
    },
    onError: (e) => {
      message.error(apiError(e, "No se pudo generar el link de pago"));
    },
  });
  const addNote = useMutation({
    mutationFn: () => clientsApi.addNote(clientId, note),
    onSuccess: () => {
      setNote("");
      qc.invalidateQueries({ queryKey: ["client-notes", clientId] });
    },
    onError: (e) => {
      message.error(apiError(e, "No se pudo guardar la nota"));
    },
  });

  const openPay = (inv?: Invoice) => {
    const target = inv ?? unpaid[0];
    if (!target) {
      message.info("El cliente no tiene facturas impagas");
      return;
    }
    setPayInvoice(target);
    payForm.setFieldsValue({
      invoice_id: target.id,
      amount: Math.max(0, Number(target.amount) - paidOf(target)),
      payment_date: dayjs(),
      method: "cash",
      reference: "",
    });
    setModal("pay");
  };

  if (isLoading) return <Spin style={{ margin: 40 }} />;
  if (error || !client) return <Alert type="error" showIcon message="No se encontró el cliente" />;

  const status = STATUS[client.status];
  const phoneDigits = (client.phone ?? "").replace(/[^0-9]/g, "");
  const whatsapp = (text = "") =>
    `https://wa.me/${phoneDigits}${text ? `?text=${encodeURIComponent(text)}` : ""}`;

  const moreItems = [
    can.edit && { key: "edit", icon: <EditOutlined />, label: "Editar datos", onClick: () => navigate(`/clients/${clientId}/edit`) },
    can.cut && { key: "sync", icon: <SyncOutlined />, label: "Volver a aplicar en el MikroTik", onClick: () => sync.mutate() },
    can.cut && client.status !== "cancelled" && {
      key: "cancel",
      icon: <StopOutlined />,
      danger: true,
      label: "Dar de baja",
      onClick: () =>
        Modal.confirm({
          title: `¿Dar de baja a ${client.full_name}?`,
          content: "Se quita su cola del MikroTik y se libera la antena.",
          okText: "Dar de baja",
          okButtonProps: { danger: true },
          cancelText: "Cancelar",
          onOk: () => cancel.mutateAsync(),
        }),
    },
  ].filter(Boolean) as any[];

  return (
    <div>
      <Button type="link" icon={<ArrowLeftOutlined />} onClick={() => navigate("/clients")} style={{ paddingLeft: 0 }}>
        Clientes
      </Button>

      {/* ── Header ── */}
      <Card style={{ marginBottom: 16 }}>
        <Row gutter={[16, 16]} align="middle" justify="space-between">
          <Col xs={24} md={14}>
            <Space align="center" wrap>
              <Title level={3} style={{ margin: 0 }}>{client.full_name}</Title>
              <Tag color={status.color}>{status.label}</Tag>
              {conn?.status === "online" && <Tag color="green">Conectado</Tag>}
              {conn?.status === "not_detected" && <Tag color="red">No se ve conectado</Tag>}
              {connLoading && <Tag>Consultando conexión…</Tag>}
            </Space>
            <div style={{ marginTop: 6 }}>
              <Text type="secondary">
                {client.plan ? `${client.plan.name} (${client.plan.download_mbps}/${client.plan.upload_mbps} Mbps)` : "Sin plan"}
                {" · "}IP {client.ip_address}
                {client.router ? ` · ${client.router.name}` : ""}
              </Text>
            </div>
            {client.phone && (
              <Space style={{ marginTop: 6 }}>
                <a href={`tel:${phoneDigits}`}>{client.phone}</a>
                <a href={whatsapp()} target="_blank" rel="noreferrer">
                  <WhatsAppOutlined /> WhatsApp
                </a>
              </Space>
            )}
          </Col>
          {can.seeBilling && <Col xs={24} md={10} style={{ textAlign: "right" }}>
            <Space size={32} wrap style={{ justifyContent: "flex-end" }}>
              <Statistic
                title="Saldo"
                value={summary?.balance != null ? money(summary.balance) : "…"}
                valueStyle={{ color: (summary?.balance ?? 0) > 0 ? "#cf1322" : undefined }}
              />
              <Statistic title="Facturas vencidas" value={summary?.overdue_count ?? "…"} />
            </Space>
            {summary?.last_payment && (
              <div>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  Último pago: {money(summary.last_payment.amount)} el {day(summary.last_payment.date)} (
                  {METHODS[summary.last_payment.method as PaymentMethod] ?? summary.last_payment.method})
                </Text>
              </div>
            )}
          </Col>}
        </Row>

        {/* ── Actions ── */}
        <Space wrap style={{ marginTop: 16 }}>
          {can.pay && unpaid.length > 0 && (
            <Button type="primary" icon={<DollarOutlined />} onClick={() => openPay()}>Registrar pago</Button>
          )}
          {can.cut && client.status === "active" && (
            <Popconfirm title="¿Cortar el servicio?" okText="Cortar" cancelText="Cancelar" onConfirm={() => cut.mutate()}>
              <Button icon={<PauseCircleOutlined />} loading={cut.isPending}>Cortar</Button>
            </Popconfirm>
          )}
          {can.cut && client.status === "suspended" && (
            <Popconfirm title="¿Reactivar el servicio?" okText="Reactivar" cancelText="Cancelar" onConfirm={() => reactivate.mutate()}>
              <Button icon={<PlayCircleOutlined />} loading={reactivate.isPending}>Reactivar</Button>
            </Popconfirm>
          )}
          {can.edit && client.status !== "cancelled" && (
            <Button onClick={() => { planForm.setFieldsValue({ plan_id: client.plan_id }); setModal("plan"); }}>Cambiar plan</Button>
          )}
          {can.ticket && (
            <Button icon={<PlusOutlined />} onClick={() => { ticketForm.resetFields(); setModal("ticket"); }}>Ticket</Button>
          )}
          {can.order && (
            <Button icon={<ToolOutlined />} onClick={() => { orderForm.resetFields(); setModal("order"); }}>Orden de trabajo</Button>
          )}
          {can.bill && summary?.oldest_unpaid_invoice_id && (
            <Button icon={<LinkOutlined />} loading={makeLink.isPending} onClick={() => makeLink.mutate(summary.oldest_unpaid_invoice_id!)}>
              Link de pago
            </Button>
          )}
          {moreItems.length > 0 && (
            <Dropdown menu={{ items: moreItems }} trigger={["click"]}>
              <Button icon={<MoreOutlined />}>Más</Button>
            </Dropdown>
          )}
        </Space>
      </Card>

      {/* ── Tabs ── */}
      <Card>
        <Tabs
          defaultActiveKey={can.seeBilling ? "account" : "service"}
          items={[
            can.seeBilling && { key: "account", label: `Cuenta${summary?.unpaid_count ? ` (${summary.unpaid_count} impagas)` : ""}`, children: <AccountTab invoices={invoices} canPay={can.pay} onPay={openPay} total={invoicePage?.total ?? 0} /> },
            { key: "service", label: "Servicio y red", children: <ServiceTab client={client} conn={conn} connLoading={connLoading} onRefresh={() => refreshConn()} /> },
            { key: "support", label: `Soporte${summary ? ` (${summary.open_tickets + summary.open_work_orders} abiertos)` : ""}`, children: <SupportTab clientId={clientId} /> },
            {
              key: "notes",
              label: "Notas e historial",
              children: <NotesTab clientId={clientId} note={note} setNote={setNote} onAdd={() => addNote.mutate()} adding={addNote.isPending} legacy={client.notes} canWrite={can.edit} />,
            },
            { key: "data", label: "Datos", children: <DataTab client={client} /> },
            { key: "map", label: "Ubicación", children: <MapTab lat={client.latitude} lng={client.longitude} address={client.address} onEdit={can.edit ? () => navigate(`/clients/${clientId}/edit`) : undefined} /> },
          ].filter(Boolean) as any[]}
        />
        {!isAdmin && !can.edit && (
          <Text type="secondary" style={{ fontSize: 12 }}>Solo lectura: tu usuario no puede modificar clientes.</Text>
        )}
      </Card>

      {/* ── Modals ── */}
      <Modal open={modal === "pay"} title="Registrar pago" okText="Registrar" cancelText="Cancelar"
        onCancel={() => setModal(null)} onOk={() => payForm.submit()} confirmLoading={pay.isPending} destroyOnClose>
        <Form form={payForm} layout="vertical" onFinish={(v) => pay.mutate(v)}>
          <Form.Item name="invoice_id" label="Factura" rules={[{ required: true }]}>
            <Select
              onChange={(v) => {
                const inv = unpaid.find((i) => i.id === v);
                setPayInvoice(inv ?? null);
                if (inv) payForm.setFieldValue("amount", Math.max(0, Number(inv.amount) - paidOf(inv)));
              }}
              options={unpaid.map((i) => ({
                value: i.id,
                label: `${i.period} · vence ${day(i.due_date)} · resta ${money(Math.max(0, Number(i.amount) - paidOf(i)))}`,
              }))}
            />
          </Form.Item>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="amount" label="Monto" rules={[{ required: true }]}
                extra={payInvoice ? `Total de la factura: ${money(Number(payInvoice.amount))}` : undefined}>
                <InputNumber min={0.01} step={100} style={{ width: "100%" }} prefix="$" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="payment_date" label="Fecha" rules={[{ required: true }]}>
                <DatePicker format="DD/MM/YYYY" style={{ width: "100%" }} />
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
                <Input placeholder="N° de operación, recibo…" />
              </Form.Item>
            </Col>
          </Row>
          {client.status === "suspended" && (
            <Alert type="info" showIcon message="Si con este pago no le quedan facturas vencidas, se reactiva solo." />
          )}
        </Form>
      </Modal>

      <PlanModal open={modal === "plan"} form={planForm} onCancel={() => setModal(null)} loading={changePlan.isPending}
        onSubmit={(planId) => changePlan.mutate(planId)} />

      <Modal open={modal === "ticket"} title={`Nuevo ticket · ${client.full_name}`} okText="Crear" cancelText="Cancelar"
        onCancel={() => setModal(null)} onOk={() => ticketForm.submit()} confirmLoading={newTicket.isPending} destroyOnClose>
        <Form form={ticketForm} layout="vertical" onFinish={(v) => newTicket.mutate(v)} initialValues={{ priority: "medium", category: "connectivity" }}>
          <Form.Item name="title" label="Asunto" rules={[{ required: true, message: "Escribí el asunto" }]}>
            <Input placeholder="Ej: No tiene internet desde ayer" />
          </Form.Item>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="category" label="Tipo">
                <Select options={Object.entries(CATEGORIES).map(([value, label]) => ({ value, label }))} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="priority" label="Prioridad">
                <Select options={Object.entries(PRIORITIES).map(([value, label]) => ({ value, label }))} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="description" label="Detalle">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal open={modal === "order"} title={`Nueva orden de trabajo · ${client.full_name}`} okText="Crear" cancelText="Cancelar"
        onCancel={() => setModal(null)} onOk={() => orderForm.submit()} confirmLoading={newOrder.isPending} destroyOnClose>
        <Form form={orderForm} layout="vertical" onFinish={(v) => newOrder.mutate(v)} initialValues={{ type: "repair", priority: "medium" }}>
          <Form.Item name="title" label="Trabajo" rules={[{ required: true, message: "Describí el trabajo" }]}>
            <Input placeholder="Ej: Revisar antena, sin señal" />
          </Form.Item>
          <Row gutter={12}>
            <Col span={8}>
              <Form.Item name="type" label="Tipo">
                <Select options={[
                  { value: "installation", label: "Instalación" },
                  { value: "repair", label: "Reparación" },
                  { value: "maintenance", label: "Mantenimiento" },
                  { value: "inspection", label: "Inspección" },
                  { value: "other", label: "Otro" },
                ]} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="priority" label="Prioridad">
                <Select options={Object.entries(PRIORITIES).map(([value, label]) => ({ value, label }))} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="scheduled_date" label="Fecha">
                <DatePicker showTime={{ format: "HH:mm" }} format="DD/MM HH:mm" style={{ width: "100%" }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="description" label="Detalle">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Text type="secondary" style={{ fontSize: 12 }}>
            La orden se crea con la dirección y la ubicación del cliente.
          </Text>
        </Form>
      </Modal>

      <Modal open={modal === "link"} title="Link de pago de MercadoPago" footer={<Button onClick={() => setModal(null)}>Cerrar</Button>} onCancel={() => setModal(null)}>
        {link && (
          <Space direction="vertical" style={{ width: "100%" }}>
            <Paragraph copyable={{ text: link }} style={{ wordBreak: "break-all", marginBottom: 0 }}>{link}</Paragraph>
            {phoneDigits && (
              <Button type="primary" icon={<WhatsAppOutlined />}
                href={whatsapp(`Hola ${client.first_name}, te paso el link para pagar tu factura de internet: ${link}`)}
                target="_blank" rel="noreferrer">
                Enviar por WhatsApp
              </Button>
            )}
          </Space>
        )}
      </Modal>
    </div>
  );
}

// ── Tabs ─────────────────────────────────────────────────────────────────────

function AccountTab({ invoices, canPay, onPay, total }: { invoices: Invoice[]; canPay: boolean; onPay: (i: Invoice) => void; total: number }) {
  if (!invoices.length) return <Empty description="Sin facturas" />;
  return (
    <>
      <Table<Invoice>
        dataSource={invoices}
        rowKey="id"
        size="small"
        pagination={{ pageSize: 12 }}
        scroll={{ x: 700 }}
        expandable={{
          rowExpandable: (r) => r.payments.length > 0,
          expandedRowRender: (r) => (
            <List
              size="small"
              dataSource={r.payments}
              renderItem={(p) => (
                <List.Item>
                  {day(p.payment_date)} · {money(Number(p.amount))} · {METHODS[p.method] ?? p.method}
                  {p.reference ? ` · ${p.reference}` : ""}
                </List.Item>
              )}
            />
          ),
        }}
        columns={[
          { title: "Período", dataIndex: "period" },
          { title: "Vence", dataIndex: "due_date", render: (d: string) => day(d) },
          { title: "Monto", dataIndex: "amount", align: "right", render: (v: number) => money(Number(v)) },
          { title: "Pagado", key: "paid", align: "right", render: (_: unknown, r) => money(paidOf(r)) },
          { title: "Estado", dataIndex: "status", render: (s: InvoiceStatus) => <Tag color={INVOICE_STATUS[s].color}>{INVOICE_STATUS[s].label}</Tag> },
          {
            title: "",
            key: "actions",
            align: "right",
            render: (_: unknown, r) => (
              <Space size={4}>
                {canPay && isUnpaid(r) && <Button size="small" onClick={() => onPay(r)}>Cobrar</Button>}
                <Tooltip title="Descargar PDF">
                  <Button size="small" icon={<FilePdfOutlined />} onClick={() => invoicesApi.downloadPdf(r.id)} />
                </Tooltip>
              </Space>
            ),
          },
        ]}
      />
      {total > invoices.length && (
        <Text type="secondary" style={{ fontSize: 12 }}>Se muestran las {invoices.length} facturas más recientes de {total}.</Text>
      )}
    </>
  );
}

function ServiceTab({ client, conn, connLoading, onRefresh }: {
  client: any;
  conn?: { status: string; checked_at: string; detail?: string; interface?: string };
  connLoading: boolean;
  onRefresh: () => void;
}) {
  const navigate = useNavigate();
  return (
    <Descriptions column={{ xs: 1, md: 2 }} size="small" bordered>
      <Descriptions.Item label="Plan">
        {client.plan ? `${client.plan.name} · ${client.plan.download_mbps}/${client.plan.upload_mbps} Mbps · ${money(Number(client.plan.price))}` : "—"}
      </Descriptions.Item>
      <Descriptions.Item label="Estado de conexión">
        <Space>
          {conn?.status === "online" && <Tag color="green">Conectado{conn.interface ? ` (${conn.interface})` : ""}</Tag>}
          {conn?.status === "not_detected" && <Tag color="red">No se ve en el router</Tag>}
          {conn?.status === "unknown" && <Tag>{conn.detail ?? "Sin datos"}</Tag>}
          <Button size="small" icon={<ReloadOutlined />} loading={connLoading} onClick={onRefresh}>Consultar</Button>
        </Space>
      </Descriptions.Item>
      <Descriptions.Item label="IP">{client.ip_address}</Descriptions.Item>
      <Descriptions.Item label="MAC">{client.mac_address ?? "—"}</Descriptions.Item>
      <Descriptions.Item label="Router">{client.router?.name ?? "—"}</Descriptions.Item>
      <Descriptions.Item label="Cola en MikroTik">{client.mikrotik_queue_name}</Descriptions.Item>
      <Descriptions.Item label="PPPoE">{client.pppoe_username ? `${client.pppoe_username}${client.has_pppoe ? " (con contraseña)" : ""}` : "No usa"}</Descriptions.Item>
      <Descriptions.Item label="Zona">{client.zone?.name ?? "—"}</Descriptions.Item>
      <Descriptions.Item label="Antena">
        {client.ubiquiti_device_id ? <a onClick={() => navigate("/ubiquiti")}>Ver equipo #{client.ubiquiti_device_id}</a> : "Sin asignar"}
      </Descriptions.Item>
      <Descriptions.Item label="Día de facturación">{client.billing_day}</Descriptions.Item>
      <Descriptions.Item label="Alta del servicio">{day(client.service_start_date)}</Descriptions.Item>
    </Descriptions>
  );
}

function SupportTab({ clientId }: { clientId: number }) {
  const navigate = useNavigate();
  const { data: tickets = [], isLoading: lt } = useQuery({
    queryKey: ["client-tickets", clientId],
    queryFn: () => ticketsApi.list({ client_id: clientId }),
  });
  const { data: orders = [], isLoading: lo } = useQuery({
    queryKey: ["client-orders", clientId],
    queryFn: () => workOrdersApi.list({ client_id: clientId }),
  });
  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} lg={12}>
        <Title level={5}>Tickets</Title>
        <Table
          loading={lt}
          size="small"
          rowKey="id"
          dataSource={tickets}
          pagination={{ pageSize: 8 }}
          locale={{ emptyText: "Sin tickets" }}
          onRow={() => ({ onClick: () => navigate("/tickets"), style: { cursor: "pointer" } })}
          columns={[
            { title: "Fecha", dataIndex: "created_at", render: (d: string) => day(d) },
            { title: "Asunto", dataIndex: "title" },
            { title: "Estado", dataIndex: "status", render: (s: string) => <Tag color={TICKET_STATUS[s]?.color}>{TICKET_STATUS[s]?.label ?? s}</Tag> },
          ]}
        />
      </Col>
      <Col xs={24} lg={12}>
        <Title level={5}>Órdenes de trabajo</Title>
        <Table
          loading={lo}
          size="small"
          rowKey="id"
          dataSource={orders}
          pagination={{ pageSize: 8 }}
          locale={{ emptyText: "Sin órdenes" }}
          onRow={() => ({ onClick: () => navigate("/work-orders"), style: { cursor: "pointer" } })}
          columns={[
            { title: "Fecha", key: "date", render: (_: unknown, r: any) => day(r.scheduled_date ?? r.created_at) },
            { title: "Trabajo", dataIndex: "title" },
            { title: "Técnico", dataIndex: "assigned_to_name", render: (v?: string) => v ?? "—" },
            { title: "Estado", dataIndex: "status", render: (s: string) => <Tag color={WO_STATUS[s]?.color}>{WO_STATUS[s]?.label ?? s}</Tag> },
          ]}
        />
      </Col>
    </Row>
  );
}

function NotesTab({ clientId, note, setNote, onAdd, adding, legacy, canWrite }: {
  clientId: number;
  note: string;
  setNote: (v: string) => void;
  onAdd: () => void;
  adding: boolean;
  legacy?: string;
  canWrite: boolean;
}) {
  const { data: notes = [] } = useQuery({ queryKey: ["client-notes", clientId], queryFn: () => clientsApi.notes(clientId) });
  const { data: history = [] } = useQuery({ queryKey: ["client-history", clientId], queryFn: () => clientsApi.history(clientId) });
  return (
    <Row gutter={[24, 16]}>
      <Col xs={24} lg={13}>
        <Title level={5}>Notas</Title>
        {canWrite && (
          <Space.Compact style={{ width: "100%", marginBottom: 12 }}>
            <Input.TextArea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              autoSize={{ minRows: 2, maxRows: 6 }}
              placeholder="Ej: Llamó para avisar que paga el viernes"
              maxLength={4000}
            />
            <Button type="primary" onClick={onAdd} loading={adding} disabled={!note.trim()}>Guardar</Button>
          </Space.Compact>
        )}
        {legacy && (
          <Alert type="info" style={{ marginBottom: 12 }} message="Nota anterior (sin fecha)" description={legacy} />
        )}
        <List
          dataSource={notes}
          locale={{ emptyText: "Sin notas" }}
          renderItem={(n) => (
            <List.Item>
              <List.Item.Meta
                title={<Text type="secondary" style={{ fontSize: 12 }}>{n.username} · {when(n.created_at)}</Text>}
                description={<span style={{ whiteSpace: "pre-wrap", color: "inherit" }}>{n.body}</span>}
              />
            </List.Item>
          )}
        />
      </Col>
      <Col xs={24} lg={11}>
        <Title level={5}>Historial</Title>
        {history.length === 0 ? (
          <Empty description="Sin movimientos registrados" />
        ) : (
          <Timeline
            items={history.map((h) => ({
              children: (
                <>
                  <Text strong>{ACTIONS[h.action] ?? h.action}</Text>
                  <Text type="secondary" style={{ fontSize: 12 }}> · {h.username} · {when(h.created_at)}</Text>
                  {h.details && <div style={{ fontSize: 12 }}>{h.details}</div>}
                </>
              ),
            }))}
          />
        )}
      </Col>
    </Row>
  );
}

function DataTab({ client }: { client: any }) {
  return (
    <Descriptions column={{ xs: 1, md: 2 }} size="small" bordered>
      <Descriptions.Item label="Nombre">{client.first_name}</Descriptions.Item>
      <Descriptions.Item label="Apellido">{client.last_name}</Descriptions.Item>
      <Descriptions.Item label="DNI">{client.dni ?? "—"}</Descriptions.Item>
      <Descriptions.Item label="CUIT">{client.cuit ?? "—"}</Descriptions.Item>
      <Descriptions.Item label="Teléfono">{client.phone ?? "—"}</Descriptions.Item>
      <Descriptions.Item label="Email">{client.email ?? "—"}</Descriptions.Item>
      <Descriptions.Item label="Dirección" span={2}>{client.address ?? "—"}</Descriptions.Item>
      <Descriptions.Item label="Cliente desde">{day(client.created_at)}</Descriptions.Item>
    </Descriptions>
  );
}

function MapTab({ lat, lng, address, onEdit }: { lat?: number; lng?: number; address?: string; onEdit?: () => void }) {
  if (lat == null || lng == null) {
    return (
      <Empty description="El cliente no tiene ubicación cargada">
        {onEdit && <Button icon={<EnvironmentOutlined />} onClick={onEdit}>Cargar ubicación</Button>}
      </Empty>
    );
  }
  return (
    <>
      <div style={{ height: 360, borderRadius: 8, overflow: "hidden" }}>
        <MapContainer center={[lat, lng]} zoom={16} style={{ height: "100%", width: "100%" }}>
          <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="&copy; OpenStreetMap" />
          <Marker position={[lat, lng]} icon={pin} />
        </MapContainer>
      </div>
      <Space style={{ marginTop: 8 }}>
        {address && <Text type="secondary">{address}</Text>}
        <a href={`https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`} target="_blank" rel="noreferrer">
          Cómo llegar (Google Maps)
        </a>
      </Space>
    </>
  );
}

function PlanModal({ open, form, onCancel, onSubmit, loading }: {
  open: boolean;
  form: any;
  onCancel: () => void;
  onSubmit: (planId: number) => void;
  loading: boolean;
}) {
  const { data: plans = [], isLoading } = useQuery({
    queryKey: ["plans", "active"],
    queryFn: () => plansApi.list(true),
    enabled: open,
  });
  return (
    <Modal open={open} title="Cambiar plan" okText="Cambiar" cancelText="Cancelar"
      onCancel={onCancel} onOk={() => form.submit()} confirmLoading={loading}>
      <Form form={form} layout="vertical" onFinish={(v: { plan_id: number }) => onSubmit(v.plan_id)}>
        <Form.Item name="plan_id" label="Plan nuevo" rules={[{ required: true, message: "Elegí un plan" }]}>
          <Select
            loading={isLoading}
            options={plans.map((p) => ({
              value: p.id,
              label: `${p.name} · ${p.download_mbps}/${p.upload_mbps} Mbps · ${money(Number(p.price))}`,
            }))}
          />
        </Form.Item>
        <Text type="secondary" style={{ fontSize: 12 }}>
          La velocidad nueva se aplica en el MikroTik al guardar. Las facturas ya emitidas no cambian.
        </Text>
      </Form>
    </Modal>
  );
}

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Badge,
  Button,
  Card,
  Col,
  Drawer,
  Form,
  Input,
  Row,
  Select,
  Space,
  Tag,
  Timeline,
  Typography,
  message,
} from "antd";
import {
  ClockCircleOutlined,
  CommentOutlined,
  CustomerServiceOutlined,
  PlusOutlined,
  UserOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import "dayjs/locale/es";
import { ticketsApi } from "@/services/api";
import { clientsApi } from "@/services/api";
import { usersApi } from "@/services/api";
import type { Ticket, TicketStatus, TicketPriority, TicketCategory } from "@/types";

dayjs.extend(relativeTime);
dayjs.locale("es");

const { Title, Text } = Typography;
const { TextArea } = Input;

const STATUS_COLOR: Record<TicketStatus, string> = {
  open: "blue",
  in_progress: "orange",
  resolved: "green",
  closed: "default",
};

const STATUS_LABEL: Record<TicketStatus, string> = {
  open: "Abierto",
  in_progress: "En curso",
  resolved: "Resuelto",
  closed: "Cerrado",
};

const PRIORITY_COLOR: Record<TicketPriority, string> = {
  low: "default",
  medium: "gold",
  high: "red",
};

const PRIORITY_LABEL: Record<TicketPriority, string> = {
  low: "Baja",
  medium: "Media",
  high: "Alta",
};

const CATEGORY_LABEL: Record<TicketCategory, string> = {
  connectivity: "Conectividad",
  speed: "Velocidad",
  billing: "Facturación",
  equipment: "Equipo",
  installation: "Instalación",
  other: "Otro",
};

export default function Tickets() {
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<TicketStatus | undefined>();
  const [priorityFilter, setPriorityFilter] = useState<TicketPriority | undefined>();
  const [formOpen, setFormOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [selected, setSelected] = useState<Ticket | null>(null);
  const [form] = Form.useForm();
  const [editForm] = Form.useForm();
  const [commentText, setCommentText] = useState("");

  const { data: tickets = [], isLoading } = useQuery({
    queryKey: ["tickets", { status: statusFilter, priority: priorityFilter }],
    queryFn: () => ticketsApi.list({ status: statusFilter, priority: priorityFilter }),
  });

  const { data: clients = [] } = useQuery({
    queryKey: ["clients-list"],
    queryFn: () => clientsApi.list({ limit: 500 }),
  });

  const { data: users = [] } = useQuery({
    queryKey: ["users"],
    queryFn: usersApi.list,
  });

  const createMutation = useMutation({
    mutationFn: ticketsApi.create,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tickets"] });
      message.success("Ticket creado");
      setFormOpen(false);
      form.resetFields();
    },
    onError: (e: any) => message.error(e.response?.data?.detail ?? "Error al crear ticket"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: any }) => ticketsApi.update(id, data),
    onSuccess: (updated) => {
      qc.invalidateQueries({ queryKey: ["tickets"] });
      setSelected(updated);
      message.success("Ticket actualizado");
    },
    onError: () => message.error("Error al actualizar ticket"),
  });

  const commentMutation = useMutation({
    mutationFn: ({ id, body }: { id: number; body: string }) => ticketsApi.addComment(id, body),
    onSuccess: (comment) => {
      qc.invalidateQueries({ queryKey: ["tickets"] });
      setSelected((prev) => prev ? { ...prev, comments: [...prev.comments, comment] } : prev);
      setCommentText("");
      message.success("Comentario agregado");
    },
    onError: () => message.error("Error al agregar comentario"),
  });

  function openDetail(ticket: Ticket) {
    setSelected(ticket);
    editForm.setFieldsValue({
      status: ticket.status,
      priority: ticket.priority,
      assigned_to_id: ticket.assigned_to_id,
    });
    setDetailOpen(true);
  }

  const statusOrder: Record<TicketStatus, number> = { open: 0, in_progress: 1, resolved: 2, closed: 3 };
  const sorted = [...tickets].sort((a, b) => {
    const pdiff = (b.priority === "high" ? 2 : b.priority === "medium" ? 1 : 0) -
                  (a.priority === "high" ? 2 : a.priority === "medium" ? 1 : 0);
    if (pdiff !== 0) return pdiff;
    return statusOrder[a.status] - statusOrder[b.status];
  });

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          <CustomerServiceOutlined /> Soporte / Tickets
        </Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setFormOpen(true)}>
          Nuevo ticket
        </Button>
      </div>

      <Space style={{ marginBottom: 16 }}>
        <Select
          placeholder="Estado"
          style={{ width: 140 }}
          allowClear
          value={statusFilter}
          onChange={setStatusFilter}
          options={Object.entries(STATUS_LABEL).map(([k, v]) => ({ value: k, label: v }))}
        />
        <Select
          placeholder="Prioridad"
          style={{ width: 130 }}
          allowClear
          value={priorityFilter}
          onChange={setPriorityFilter}
          options={Object.entries(PRIORITY_LABEL).map(([k, v]) => ({ value: k, label: v }))}
        />
      </Space>

      {isLoading ? (
        <Text>Cargando...</Text>
      ) : (
        <Row gutter={[12, 12]}>
          {sorted.map((ticket) => (
            <Col xs={24} sm={12} lg={8} xl={6} key={ticket.id}>
              <Card
                size="small"
                hoverable
                onClick={() => openDetail(ticket)}
                title={
                  <Space size={4}>
                    <Tag color={PRIORITY_COLOR[ticket.priority]}>{PRIORITY_LABEL[ticket.priority]}</Tag>
                    <Tag color={STATUS_COLOR[ticket.status]}>{STATUS_LABEL[ticket.status]}</Tag>
                  </Space>
                }
                extra={<Text type="secondary" style={{ fontSize: 11 }}>#{ticket.id}</Text>}
                style={{ cursor: "pointer" }}
              >
                <div style={{ fontWeight: 600, marginBottom: 4 }}>{ticket.title}</div>
                {ticket.client_name && (
                  <div style={{ fontSize: 12, color: "#666" }}>
                    <UserOutlined /> {ticket.client_name}
                  </div>
                )}
                <div style={{ fontSize: 12, color: "#666", marginTop: 2 }}>
                  {CATEGORY_LABEL[ticket.category]}
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, fontSize: 11, color: "#999" }}>
                  <span><ClockCircleOutlined /> {dayjs(ticket.created_at).fromNow()}</span>
                  {ticket.comments.length > 0 && (
                    <span><CommentOutlined /> {ticket.comments.length}</span>
                  )}
                </div>
              </Card>
            </Col>
          ))}
          {sorted.length === 0 && (
            <Col span={24}>
              <Text type="secondary">No hay tickets con los filtros seleccionados.</Text>
            </Col>
          )}
        </Row>
      )}

      {/* New ticket modal */}
      <Drawer
        title="Nuevo ticket"
        open={formOpen}
        onClose={() => { setFormOpen(false); form.resetFields(); }}
        width={480}
        footer={
          <Space>
            <Button onClick={() => { setFormOpen(false); form.resetFields(); }}>Cancelar</Button>
            <Button type="primary" onClick={() => form.submit()} loading={createMutation.isPending}>
              Crear ticket
            </Button>
          </Space>
        }
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{ priority: "medium", category: "other" }}
          onFinish={(v) => createMutation.mutate(v)}
        >
          <Form.Item name="title" label="Título" rules={[{ required: true }]}>
            <Input placeholder="Describe brevemente el problema" />
          </Form.Item>
          <Form.Item name="client_id" label="Cliente">
            <Select
              showSearch
              allowClear
              placeholder="Opcional"
              filterOption={(input, opt) => (opt?.label as string ?? "").toLowerCase().includes(input.toLowerCase())}
              options={clients.map((c: any) => ({ value: c.id, label: c.full_name }))}
            />
          </Form.Item>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="priority" label="Prioridad">
                <Select options={Object.entries(PRIORITY_LABEL).map(([k, v]) => ({ value: k, label: v }))} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="category" label="Categoría">
                <Select options={Object.entries(CATEGORY_LABEL).map(([k, v]) => ({ value: k, label: v }))} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="assigned_to_id" label="Asignar a">
            <Select
              showSearch
              allowClear
              placeholder="Sin asignar"
              filterOption={(input, opt) => (opt?.label as string ?? "").toLowerCase().includes(input.toLowerCase())}
              options={users.map((u: any) => ({ value: u.id, label: u.full_name || u.username }))}
            />
          </Form.Item>
          <Form.Item name="description" label="Descripción">
            <TextArea rows={4} placeholder="Detalle del problema..." />
          </Form.Item>
        </Form>
      </Drawer>

      {/* Ticket detail drawer */}
      <Drawer
        title={selected ? `Ticket #${selected.id} — ${selected.title}` : ""}
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        width={560}
      >
        {selected && (
          <>
            <Form
              form={editForm}
              layout="inline"
              onFinish={(v) => updateMutation.mutate({ id: selected.id, data: v })}
              style={{ marginBottom: 16, gap: 8, flexWrap: "wrap" }}
            >
              <Form.Item name="status" label="Estado">
                <Select style={{ width: 130 }} options={Object.entries(STATUS_LABEL).map(([k, v]) => ({ value: k, label: v }))} />
              </Form.Item>
              <Form.Item name="priority" label="Prioridad">
                <Select style={{ width: 120 }} options={Object.entries(PRIORITY_LABEL).map(([k, v]) => ({ value: k, label: v }))} />
              </Form.Item>
              <Form.Item name="assigned_to_id" label="Técnico">
                <Select
                  style={{ width: 160 }}
                  allowClear
                  placeholder="Sin asignar"
                  options={users.map((u: any) => ({ value: u.id, label: u.full_name || u.username }))}
                />
              </Form.Item>
              <Form.Item>
                <Button type="primary" htmlType="submit" size="small" loading={updateMutation.isPending}>
                  Guardar
                </Button>
              </Form.Item>
            </Form>

            {selected.client_name && (
              <div style={{ marginBottom: 8 }}>
                <Text type="secondary">Cliente: </Text>
                <Text strong>{selected.client_name}</Text>
              </div>
            )}
            <div style={{ marginBottom: 8 }}>
              <Tag>{CATEGORY_LABEL[selected.category]}</Tag>
              <Text type="secondary" style={{ fontSize: 12 }}>
                Creado {dayjs(selected.created_at).format("DD/MM/YYYY HH:mm")}
              </Text>
            </div>

            {selected.description && (
              <Card size="small" style={{ marginBottom: 16, background: "#fafafa" }}>
                <Text>{selected.description}</Text>
              </Card>
            )}

            <div style={{ fontWeight: 600, marginBottom: 8 }}>Comentarios</div>
            {selected.comments.length > 0 ? (
              <Timeline
                style={{ marginBottom: 16 }}
                items={selected.comments.map((c) => ({
                  key: c.id,
                  dot: <CommentOutlined />,
                  children: (
                    <div>
                      <div style={{ fontSize: 12, color: "#999", marginBottom: 2 }}>
                        {c.author_name ?? "Sistema"} · {dayjs(c.created_at).format("DD/MM HH:mm")}
                      </div>
                      <div>{c.body}</div>
                    </div>
                  ),
                }))}
              />
            ) : (
              <Text type="secondary" style={{ fontSize: 13 }}>Sin comentarios todavía.</Text>
            )}

            <div style={{ marginTop: 16 }}>
              <TextArea
                rows={3}
                value={commentText}
                onChange={(e) => setCommentText(e.target.value)}
                placeholder="Escribí un comentario..."
              />
              <Button
                type="primary"
                style={{ marginTop: 8 }}
                disabled={!commentText.trim()}
                loading={commentMutation.isPending}
                onClick={() => {
                  if (selected && commentText.trim()) {
                    commentMutation.mutate({ id: selected.id, body: commentText.trim() });
                  }
                }}
              >
                Comentar
              </Button>
            </div>
          </>
        )}
      </Drawer>
    </div>
  );
}

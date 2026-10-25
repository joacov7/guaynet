import { useState } from "react";
import {
  Button, DatePicker, Form, Input, Modal, Popconfirm, Select, Space,
  Table, Tag, Typography, message,
} from "antd";
import { PlusOutlined, EditOutlined, DeleteOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import dayjs from "dayjs";
import { workOrdersApi, clientsApi, usersApi } from "@/services/api";
import type { WorkOrder } from "@/types";

const { Title } = Typography;

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
const PRIORITY_COLOR: Record<string, string> = {
  low: "default",
  medium: "gold",
  high: "red",
};
const PRIORITY_LABEL: Record<string, string> = {
  low: "Baja",
  medium: "Media",
  high: "Alta",
};

export default function WorkOrders() {
  const qc = useQueryClient();
  const [form] = Form.useForm();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<WorkOrder | null>(null);

  const { data: orders = [], isLoading } = useQuery({
    queryKey: ["work-orders"],
    queryFn: () => workOrdersApi.list(),
  });
  const { data: clients = [] } = useQuery({
    queryKey: ["clients-brief"],
    queryFn: () => clientsApi.list({ limit: 1000 }),
  });
  const { data: users = [] } = useQuery({
    queryKey: ["users"],
    queryFn: () => usersApi.list(),
  });

  const createMutation = useMutation({
    mutationFn: workOrdersApi.create,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["work-orders"] }); closeModal(); message.success("Orden creada"); },
    onError: () => message.error("Error al crear la orden"),
  });
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<WorkOrder> }) => workOrdersApi.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["work-orders"] }); closeModal(); message.success("Orden actualizada"); },
    onError: () => message.error("Error al actualizar"),
  });
  const deleteMutation = useMutation({
    mutationFn: workOrdersApi.delete,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["work-orders"] }); message.success("Orden eliminada"); },
    onError: () => message.error("Error al eliminar"),
  });

  function openCreate() {
    setEditing(null);
    form.resetFields();
    setOpen(true);
  }

  function openEdit(wo: WorkOrder) {
    setEditing(wo);
    form.setFieldsValue({
      ...wo,
      scheduled_date: wo.scheduled_date ? dayjs(wo.scheduled_date) : null,
    });
    setOpen(true);
  }

  function closeModal() {
    setOpen(false);
    setEditing(null);
    form.resetFields();
  }

  async function handleSubmit() {
    const vals = await form.validateFields();
    const payload = {
      ...vals,
      scheduled_date: vals.scheduled_date ? vals.scheduled_date.toISOString() : null,
    };
    if (editing) {
      updateMutation.mutate({ id: editing.id, data: payload });
    } else {
      createMutation.mutate(payload);
    }
  }

  const columns = [
    {
      title: "Título",
      dataIndex: "title",
      key: "title",
      render: (v: string, r: WorkOrder) => (
        <div>
          <div style={{ fontWeight: 600 }}>{v}</div>
          {r.address && <div style={{ fontSize: 12, color: "#8c8c8c" }}>📍 {r.address}</div>}
        </div>
      ),
    },
    {
      title: "Tipo",
      dataIndex: "type",
      key: "type",
      render: (v: string) => <Tag>{TYPE_LABEL[v] || v}</Tag>,
    },
    {
      title: "Prioridad",
      dataIndex: "priority",
      key: "priority",
      render: (v: string) => <Tag color={PRIORITY_COLOR[v]}>{PRIORITY_LABEL[v] || v}</Tag>,
    },
    {
      title: "Estado",
      dataIndex: "status",
      key: "status",
      render: (v: string) => <Tag color={STATUS_COLOR[v]}>{STATUS_LABEL[v] || v}</Tag>,
    },
    {
      title: "Cliente",
      dataIndex: "client_name",
      key: "client_name",
      render: (v: string) => v || <span style={{ color: "#bfbfbf" }}>—</span>,
    },
    {
      title: "Técnico",
      dataIndex: "assigned_to_name",
      key: "assigned_to_name",
      render: (v: string) => v || <span style={{ color: "#bfbfbf" }}>—</span>,
    },
    {
      title: "Programada",
      dataIndex: "scheduled_date",
      key: "scheduled_date",
      render: (v: string) => v ? dayjs(v).format("DD/MM/YY HH:mm") : <span style={{ color: "#bfbfbf" }}>—</span>,
    },
    {
      title: "Acciones",
      key: "actions",
      render: (_: unknown, r: WorkOrder) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)} />
          <Popconfirm
            title="¿Eliminar esta orden?"
            onConfirm={() => deleteMutation.mutate(r.id)}
            okText="Sí"
            cancelText="No"
          >
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>Órdenes de Trabajo</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          Nueva OT
        </Button>
      </div>

      <Table
        dataSource={orders}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        size="small"
        pagination={{ pageSize: 20 }}
      />

      <Modal
        open={open}
        title={editing ? "Editar Orden" : "Nueva Orden de Trabajo"}
        onCancel={closeModal}
        onOk={handleSubmit}
        confirmLoading={createMutation.isPending || updateMutation.isPending}
        okText={editing ? "Guardar" : "Crear"}
        width={600}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="title" label="Título" rules={[{ required: true, message: "Requerido" }]}>
            <Input placeholder="Ej: Instalación nuevo cliente" />
          </Form.Item>
          <Form.Item name="type" label="Tipo" initialValue="other">
            <Select options={Object.entries(TYPE_LABEL).map(([v, l]) => ({ value: v, label: l }))} />
          </Form.Item>
          <Form.Item name="priority" label="Prioridad" initialValue="medium">
            <Select options={Object.entries(PRIORITY_LABEL).map(([v, l]) => ({ value: v, label: l }))} />
          </Form.Item>
          {editing && (
            <Form.Item name="status" label="Estado">
              <Select options={Object.entries(STATUS_LABEL).map(([v, l]) => ({ value: v, label: l }))} />
            </Form.Item>
          )}
          <Form.Item name="client_id" label="Cliente">
            <Select
              showSearch
              allowClear
              placeholder="Seleccionar cliente"
              optionFilterProp="label"
              options={clients.map((c) => ({ value: c.id, label: c.full_name }))}
            />
          </Form.Item>
          <Form.Item name="assigned_to_id" label="Técnico asignado">
            <Select
              showSearch
              allowClear
              placeholder="Seleccionar técnico"
              optionFilterProp="label"
              options={users.map((u) => ({ value: u.id, label: u.full_name || u.username }))}
            />
          </Form.Item>
          <Form.Item name="scheduled_date" label="Fecha programada">
            <DatePicker showTime style={{ width: "100%" }} format="DD/MM/YYYY HH:mm" />
          </Form.Item>
          <Form.Item name="address" label="Dirección">
            <Input placeholder="Ej: Av. San Martín 123" />
          </Form.Item>
          <Form.Item name="description" label="Descripción">
            <Input.TextArea rows={3} placeholder="Detalles de la orden..." />
          </Form.Item>
          {editing && (
            <Form.Item name="completion_notes" label="Notas de cierre">
              <Input.TextArea rows={2} placeholder="Observaciones al completar..." />
            </Form.Item>
          )}
        </Form>
      </Modal>
    </div>
  );
}

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Badge,
  Button,
  Col,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import { DeleteOutlined, EditOutlined, PlusOutlined, ToolOutlined } from "@ant-design/icons";
import { inventoryApi, clientsApi } from "@/services/api";
import type { InventoryItem } from "@/types";

const { Title } = Typography;

const CONDITION_LABEL: Record<string, string> = {
  new: "Nuevo",
  good: "Bueno",
  damaged: "Dañado",
  scrapped: "Desechado",
};

const CONDITION_COLOR: Record<string, string> = {
  new: "green",
  good: "blue",
  damaged: "orange",
  scrapped: "red",
};

const STATUS_LABEL: Record<string, string> = {
  in_stock: "En stock",
  assigned: "Asignado",
  returned: "Devuelto",
  lost: "Perdido",
};

const STATUS_COLOR: Record<string, string> = {
  in_stock: "green",
  assigned: "blue",
  returned: "gold",
  lost: "red",
};

const CATEGORIES = [
  "Antena",
  "Router",
  "Switch",
  "Cable UTP",
  "Conector",
  "Fuente de alimentación",
  "Herramienta",
  "Accesorio",
  "Otro",
];

const formatARS = (v: number) =>
  new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS" }).format(v);

export default function Inventory() {
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [categoryFilter, setCategoryFilter] = useState<string | undefined>();
  const [search, setSearch] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<InventoryItem | null>(null);
  const [form] = Form.useForm();

  const { data = [], isLoading } = useQuery({
    queryKey: ["inventory", { status: statusFilter, category: categoryFilter, search }],
    queryFn: () => inventoryApi.list({ status: statusFilter, category: categoryFilter, search: search || undefined }),
  });

  const { data: summary = [] } = useQuery({
    queryKey: ["inventory-summary"],
    queryFn: inventoryApi.summary,
  });

  const { data: clients = [] } = useQuery({
    queryKey: ["clients-list"],
    queryFn: () => clientsApi.list({ limit: 500 }),
  });

  const createMutation = useMutation({
    mutationFn: inventoryApi.create,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["inventory"] });
      qc.invalidateQueries({ queryKey: ["inventory-summary"] });
      message.success("Ítem creado");
      setModalOpen(false);
      form.resetFields();
    },
    onError: (e: any) => message.error(e.response?.data?.detail ?? "Error"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: any }) => inventoryApi.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["inventory"] });
      qc.invalidateQueries({ queryKey: ["inventory-summary"] });
      message.success("Ítem actualizado");
      setModalOpen(false);
      setEditing(null);
      form.resetFields();
    },
    onError: () => message.error("Error al actualizar"),
  });

  const deleteMutation = useMutation({
    mutationFn: inventoryApi.delete,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["inventory"] });
      qc.invalidateQueries({ queryKey: ["inventory-summary"] });
      message.success("Ítem eliminado");
    },
  });

  function openCreate() {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ condition: "new", status: "in_stock", quantity: 1 });
    setModalOpen(true);
  }

  function openEdit(item: InventoryItem) {
    setEditing(item);
    form.setFieldsValue(item);
    setModalOpen(true);
  }

  function handleSubmit(values: any) {
    if (editing) {
      updateMutation.mutate({ id: editing.id, data: values });
    } else {
      createMutation.mutate(values);
    }
  }

  // Summary stats
  const totalInStock = summary.filter((s: any) => s.status === "in_stock").reduce((acc: number, s: any) => acc + s.qty, 0);
  const totalAssigned = summary.filter((s: any) => s.status === "assigned").reduce((acc: number, s: any) => acc + s.qty, 0);
  const totalCost = data
    .filter((i) => i.status === "in_stock" && i.unit_cost)
    .reduce((acc, i) => acc + (i.unit_cost! * i.quantity), 0);

  const columns = [
    { title: "Nombre", dataIndex: "name", key: "name" },
    { title: "Categoría", dataIndex: "category", key: "category" },
    {
      title: "Marca / Modelo",
      key: "brand_model",
      render: (_: unknown, r: InventoryItem) =>
        [r.brand, r.model].filter(Boolean).join(" ") || "—",
    },
    { title: "Serie", dataIndex: "serial_number", key: "serial_number", render: (v: string) => v || "—" },
    { title: "Cant.", dataIndex: "quantity", key: "quantity", width: 70 },
    {
      title: "Costo unit.",
      dataIndex: "unit_cost",
      key: "unit_cost",
      render: (v: number) => (v ? formatARS(v) : "—"),
    },
    {
      title: "Estado",
      dataIndex: "status",
      key: "status",
      render: (s: string) => <Tag color={STATUS_COLOR[s]}>{STATUS_LABEL[s]}</Tag>,
    },
    {
      title: "Condición",
      dataIndex: "condition",
      key: "condition",
      render: (c: string) => <Tag color={CONDITION_COLOR[c]}>{CONDITION_LABEL[c]}</Tag>,
    },
    {
      title: "Cliente asignado",
      dataIndex: "client_id",
      key: "client_id",
      render: (id: number) => {
        if (!id) return "—";
        const c = clients.find((x: any) => x.id === id);
        return c ? (c as any).full_name : `#${id}`;
      },
    },
    {
      title: "",
      key: "actions",
      align: "right" as const,
      render: (_: unknown, r: InventoryItem) => (
        <Space size={4}>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)} />
          <Popconfirm title="¿Eliminar ítem?" onConfirm={() => deleteMutation.mutate(r.id)} okText="Sí" cancelText="No">
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          <ToolOutlined /> Inventario de equipos
        </Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          Agregar ítem
        </Button>
      </div>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col><Statistic title="En stock" value={totalInStock} /></Col>
        <Col><Statistic title="Asignados" value={totalAssigned} /></Col>
        <Col><Statistic title="Valor en stock" value={totalCost} prefix="$" precision={0} /></Col>
      </Row>

      <Space style={{ marginBottom: 16 }} wrap>
        <Input.Search
          placeholder="Buscar por nombre, marca, serie..."
          style={{ width: 260 }}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          allowClear
        />
        <Select
          placeholder="Categoría"
          style={{ width: 160 }}
          allowClear
          value={categoryFilter}
          onChange={setCategoryFilter}
          options={CATEGORIES.map((c) => ({ value: c, label: c }))}
        />
        <Select
          placeholder="Estado"
          style={{ width: 140 }}
          allowClear
          value={statusFilter}
          onChange={setStatusFilter}
          options={Object.entries(STATUS_LABEL).map(([k, v]) => ({ value: k, label: v }))}
        />
      </Space>

      <Table
        dataSource={data}
        rowKey="id"
        loading={isLoading}
        columns={columns}
        size="small"
        pagination={{ pageSize: 50, showTotal: (t) => `${t} ítems` }}
      />

      <Modal
        title={editing ? "Editar ítem" : "Nuevo ítem"}
        open={modalOpen}
        onCancel={() => { setModalOpen(false); setEditing(null); form.resetFields(); }}
        onOk={() => form.submit()}
        confirmLoading={createMutation.isPending || updateMutation.isPending}
        width={600}
        destroyOnClose
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Row gutter={12}>
            <Col span={16}>
              <Form.Item name="name" label="Nombre" rules={[{ required: true }]}>
                <Input placeholder="ej: Antena Ubiquiti LiteBeam 5AC" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="quantity" label="Cantidad" rules={[{ required: true }]}>
                <InputNumber min={1} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="category" label="Categoría" rules={[{ required: true }]}>
                <Select
                  showSearch
                  options={CATEGORIES.map((c) => ({ value: c, label: c }))}
                  placeholder="Seleccioná o escribí"
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="unit_cost" label="Costo unitario (ARS)">
                <InputNumber min={0} precision={2} style={{ width: "100%" }} prefix="$" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="brand" label="Marca">
                <Input placeholder="Ubiquiti, TP-Link, MikroTik..." />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="model" label="Modelo">
                <Input placeholder="LiteBeam 5AC Gen2" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="serial_number" label="Número de serie">
            <Input placeholder="Opcional" />
          </Form.Item>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="condition" label="Condición">
                <Select options={Object.entries(CONDITION_LABEL).map(([k, v]) => ({ value: k, label: v }))} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="status" label="Estado">
                <Select options={Object.entries(STATUS_LABEL).map(([k, v]) => ({ value: k, label: v }))} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="client_id" label="Asignado a cliente">
            <Select
              showSearch
              allowClear
              placeholder="Opcional"
              filterOption={(input, opt) => (opt?.label as string ?? "").toLowerCase().includes(input.toLowerCase())}
              options={clients.map((c: any) => ({ value: c.id, label: c.full_name }))}
            />
          </Form.Item>
          <Form.Item name="notes" label="Notas">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

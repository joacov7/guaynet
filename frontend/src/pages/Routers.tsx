import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Badge,
  Button,
  Card,
  Col,
  Descriptions,
  Drawer,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Row,
  Space,
  Spin,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ApiOutlined,
  UnorderedListOutlined,
  SyncOutlined,
} from "@ant-design/icons";
import { routersApi } from "@/services/api";
import type { MikrotikQueue, Router, RouterStats } from "@/types";

const { Title } = Typography;

const statusTag: Record<string, React.ReactNode> = {
  online: <Badge status="success" text="Online" />,
  offline: <Badge status="error" text="Offline" />,
  unknown: <Badge status="default" text="Desconocido" />,
};

export default function Routers() {
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editRouter, setEditRouter] = useState<Router | null>(null);
  const [testResult, setTestResult] = useState<RouterStats | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [queuesDrawer, setQueuesDrawer] = useState<{ open: boolean; routerId: number | null }>({
    open: false,
    routerId: null,
  });
  const [form] = Form.useForm();

  const { data = [], isLoading } = useQuery({ queryKey: ["routers"], queryFn: routersApi.list });

  const { data: queues = [], isLoading: queuesLoading } = useQuery({
    queryKey: ["router-queues", queuesDrawer.routerId],
    queryFn: () => routersApi.queues(queuesDrawer.routerId!),
    enabled: queuesDrawer.open && queuesDrawer.routerId != null,
  });

  const saveMutation = useMutation({
    mutationFn: (values: any) =>
      editRouter ? routersApi.update(editRouter.id, values) : routersApi.create(values),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["routers"] });
      message.success(editRouter ? "Router actualizado" : "Router creado");
      closeModal();
    },
    onError: (err: any) => message.error(err.response?.data?.detail ?? "Error al guardar"),
  });

  const deleteMutation = useMutation({
    mutationFn: routersApi.delete,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["routers"] }); message.success("Router eliminado"); },
    onError: (err: any) => message.error(err.response?.data?.detail ?? "Error al eliminar"),
  });

  const syncMutation = useMutation({
    mutationFn: (id: number) => routersApi.syncClients(id),
    onSuccess: (data) => message.success(`Sincronizados: ${data.synced} clientes. Errores: ${data.errors.length}`),
    onError: (err: any) => message.error(err.response?.data?.detail ?? "Error de conexión"),
  });

  const openCreate = () => {
    setEditRouter(null);
    setTestResult(null);
    form.resetFields();
    form.setFieldsValue({ port: 8728, username: "admin" });
    setModalOpen(true);
  };

  const openEdit = (r: Router) => {
    setEditRouter(r);
    setTestResult(null);
    form.setFieldsValue({ ...r, password: "" });
    setModalOpen(true);
  };

  const closeModal = () => {
    setModalOpen(false);
    setEditRouter(null);
    setTestResult(null);
  };

  const handleTest = async () => {
    const values = form.getFieldsValue();
    if (!values.host || !values.username) {
      message.warning("Completá host y usuario antes de probar");
      return;
    }
    if (!editRouter && !values.password) {
      message.warning("Ingresá la contraseña");
      return;
    }
    setTestLoading(true);
    setTestResult(null);
    try {
      // Save first to get an ID, then test
      const saved = editRouter
        ? await routersApi.update(editRouter.id, values)
        : await routersApi.create(values);
      const stats = await routersApi.test(saved.id);
      setTestResult(stats);
      qc.invalidateQueries({ queryKey: ["routers"] });
      if (!editRouter) setEditRouter(saved);
    } catch (err: any) {
      message.error(err.response?.data?.detail ?? "No se pudo conectar");
    } finally {
      setTestLoading(false);
    }
  };

  const columns = [
    { title: "Nombre", dataIndex: "name", key: "name" },
    { title: "Host", dataIndex: "host", key: "host" },
    { title: "Puerto", dataIndex: "port", key: "port" },
    { title: "Ubicación", dataIndex: "location", key: "location", render: (v: string) => v ?? "—" },
    {
      title: "Estado",
      dataIndex: "status",
      key: "status",
      render: (s: string) => statusTag[s] ?? <Badge status="default" text={s} />,
    },
    { title: "Clientes", dataIndex: "client_count", key: "client_count", align: "right" as const },
    {
      title: "",
      key: "actions",
      align: "right" as const,
      render: (_: unknown, r: Router) => (
        <Space size={4}>
          <Tooltip title="Ver queues">
            <Button size="small" icon={<UnorderedListOutlined />} onClick={() => setQueuesDrawer({ open: true, routerId: r.id })} />
          </Tooltip>
          <Tooltip title="Sync todos los clientes">
            <Popconfirm title="¿Sincronizar todos los clientes al router?" onConfirm={() => syncMutation.mutate(r.id)}>
              <Button size="small" icon={<SyncOutlined />} />
            </Popconfirm>
          </Tooltip>
          <Tooltip title="Editar">
            <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)} />
          </Tooltip>
          <Popconfirm title="¿Eliminar router?" onConfirm={() => deleteMutation.mutate(r.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>Routers Mikrotik</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          Nuevo router
        </Button>
      </div>

      <Table loading={isLoading} dataSource={data} rowKey="id" columns={columns} size="small" pagination={false} />

      {/* Create / Edit Modal */}
      <Modal
        title={editRouter ? "Editar router" : "Nuevo router"}
        open={modalOpen}
        onCancel={closeModal}
        onOk={() => form.submit()}
        confirmLoading={saveMutation.isPending}
        width={560}
        footer={[
          <Button key="cancel" onClick={closeModal}>Cancelar</Button>,
          <Button key="test" icon={<ApiOutlined />} onClick={handleTest} loading={testLoading}>
            Probar conexión
          </Button>,
          <Button key="save" type="primary" onClick={() => form.submit()} loading={saveMutation.isPending}>
            {editRouter ? "Guardar" : "Crear"}
          </Button>,
        ]}
      >
        <Form form={form} layout="vertical" onFinish={(v) => saveMutation.mutate(v)}>
          <Form.Item name="name" label="Nombre" rules={[{ required: true }]}>
            <Input placeholder="Ej: Router Centro" />
          </Form.Item>
          <Row gutter={12}>
            <Col span={16}>
              <Form.Item name="host" label="Host / IP" rules={[{ required: true }]}>
                <Input placeholder="192.168.1.1" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="port" label="Puerto API">
                <InputNumber min={1} max={65535} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="username" label="Usuario" rules={[{ required: true }]}>
                <Input />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="password"
                label="Contraseña"
                rules={editRouter ? [] : [{ required: true }]}
              >
                <Input.Password placeholder={editRouter ? "(sin cambios)" : ""} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="location" label="Ubicación / Zona">
            <Input placeholder="Ej: Zona Norte" />
          </Form.Item>
          <Form.Item name="notes" label="Notas">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>

        {testResult && (
          <Card size="small" style={{ marginTop: 12, background: "#f6ffed", border: "1px solid #b7eb8f" }}>
            <Descriptions size="small" column={2} title="Conexión exitosa">
              <Descriptions.Item label="Identidad">{testResult.identity}</Descriptions.Item>
              <Descriptions.Item label="RouterOS">{testResult.version}</Descriptions.Item>
              <Descriptions.Item label="Uptime">{testResult.uptime}</Descriptions.Item>
              <Descriptions.Item label="CPU">{testResult.cpu_load}%</Descriptions.Item>
              <Descriptions.Item label="Board">{testResult.board_name || "—"}</Descriptions.Item>
            </Descriptions>
          </Card>
        )}
      </Modal>

      {/* Queues Drawer */}
      <Drawer
        title="Simple Queues"
        open={queuesDrawer.open}
        onClose={() => setQueuesDrawer({ open: false, routerId: null })}
        width={600}
      >
        {queuesLoading ? (
          <Spin />
        ) : (
          <Table
            dataSource={queues}
            rowKey="id"
            size="small"
            pagination={{ pageSize: 25 }}
            columns={[
              { title: "Nombre", dataIndex: "name", key: "name" },
              { title: "Target", dataIndex: "target", key: "target" },
              { title: "Límite", dataIndex: "max_limit", key: "max_limit" },
              {
                title: "Estado",
                dataIndex: "disabled",
                key: "disabled",
                render: (v: boolean) => <Tag color={v ? "orange" : "green"}>{v ? "Deshabilitada" : "Activa"}</Tag>,
              },
              {
                title: "Comentario",
                dataIndex: "comment",
                key: "comment",
                render: (v: string) => v ?? "—",
              },
            ]}
          />
        )}
      </Drawer>
    </div>
  );
}

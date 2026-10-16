import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Badge,
  Button,
  Card,
  Col,
  Descriptions,
  Divider,
  Drawer,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Progress,
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
  ThunderboltOutlined,
  BarChartOutlined,
} from "@ant-design/icons";
import { routersApi } from "@/services/api";
import type { MikrotikQueue, Router, RouterStats, RouterUtilization } from "@/types";

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
  const [utilizationDrawer, setUtilizationDrawer] = useState<{ open: boolean; router: Router | null }>({
    open: false,
    router: null,
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
    onSuccess: (data) => {
      if (data.errors.length > 0) {
        const first = (data.errors[0] as any)?.error ?? JSON.stringify(data.errors[0]);
        message.warning(`Sincronizados ${data.synced}. ${data.errors.length} error(es): ${first}`, 10);
      } else {
        message.success(`Sincronizados: ${data.synced} clientes`);
      }
    },
    onError: (err: any) => message.error(`Error MikroTik: ${err.response?.data?.detail ?? "Sin conexión"}`, 10),
  });

  const qosMutation = useMutation({
    mutationFn: (id: number) => routersApi.setupQos(id),
    onSuccess: (data: any) => {
      const parts = [];
      if (data.added) parts.push(`${data.added} agregadas`);
      if (data.enabled) parts.push(`${data.enabled} reactivadas`);
      if (data.skipped) parts.push(`${data.skipped} ya existían`);
      if (data.pcq_added) parts.push(`${data.pcq_added} PCQ`);
      message.success(`QoS: ${parts.join(", ") || "sin cambios"}`);
    },
    onError: (err: any) => message.error(err.response?.data?.detail ?? "Error al aplicar QoS"),
  });

  const { data: utilizationData, isLoading: utilizationLoading } = useQuery({
    queryKey: ["router-utilization", utilizationDrawer.router?.id],
    queryFn: () => routersApi.utilization(utilizationDrawer.router!.id),
    enabled: utilizationDrawer.open && utilizationDrawer.router != null,
    refetchInterval: (query: any) => (utilizationDrawer.open && !query.state.error) ? 5000 : false,
    retry: 1,
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
          <Tooltip title="Utilización">
            <Button size="small" icon={<BarChartOutlined />} onClick={() => setUtilizationDrawer({ open: true, router: r })} />
          </Tooltip>
          <Tooltip title="Sync todos los clientes">
            <Popconfirm title="¿Sincronizar todos los clientes al router?" onConfirm={() => syncMutation.mutate(r.id)}>
              <Button size="small" icon={<SyncOutlined />} />
            </Popconfirm>
          </Tooltip>
          <Tooltip title="Aplicar QoS">
            <Popconfirm
              title="¿Aplicar reglas QoS?"
              description="Agrega PCQ y mangle de priorización (VoIP > DNS > HTTPS > HTTP)."
              onConfirm={() => qosMutation.mutate(r.id)}
            >
              <Button size="small" icon={<ThunderboltOutlined />} />
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
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="latitude" label="Latitud">
                <InputNumber style={{ width: "100%" }} placeholder="-34.6037" step={0.0001} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="longitude" label="Longitud">
                <InputNumber style={{ width: "100%" }} placeholder="-58.3816" step={0.0001} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="notes" label="Notas">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Divider style={{ margin: "12px 0" }}>Capacidad del enlace (para cola padre)</Divider>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="uplink_download_mbps" label="Bajada del enlace (Mbps)">
                <InputNumber min={1} style={{ width: "100%" }} placeholder="Ej: 100" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="uplink_upload_mbps" label="Subida del enlace (Mbps)">
                <InputNumber min={1} style={{ width: "100%" }} placeholder="Ej: 50" />
              </Form.Item>
            </Col>
          </Row>
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

      {/* Utilization Drawer */}
      <Drawer
        title={`Utilización — ${utilizationDrawer.router?.name ?? ""}`}
        open={utilizationDrawer.open}
        onClose={() => setUtilizationDrawer({ open: false, router: null })}
        width={560}
      >
        {utilizationLoading ? (
          <Spin />
        ) : utilizationData ? (
          <UtilizationPanel data={utilizationData} />
        ) : null}
      </Drawer>
    </div>
  );
}

function UtilizationPanel({ data }: { data: RouterUtilization }) {
  const fmtMbps = (bps: number) => `${(bps / 1_000_000).toFixed(1)} Mbps`;
  const fmtGB = (bytes: number) => {
    if (bytes > 1e9) return `${(bytes / 1e9).toFixed(2)} GB`;
    if (bytes > 1e6) return `${(bytes / 1e6).toFixed(1)} MB`;
    return `${(bytes / 1e3).toFixed(0)} KB`;
  };

  return (
    <>
      {(data.uplink_download_mbps || data.uplink_upload_mbps) && (
        <Card size="small" title="Cola padre (guaynet-uplink)" style={{ marginBottom: 16 }}>
          <p style={{ margin: "0 0 8px", color: "#888", fontSize: 12 }}>
            Bytes acumulados de las queues de clientes vs capacidad configurada
          </p>
          {data.uplink_download_mbps && (
            <div style={{ marginBottom: 8 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
                <span>Bajada acumulada</span>
                <span>{fmtGB(data.queue_total_download_bytes)}</span>
              </div>
              <Progress
                percent={0}
                format={() => `límite ${data.uplink_download_mbps} Mbps`}
                strokeColor="#1677ff"
                size="small"
              />
            </div>
          )}
          {data.uplink_upload_mbps && (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
                <span>Subida acumulada</span>
                <span>{fmtGB(data.queue_total_upload_bytes)}</span>
              </div>
              <Progress
                percent={0}
                format={() => `límite ${data.uplink_upload_mbps} Mbps`}
                strokeColor="#52c41a"
                size="small"
              />
            </div>
          )}
        </Card>
      )}

      <Card size="small" title="Interfaces (se actualiza cada 5s)">
        <Table
          dataSource={data.interfaces}
          rowKey="name"
          size="small"
          pagination={false}
          columns={[
            {
              title: "Interfaz",
              dataIndex: "name",
              key: "name",
              render: (v: string, r: RouterUtilization["interfaces"][0]) => (
                <Space>
                  <Badge status={r.running ? "success" : "default"} />
                  {v}
                </Space>
              ),
            },
            { title: "Tipo", dataIndex: "type", key: "type", render: (v: string) => <Tag>{v}</Tag> },
            {
              title: "RX",
              key: "rx",
              render: (_: unknown, r: RouterUtilization["interfaces"][0]) =>
                r.rx_rate ? fmtMbps(r.rx_rate) : "—",
            },
            {
              title: "TX",
              key: "tx",
              render: (_: unknown, r: RouterUtilization["interfaces"][0]) =>
                r.tx_rate ? fmtMbps(r.tx_rate) : "—",
            },
          ]}
        />
      </Card>
    </>
  );
}

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Badge,
  Button,
  Col,
  Form,
  Input,
  InputNumber,
  Modal,
  Progress,
  Row,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import { PlusOutlined, StopOutlined } from "@ant-design/icons";
import { entrySessionsApi } from "@/services/security/api";
import type { EntrySession } from "@/types/security";

const { Title } = Typography;

function getRemainingMinutes(expiresAt: string): number {
  return Math.max(0, Math.round((new Date(expiresAt).getTime() - Date.now()) / 60000));
}

function SessionTimer({ session }: { session: EntrySession }) {
  const remaining = getRemainingMinutes(session.expires_at);
  const percent = Math.round((remaining / session.duration_minutes) * 100);
  const status = remaining <= 5 ? "exception" : remaining <= 15 ? "active" : "normal";
  return (
    <Space direction="vertical" size={2} style={{ width: "100%" }}>
      <Progress percent={percent} status={status} size="small" />
      <span style={{ fontSize: 12 }}>
        {remaining > 0 ? `${remaining} min restantes` : "Expirado"}
      </span>
    </Space>
  );
}

export default function EntrySecure() {
  const qc = useQueryClient();
  const [startOpen, setStartOpen] = useState(false);
  const [cancelTarget, setCancelTarget] = useState<EntrySession | null>(null);
  const [startForm] = Form.useForm();
  const [cancelForm] = Form.useForm();

  const { data: sessions = [], isLoading } = useQuery({
    queryKey: ["security-entry-sessions-active"],
    queryFn: () => entrySessionsApi.listActive(),
    refetchInterval: 30_000,
  });

  const startMutation = useMutation({
    mutationFn: (values: any) => entrySessionsApi.start(values),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["security-entry-sessions-active"] });
      message.success("Sesión iniciada");
      setStartOpen(false);
      startForm.resetFields();
    },
    onError: (e: any) => message.error(e.response?.data?.detail ?? "Error al iniciar sesión"),
  });

  const cancelMutation = useMutation({
    mutationFn: ({ id, pin }: { id: number; pin: string }) =>
      entrySessionsApi.cancel(id, pin),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["security-entry-sessions-active"] });
      message.success("Sesión cancelada");
      setCancelTarget(null);
      cancelForm.resetFields();
    },
    onError: (e: any) => message.error(e.response?.data?.detail ?? "PIN incorrecto"),
  });

  const columns = [
    { title: "ID", dataIndex: "id", key: "id", width: 60 },
    {
      title: "Suscripción",
      dataIndex: "subscription_id",
      key: "sub",
      render: (v: number) => `#${v}`,
    },
    {
      title: "Inicio",
      dataIndex: "created_at",
      key: "created_at",
      render: (v: string) => new Date(v).toLocaleTimeString("es-AR"),
    },
    {
      title: "Tiempo restante",
      key: "timer",
      render: (_: unknown, r: EntrySession) => <SessionTimer session={r} />,
    },
    {
      title: "Estado",
      dataIndex: "status",
      key: "status",
      render: (v: string) => (
        <Tag color={v === "active" ? "green" : v === "expired" ? "red" : "default"}>
          {v === "active" ? "Activa" : v === "expired" ? "Expirada" : v}
        </Tag>
      ),
    },
    {
      title: "",
      key: "actions",
      render: (_: unknown, r: EntrySession) =>
        r.status === "active" ? (
          <Button
            danger
            size="small"
            icon={<StopOutlined />}
            onClick={() => { setCancelTarget(r); cancelForm.resetFields(); }}
          >
            Cancelar
          </Button>
        ) : null,
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={3} style={{ margin: 0 }}>
            Entrada Segura
            {sessions.length > 0 && <Badge count={sessions.length} style={{ marginLeft: 12 }} />}
          </Title>
        </Col>
        <Col>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setStartOpen(true)}>
            Iniciar sesión
          </Button>
        </Col>
      </Row>

      {sessions.some((s) => getRemainingMinutes(s.expires_at) <= 5) && (
        <Alert
          type="warning"
          message="Hay sesiones que vencen en menos de 5 minutos"
          style={{ marginBottom: 16 }}
          showIcon
        />
      )}

      <Table
        dataSource={sessions}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        size="small"
        pagination={false}
        locale={{ emptyText: "No hay sesiones activas" }}
      />

      {/* Start modal */}
      <Modal
        open={startOpen}
        title="Iniciar Entrada Segura"
        onCancel={() => { setStartOpen(false); startForm.resetFields(); }}
        footer={null}
      >
        <Form form={startForm} layout="vertical" onFinish={(v) => startMutation.mutate(v)}>
          <Form.Item name="subscription_id" label="ID de suscripción" rules={[{ required: true }]}>
            <InputNumber style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="duration_minutes" label="Duración (minutos)" initialValue={60}>
            <InputNumber min={1} max={240} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={startMutation.isPending}>
                Iniciar
              </Button>
              <Button onClick={() => { setStartOpen(false); startForm.resetFields(); }}>Cancelar</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* Cancel modal — requires PIN */}
      <Modal
        open={!!cancelTarget}
        title={`Cancelar sesión #${cancelTarget?.id}`}
        onCancel={() => { setCancelTarget(null); cancelForm.resetFields(); }}
        footer={null}
      >
        <Alert
          type="info"
          message="Ingresá tu PIN de seguridad para cancelar la sesión"
          style={{ marginBottom: 16 }}
          showIcon
        />
        <Form
          form={cancelForm}
          layout="vertical"
          onFinish={(v) => cancelTarget && cancelMutation.mutate({ id: cancelTarget.id, pin: v.pin })}
        >
          <Form.Item name="pin" label="PIN" rules={[{ required: true, message: "Ingresá el PIN" }]}>
            <Input.Password maxLength={10} inputMode="numeric" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button danger htmlType="submit" loading={cancelMutation.isPending} icon={<StopOutlined />}>
                Cancelar sesión
              </Button>
              <Button onClick={() => { setCancelTarget(null); cancelForm.resetFields(); }}>
                Volver
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

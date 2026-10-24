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
  Row,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import { EyeOutlined, PlusOutlined, SettingOutlined } from "@ant-design/icons";
import { subscriptionsApi } from "@/services/security/api";
import type { SecuritySubscription, SecurityFeatureName } from "@/types/security";

const { Title } = Typography;

const statusColor: Record<string, string> = {
  active: "green",
  suspended: "orange",
  cancelled: "red",
  pending_install: "blue",
};

const statusLabel: Record<string, string> = {
  active: "Activo",
  suspended: "Suspendido",
  cancelled: "Cancelado",
  pending_install: "Pendiente instalación",
};

const featureLabels: Record<SecurityFeatureName, string> = {
  entry_secure:            "Entrada Segura",
  panic_button:            "Botón de pánico",
  duress_pin:              "PIN de coacción",
  safe_word:               "Palabra segura",
  vacation_mode:           "Modo ausencia",
  member_access:           "Miembros",
  camera_access:           "Cámaras",
  elderly_care:            "Adultos mayores",
  schedule_alerts:         "Alertas de horario",
  alert_confirmation:      "Confirmación de alerta",
  equipment_status:        "Estado de equipos",
  monitoring_certificate:  "Certificado de monitoreo",
  tech_survey:             "Encuesta técnica",
  event_history:           "Historial de eventos",
  monthly_report:          "Reporte mensual",
  weekly_report:           "Reporte semanal",
  digital_contract:        "Contrato digital",
};

export default function SecuritySubscriptions() {
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [featuresModal, setFeaturesModal] = useState<SecuritySubscription | null>(null);
  const [editModal, setEditModal] = useState<SecuritySubscription | null>(null);
  const [form] = Form.useForm();
  const [editForm] = Form.useForm();

  const { data = [], isLoading } = useQuery({
    queryKey: ["security-subscriptions"],
    queryFn: () => subscriptionsApi.list(),
  });

  const createMutation = useMutation({
    mutationFn: (values: any) => subscriptionsApi.create(values),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["security-subscriptions"] });
      message.success("Suscripción creada");
      setCreateOpen(false);
      form.resetFields();
    },
    onError: (e: any) => message.error(e.response?.data?.detail ?? "Error al crear"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Record<string, unknown> }) =>
      subscriptionsApi.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["security-subscriptions"] });
      message.success("Suscripción actualizada");
      setEditModal(null);
      editForm.resetFields();
    },
    onError: () => message.error("Error al actualizar suscripción"),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, feature_name, enabled }: { id: number; feature_name: SecurityFeatureName; enabled: boolean }) =>
      subscriptionsApi.toggleFeature(id, feature_name, enabled) as Promise<void>,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["security-subscriptions"] }),
    onError: () => message.error("Error al cambiar funcionalidad"),
  });

  const columns = [
    { title: "ID", dataIndex: "id", key: "id", width: 60 },
    {
      title: "Propiedad",
      dataIndex: "property_id",
      key: "property",
      render: (v: number) => `Prop. #${v}`,
    },
    {
      title: "Plan",
      dataIndex: "plan_id",
      key: "plan",
      render: (v: number) => `Plan #${v}`,
    },
    {
      title: "Estado",
      dataIndex: "status",
      key: "status",
      render: (v: string) => <Tag color={statusColor[v] ?? "default"}>{statusLabel[v] ?? v}</Tag>,
    },
    {
      title: "Notificación",
      key: "notification",
      render: (_: unknown, r: SecuritySubscription) => (
        <Tag color={r.client_telegram_id ? "blue" : "default"}>
          {r.client_telegram_id ? "Telegram cliente" : "Sin canal"}
        </Tag>
      ),
    },
    {
      title: "BEAT",
      dataIndex: "beat_account_id",
      key: "beat",
      render: (v: string | undefined) => v ?? <span style={{ color: "#aaa" }}>No configurado</span>,
    },
    {
      title: "Funcionalidades",
      key: "features",
      render: (_: unknown, r: SecuritySubscription) => {
        const enabled = r.features.filter((f) => f.enabled).length;
        return (
          <Tooltip title="Ver y editar funcionalidades">
            <Button
              size="small"
              icon={<SettingOutlined />}
              onClick={() => setFeaturesModal(r)}
            >
              {enabled}/{r.features.length}
            </Button>
          </Tooltip>
        );
      },
    },
    {
      title: "",
      key: "edit",
      render: (_: unknown, r: SecuritySubscription) => (
        <Button
          size="small"
          icon={<EyeOutlined />}
          onClick={() => {
            setEditModal(r);
            editForm.setFieldsValue({
              beat_account_id: r.beat_account_id,
              client_telegram_id: r.client_telegram_id,
              notes: r.notes,
            });
          }}
        >
          Editar
        </Button>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={3} style={{ margin: 0 }}>Abonados de Seguridad</Title>
        </Col>
        <Col>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
            Nueva suscripción
          </Button>
        </Col>
      </Row>

      <Table
        dataSource={data}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        size="small"
        pagination={{ pageSize: 20 }}
      />

      {/* Create modal */}
      <Modal
        open={createOpen}
        title="Nueva suscripción de seguridad"
        onCancel={() => { setCreateOpen(false); form.resetFields(); }}
        footer={null}
      >
        <Form form={form} layout="vertical" onFinish={(v) => createMutation.mutate(v)}>
          <Form.Item name="property_id" label="ID de propiedad" rules={[{ required: true }]}>
            <InputNumber style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="plan_id" label="ID de plan" rules={[{ required: true }]}>
            <InputNumber style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="beat_account_id" label="Cuenta BEAT (opcional)">
            <Input />
          </Form.Item>
          <Form.Item name="billing_day" label="Día de facturación" initialValue={1}>
            <InputNumber min={1} max={28} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="notes" label="Notas">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={createMutation.isPending}>
                Crear
              </Button>
              <Button onClick={() => { setCreateOpen(false); form.resetFields(); }}>Cancelar</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* Edit modal — beat_account_id, client_telegram_id, notes */}
      <Modal
        open={!!editModal}
        title={`Editar suscripción #${editModal?.id}`}
        onCancel={() => { setEditModal(null); editForm.resetFields(); }}
        footer={null}
      >
        <Form
          form={editForm}
          layout="vertical"
          onFinish={(v) => editModal && updateMutation.mutate({ id: editModal.id, data: v })}
        >
          <Form.Item name="beat_account_id" label="Cuenta BEAT">
            <Input placeholder="ID de cuenta en central BEAT" />
          </Form.Item>
          <Form.Item
            name="client_telegram_id"
            label="Telegram ID del cliente"
            tooltip="Chat ID de Telegram para notificar al cliente cuando no hay monitoreo operado"
          >
            <Input placeholder="Ej: 123456789" />
          </Form.Item>
          <Form.Item name="notes" label="Notas">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={updateMutation.isPending}>
                Guardar
              </Button>
              <Button onClick={() => { setEditModal(null); editForm.resetFields(); }}>Cancelar</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* Features modal */}
      <Modal
        open={!!featuresModal}
        title={`Funcionalidades — Suscripción #${featuresModal?.id}`}
        onCancel={() => setFeaturesModal(null)}
        footer={<Button onClick={() => setFeaturesModal(null)}>Cerrar</Button>}
        width={520}
      >
        {featuresModal && (
          <div>
            {featuresModal.features.map((f) => (
              <Row key={f.feature_name} justify="space-between" align="middle" style={{ padding: "6px 0", borderBottom: "1px solid #f0f0f0" }}>
                <Col>{featureLabels[f.feature_name as SecurityFeatureName] ?? f.feature_name}</Col>
                <Col>
                  <Switch
                    checked={f.enabled}
                    loading={toggleMutation.isPending}
                    onChange={(checked) =>
                      toggleMutation.mutate({
                        id: featuresModal.id,
                        feature_name: f.feature_name as SecurityFeatureName,
                        enabled: checked,
                      })
                    }
                  />
                </Col>
              </Row>
            ))}
          </div>
        )}
      </Modal>
    </div>
  );
}

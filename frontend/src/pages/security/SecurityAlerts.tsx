import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Col,
  Form,
  Input,
  Modal,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import { CheckOutlined, EyeOutlined } from "@ant-design/icons";
import { alertsApi } from "@/services/security/api";
import type { SecurityAlert } from "@/types/security";

const { Title } = Typography;

const statusColor: Record<string, string> = {
  new: "red",
  acknowledged: "orange",
  resolved: "green",
  false_alarm: "default",
};

const statusLabel: Record<string, string> = {
  new: "Nueva",
  acknowledged: "Atendiendo",
  resolved: "Resuelta",
  false_alarm: "Falsa alarma",
};

const alertTypeLabel: Record<string, string> = {
  PANIC: "🚨 Pánico",
  ENTRY_TIMEOUT: "⏰ Entrada expirada",
  DURESS: "🆘 Coacción",
  INTRUSION: "🔓 Intrusión",
  CHECKIN_MISSED: "❓ Check-in",
  INACTIVITY: "😴 Inactividad",
  SYSTEM_FAULT: "⚠️ Falla sistema",
  CONNECTION_LOST: "📡 Sin comunicación",
  SCHEDULE_VIOLATION: "🕐 Violación horario",
};

export default function SecurityAlerts() {
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [selected, setSelected] = useState<SecurityAlert | null>(null);
  const [form] = Form.useForm();

  const { data = [], isLoading } = useQuery({
    queryKey: ["security-alerts", statusFilter],
    queryFn: () => alertsApi.list(),
  });

  const filtered = statusFilter ? data.filter((a) => a.status === statusFilter) : data;

  const updateMutation = useMutation({
    mutationFn: ({ id, status, notes }: { id: number; status: string; notes?: string }) =>
      alertsApi.update(id, { status: status as SecurityAlert["status"], operator_notes: notes }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["security-alerts"] });
      message.success("Alerta actualizada");
      setSelected(null);
    },
    onError: () => message.error("Error al actualizar"),
  });

  const handleUpdate = (values: any) => {
    if (!selected) return;
    updateMutation.mutate({ id: selected.id, ...values });
  };

  const columns = [
    {
      title: "Tipo",
      dataIndex: "alert_type",
      key: "type",
      render: (v: string) => alertTypeLabel[v] ?? v,
    },
    {
      title: "Suscripción",
      dataIndex: "subscription_id",
      key: "sub",
      render: (v: number) => `#${v}`,
    },
    {
      title: "Estado",
      dataIndex: "status",
      key: "status",
      render: (v: string) => <Tag color={statusColor[v]}>{statusLabel[v] ?? v}</Tag>,
    },
    {
      title: "Disparada",
      dataIndex: "triggered_at",
      key: "triggered",
      render: (v: string) => new Date(v).toLocaleString("es-AR"),
    },
    {
      title: "Confirmación",
      key: "confirmation",
      render: (_: unknown, r: SecurityAlert) => {
        if (r.confirmation_sent_at && !r.resolved_at && r.status === "new") {
          const expires = r.confirmation_expires_at ? new Date(r.confirmation_expires_at) : null;
          const remaining = expires ? Math.max(0, Math.round((expires.getTime() - Date.now()) / 1000)) : 0;
          return remaining > 0
            ? <Tag color="orange">Esperando respuesta ({remaining}s)</Tag>
            : <Tag color="red">Sin respuesta</Tag>;
        }
        return <span style={{ color: "#aaa" }}>—</span>;
      },
    },
    {
      title: "Resuelta",
      dataIndex: "resolved_at",
      key: "resolved",
      render: (v: string | undefined) => (v ? new Date(v).toLocaleString("es-AR") : "—"),
    },
    {
      title: "",
      key: "actions",
      render: (_: unknown, r: SecurityAlert) =>
        r.status !== "resolved" && r.status !== "false_alarm" ? (
          <Button
            size="small"
            icon={<EyeOutlined />}
            onClick={() => { setSelected(r); form.setFieldsValue({ status: r.status, operator_notes: r.operator_notes }); }}
          >
            Gestionar
          </Button>
        ) : null,
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={3} style={{ margin: 0 }}>Alertas de Seguridad</Title>
        </Col>
        <Col>
          <Select
            placeholder="Filtrar por estado"
            allowClear
            style={{ width: 180 }}
            onChange={setStatusFilter}
            options={[
              { value: "new", label: "Nuevas" },
              { value: "acknowledged", label: "Atendiendo" },
              { value: "resolved", label: "Resueltas" },
              { value: "false_alarm", label: "Falsas alarmas" },
            ]}
          />
        </Col>
      </Row>

      <Table
        dataSource={filtered}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        size="small"
        pagination={{ pageSize: 20 }}
        rowClassName={(r) => r.status === "new" ? "ant-table-row-highlight" : ""}
      />

      <Modal
        open={!!selected}
        title="Gestionar alerta"
        onCancel={() => setSelected(null)}
        footer={null}
      >
        {selected && (
          <Form form={form} layout="vertical" onFinish={handleUpdate}>
            <Form.Item label="Tipo">
              <span>{alertTypeLabel[selected.alert_type] ?? selected.alert_type}</span>
            </Form.Item>
            <Form.Item name="status" label="Nuevo estado" rules={[{ required: true }]}>
              <Select
                options={[
                  { value: "acknowledged", label: "Atendiendo" },
                  { value: "resolved", label: "Resuelta" },
                  { value: "false_alarm", label: "Falsa alarma" },
                ]}
              />
            </Form.Item>
            <Form.Item name="operator_notes" label="Notas del operador">
              <Input.TextArea rows={3} />
            </Form.Item>
            <Form.Item>
              <Space>
                <Button type="primary" htmlType="submit" icon={<CheckOutlined />} loading={updateMutation.isPending}>
                  Guardar
                </Button>
                <Button onClick={() => setSelected(null)}>Cancelar</Button>
              </Space>
            </Form.Item>
          </Form>
        )}
      </Modal>
    </div>
  );
}

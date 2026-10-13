import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Card, Col, Divider, Form, InputNumber, Row, Space, Switch, Table, Tag, Typography, message } from "antd";
import dayjs from "dayjs";
import { automationsApi } from "@/services/api";

const { Title, Text } = Typography;

const JOB_LABEL: Record<string, string> = {
  auto_suspend: "Suspensión automática",
  auto_invoice: "Generación de facturas",
  whatsapp_reminder: "Recordatorio WhatsApp",
};

const STATUS_COLOR: Record<string, string> = {
  success: "green",
  error: "red",
  skipped: "default",
};

export default function Automations() {
  const qc = useQueryClient();
  const [form] = Form.useForm();

  const { data: settings, isLoading } = useQuery({
    queryKey: ["automation-settings"],
    queryFn: automationsApi.getSettings,
    onSuccess: (d) => form.setFieldsValue(d),
  });

  const { data: logs = [] } = useQuery({
    queryKey: ["automation-logs"],
    queryFn: () => automationsApi.getLogs(50),
    refetchInterval: 30_000,
  });

  const saveMutation = useMutation({
    mutationFn: automationsApi.updateSettings,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["automation-settings"] });
      message.success("Configuración guardada");
    },
    onError: () => message.error("Error al guardar"),
  });

  const runMutation = useMutation({
    mutationFn: automationsApi.runJob,
    onSuccess: (_, job) => {
      qc.invalidateQueries({ queryKey: ["automation-logs"] });
      message.success(`${JOB_LABEL[job]} iniciado`);
    },
    onError: () => message.error("Error al ejecutar"),
  });

  return (
    <div style={{ padding: 24 }}>
      <Title level={3} style={{ marginBottom: 24 }}>Automatizaciones</Title>

      <Form
        form={form}
        layout="vertical"
        initialValues={settings}
        onFinish={saveMutation.mutate}
      >
        <Row gutter={16}>
          {/* Auto-suspend */}
          <Col xs={24} md={8}>
            <Card
              title="🔒 Suspensión automática"
              extra={
                <Button
                  size="small"
                  loading={runMutation.isPending && runMutation.variables === "auto_suspend"}
                  onClick={() => runMutation.mutate("auto_suspend")}
                >
                  Ejecutar
                </Button>
              }
            >
              <Form.Item name="auto_suspend_enabled" valuePropName="checked" label="Habilitado">
                <Switch />
              </Form.Item>
              <Form.Item
                name="auto_suspend_days"
                label="Días de gracia tras vencimiento"
                rules={[{ required: true }]}
              >
                <InputNumber min={1} max={365} style={{ width: "100%" }} addonAfter="días" />
              </Form.Item>
              <Text type="secondary" style={{ fontSize: 12 }}>
                Suspende automáticamente los clientes con facturas vencidas que superen el período de gracia.
              </Text>
            </Card>
          </Col>

          {/* Auto-invoice */}
          <Col xs={24} md={8}>
            <Card
              title="📄 Generación de facturas"
              extra={
                <Button
                  size="small"
                  loading={runMutation.isPending && runMutation.variables === "auto_invoice"}
                  onClick={() => runMutation.mutate("auto_invoice")}
                >
                  Ejecutar
                </Button>
              }
            >
              <Form.Item name="auto_invoice_enabled" valuePropName="checked" label="Habilitado">
                <Switch />
              </Form.Item>
              <Text type="secondary" style={{ fontSize: 12 }}>
                Genera facturas para todos los clientes activos el 1° de cada mes a la 1:00 AM.
              </Text>
            </Card>
          </Col>

          {/* WhatsApp reminder */}
          <Col xs={24} md={8}>
            <Card
              title="💬 Recordatorio WhatsApp"
              extra={
                <Button
                  size="small"
                  loading={runMutation.isPending && runMutation.variables === "whatsapp_reminder"}
                  onClick={() => runMutation.mutate("whatsapp_reminder")}
                >
                  Ejecutar
                </Button>
              }
            >
              <Form.Item name="auto_whatsapp_enabled" valuePropName="checked" label="Habilitado">
                <Switch />
              </Form.Item>
              <Form.Item
                name="whatsapp_reminder_days"
                label="Días antes del vencimiento"
                rules={[{ required: true }]}
              >
                <InputNumber min={1} max={30} style={{ width: "100%" }} addonAfter="días" />
              </Form.Item>
              <Text type="secondary" style={{ fontSize: 12 }}>
                Envía un recordatorio WhatsApp a los clientes N días antes del vencimiento de su factura.
              </Text>
            </Card>
          </Col>
        </Row>

        <div style={{ marginTop: 16, textAlign: "right" }}>
          <Button type="primary" htmlType="submit" loading={saveMutation.isPending}>
            Guardar configuración
          </Button>
        </div>
      </Form>

      <Divider />

      <Title level={4}>Historial de ejecuciones</Title>
      <Table
        dataSource={logs}
        rowKey="id"
        size="small"
        pagination={{ pageSize: 20 }}
        columns={[
          {
            title: "Fecha",
            dataIndex: "created_at",
            render: (v) => dayjs(v).format("DD/MM/YY HH:mm"),
            width: 130,
          },
          {
            title: "Tarea",
            dataIndex: "job",
            render: (v) => JOB_LABEL[v] ?? v,
          },
          {
            title: "Estado",
            dataIndex: "status",
            render: (v) => <Tag color={STATUS_COLOR[v] ?? "default"}>{v}</Tag>,
            width: 100,
          },
          {
            title: "Afectados",
            dataIndex: "affected",
            width: 90,
            align: "center",
          },
          {
            title: "Detalle",
            dataIndex: "message",
            ellipsis: true,
          },
        ]}
      />
    </div>
  );
}

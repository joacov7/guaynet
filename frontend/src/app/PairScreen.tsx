import { useState } from "react";
import { Alert, Button, Card, Form, Input, Typography } from "antd";
import { SafetyCertificateOutlined } from "@ant-design/icons";
import axios from "axios";

const { Title, Text, Paragraph } = Typography;

export default function PairScreen({
  notice,
  onPaired,
}: {
  notice?: string | null;
  onPaired: (credential: string) => Promise<void>;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form] = Form.useForm();

  async function pair(values: { portal_link: string; pin: string; device_name: string }) {
    setLoading(true);
    setError(null);
    try {
      const r = await axios.post<{ credential: string }>("/api/v1/mobile/pair", {
        ...values,
        platform: "android",
      });
      await onPaired(r.data.credential);
    } catch (e: any) {
      const d = e.response?.data?.detail;
      setError(
        Array.isArray(d) ? d[0]?.msg : d ?? "No se pudo conectar con el servidor. Revisá tu conexión.",
      );
      form.setFieldValue("pin", "");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ maxWidth: 420, margin: "0 auto", padding: "32px 16px" }}>
      <div style={{ textAlign: "center", marginBottom: 24 }}>
        <SafetyCertificateOutlined style={{ fontSize: 40, color: "#1677ff" }} />
        <Title level={3} style={{ margin: "8px 0 0" }}>Guaynet Seguridad</Title>
        <Text type="secondary">Vinculá este teléfono con tu alarma</Text>
      </div>
      {notice && <Alert type="warning" showIcon message={notice} style={{ marginBottom: 16 }} />}
      <Card>
        <Paragraph type="secondary" style={{ fontSize: 13 }}>
          Pegá el enlace del portal que te enviamos por Telegram y confirmá con el PIN de tu alarma.
          Si no tenés el enlace, pedíselo a la central.
        </Paragraph>
        {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 12 }} />}
        <Form
          form={form}
          layout="vertical"
          requiredMark={false}
          initialValues={{ device_name: "Mi teléfono" }}
          onFinish={pair}
        >
          <Form.Item name="portal_link" label="Enlace del portal" rules={[{ required: true, message: "Pegá el enlace" }]}>
            <Input.TextArea autoSize={{ minRows: 2, maxRows: 4 }} placeholder="https://…/portal?token=…" />
          </Form.Item>
          <Form.Item name="pin" label="PIN de la alarma" rules={[{ required: true, message: "Ingresá el PIN" }]}>
            <Input.Password inputMode="numeric" autoComplete="off" maxLength={12} />
          </Form.Item>
          <Form.Item name="device_name" label="Nombre de este teléfono" rules={[{ required: true }]}>
            <Input maxLength={100} />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={loading}>
            Vincular
          </Button>
        </Form>
      </Card>
    </div>
  );
}

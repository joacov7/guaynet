import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  Radio,
  Space,
  Typography,
  message,
} from "antd";
import { adminApi, notificationsApi } from "@/services/api";

const { Title, Text } = Typography;
const { TextArea } = Input;

export default function Settings() {
  const qc = useQueryClient();
  const [form] = Form.useForm();
  const [waForm] = Form.useForm();
  const [mpForm] = Form.useForm();
  const [testPhone, setTestPhone] = useState("");
  const [testMsg, setTestMsg] = useState("");
  const [testing, setTesting] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["system-config"],
    queryFn: adminApi.getConfig,
  });

  useEffect(() => {
    if (data) {
      form.setFieldsValue(data);
      waForm.setFieldsValue({
        twilio_account_sid: data.twilio_account_sid ?? "",
        twilio_auth_token: data.twilio_auth_token ?? "",
        twilio_whatsapp_from: data.twilio_whatsapp_from ?? "whatsapp:+14155238886",
        whatsapp_reminder_template: data.whatsapp_reminder_template ??
          "Hola {nombre}, te recordamos que tenés una factura de ${monto} con vencimiento {vencimiento} pendiente de pago.",
      });
      mpForm.setFieldsValue({
        mp_access_token: data.mp_access_token ?? "",
        mp_public_key: data.mp_public_key ?? "",
        company_name: data.company_name ?? "",
        company_address: data.company_address ?? "",
        company_cuit: data.company_cuit ?? "",
      });
    }
  }, [data, form, waForm, mpForm]);

  const mutation = useMutation({
    mutationFn: adminApi.updateConfig,
    onSuccess: (updated) => {
      qc.setQueryData(["system-config"], updated);
      message.success("Configuración guardada");
    },
    onError: () => message.error("Error al guardar"),
  });

  const suspensionAction = Form.useWatch("suspension_action", form);

  async function handleTestWhatsapp() {
    if (!testPhone || !testMsg) return;
    setTesting(true);
    try {
      await notificationsApi.sendOne(0, testMsg, testPhone);
      message.success("Mensaje enviado");
    } catch (e: any) {
      message.error(e.response?.data?.detail ?? "Error al enviar");
    } finally {
      setTesting(false);
    }
  }

  return (
    <div style={{ padding: 24, maxWidth: 640 }}>
      <Title level={4}>Configuración del sistema</Title>

      <Card title="Suspensión de clientes" loading={isLoading} style={{ marginBottom: 16 }}>
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 20 }}
          message="Define qué acción se aplica en MikroTik cuando un cliente es suspendido (manual o automáticamente por falta de pago)."
        />
        <Form
          form={form}
          layout="vertical"
          onFinish={(values) => mutation.mutate(values)}
          initialValues={{ suspension_action: "disable", suspension_speed: "64k" }}
        >
          <Form.Item name="suspension_action" label="Acción al suspender">
            <Radio.Group>
              <Space direction="vertical">
                <Radio value="disable">
                  <Text strong>Deshabilitar queue</Text>
                  <br />
                  <Text type="secondary">El cliente pierde el acceso completamente (disabled=yes en el queue).</Text>
                </Radio>
                <Radio value="throttle">
                  <Text strong>Reducir velocidad (throttle)</Text>
                  <br />
                  <Text type="secondary">El cliente mantiene conexión pero con velocidad mínima. Útil para mostrar una página de aviso.</Text>
                </Radio>
              </Space>
            </Radio.Group>
          </Form.Item>

          {suspensionAction === "throttle" && (
            <Form.Item
              name="suspension_speed"
              label="Velocidad al suspender"
              extra="Formato MikroTik: 64k, 128k, 512k, 1M, etc. Se aplica igual para subida y bajada."
              rules={[{ required: true, message: "Ingresá la velocidad" }]}
            >
              <Input style={{ width: 160 }} placeholder="64k" />
            </Form.Item>
          )}

          <Form.Item style={{ marginTop: 8 }}>
            <Button type="primary" htmlType="submit" loading={mutation.isPending}>
              Guardar cambios
            </Button>
          </Form.Item>
        </Form>
      </Card>

      <Card title="WhatsApp (Twilio)" loading={isLoading}>
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 20 }}
          message={
            <>
              Necesitás una cuenta de Twilio con WhatsApp habilitado.{" "}
              Variables disponibles en el template: <Text code>{"{nombre}"}</Text>,{" "}
              <Text code>{"{monto}"}</Text>, <Text code>{"{vencimiento}"}</Text>.
            </>
          }
        />
        <Form
          form={waForm}
          layout="vertical"
          onFinish={(values) => mutation.mutate(values)}
        >
          <Form.Item name="twilio_account_sid" label="Account SID">
            <Input placeholder="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" />
          </Form.Item>
          <Form.Item name="twilio_auth_token" label="Auth Token">
            <Input.Password placeholder="Tu auth token de Twilio" />
          </Form.Item>
          <Form.Item name="twilio_whatsapp_from" label="Número WhatsApp sender" extra="Ej: whatsapp:+14155238886 (sandbox de Twilio)">
            <Input placeholder="whatsapp:+14155238886" />
          </Form.Item>
          <Form.Item name="whatsapp_reminder_template" label="Template de recordatorio">
            <TextArea rows={3} placeholder="Hola {nombre}, te recordamos..." />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={mutation.isPending}>
              Guardar configuración WhatsApp
            </Button>
          </Form.Item>
        </Form>

        <div style={{ borderTop: "1px solid #f0f0f0", paddingTop: 16, marginTop: 8 }}>
          <Text strong>Envío de prueba</Text>
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <Input
              placeholder="+5491112345678"
              value={testPhone}
              onChange={(e) => setTestPhone(e.target.value)}
              style={{ width: 200 }}
            />
            <Input
              placeholder="Mensaje de prueba"
              value={testMsg}
              onChange={(e) => setTestMsg(e.target.value)}
              style={{ flex: 1 }}
            />
            <Button loading={testing} onClick={handleTestWhatsapp} disabled={!testPhone || !testMsg}>
              Enviar prueba
            </Button>
          </div>
        </div>
      </Card>

      <Card title="MercadoPago" loading={isLoading} style={{ marginTop: 16 }}>
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 20 }}
          message={
            <>
              Credenciales de MercadoPago para cobros online.{" "}
              Obtené tu Access Token desde{" "}
              <Text strong>mercadopago.com → Tu negocio → Credenciales</Text>.
            </>
          }
        />
        <Form
          form={mpForm}
          layout="vertical"
          onFinish={(values) => mutation.mutate(values)}
        >
          <Form.Item name="mp_access_token" label="Access Token (producción o sandbox)">
            <Input.Password placeholder="APP_USR-..." />
          </Form.Item>
          <Form.Item name="mp_public_key" label="Public Key">
            <Input placeholder="APP_USR-..." />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0 }}>
            <Button type="primary" htmlType="submit" loading={mutation.isPending}>
              Guardar credenciales MP
            </Button>
          </Form.Item>
        </Form>
      </Card>

      <Card title="Empresa / Datos para PDF" loading={isLoading} style={{ marginTop: 16 }}>
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 20 }}
          message="Estos datos aparecen en el encabezado de los PDFs de facturas."
        />
        <Form
          form={mpForm}
          layout="vertical"
          onFinish={(values) => mutation.mutate(values)}
        >
          <Form.Item name="company_name" label="Nombre de la empresa">
            <Input placeholder="Mi ISP S.A." />
          </Form.Item>
          <Form.Item name="company_address" label="Dirección">
            <Input placeholder="Calle 123, Ciudad, Provincia" />
          </Form.Item>
          <Form.Item name="company_cuit" label="CUIT">
            <Input placeholder="20-12345678-9" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={mutation.isPending}>
              Guardar datos empresa
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}

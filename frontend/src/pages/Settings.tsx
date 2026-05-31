import { useEffect } from "react";
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
import { adminApi } from "@/services/api";

const { Title, Text } = Typography;

export default function Settings() {
  const qc = useQueryClient();
  const [form] = Form.useForm();

  const { data, isLoading } = useQuery({
    queryKey: ["system-config"],
    queryFn: adminApi.getConfig,
  });

  useEffect(() => {
    if (data) form.setFieldsValue(data);
  }, [data, form]);

  const mutation = useMutation({
    mutationFn: adminApi.updateConfig,
    onSuccess: (updated) => {
      qc.setQueryData(["system-config"], updated);
      message.success("Configuración guardada");
    },
    onError: () => message.error("Error al guardar"),
  });

  const suspensionAction = Form.useWatch("suspension_action", form);

  return (
    <div style={{ padding: 24, maxWidth: 600 }}>
      <Title level={4}>Configuración del sistema</Title>

      <Card title="Suspensión de clientes" loading={isLoading}>
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
    </div>
  );
}

import { useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Card,
  Col,
  DatePicker,
  Form,
  Input,
  InputNumber,
  Row,
  Select,
  Space,
  Spin,
  Typography,
  message,
} from "antd";
import dayjs from "dayjs";
import { clientsApi, plansApi, routersApi } from "@/services/api";
import type { Client } from "@/types";

const { Title } = Typography;

export default function ClientForm() {
  const { id } = useParams<{ id: string }>();
  const isEdit = Boolean(id);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [form] = Form.useForm();

  const { data: client, isLoading: loadingClient } = useQuery({
    queryKey: ["client", id],
    queryFn: () => clientsApi.get(Number(id)),
    enabled: isEdit,
  });

  const { data: plans = [] } = useQuery({ queryKey: ["plans"], queryFn: () => plansApi.list() });
  const { data: routers = [] } = useQuery({ queryKey: ["routers"], queryFn: routersApi.list });

  useEffect(() => {
    if (client) {
      form.setFieldsValue({
        ...client,
        service_start_date: client.service_start_date ? dayjs(client.service_start_date) : undefined,
      });
    }
  }, [client, form]);

  const createMutation = useMutation({
    mutationFn: clientsApi.create,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["clients"] });
      message.success("Cliente creado y sincronizado con Mikrotik");
      navigate("/clients");
    },
    onError: (err: any) => message.error(err.response?.data?.detail ?? "Error al crear cliente"),
  });

  const updateMutation = useMutation({
    mutationFn: (data: Partial<Client>) => clientsApi.update(Number(id), data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["clients"] });
      qc.invalidateQueries({ queryKey: ["client", id] });
      message.success("Cliente actualizado");
      navigate("/clients");
    },
    onError: (err: any) => message.error(err.response?.data?.detail ?? "Error al actualizar"),
  });

  const onFinish = (values: any) => {
    const payload = {
      ...values,
      service_start_date: values.service_start_date
        ? values.service_start_date.format("YYYY-MM-DD")
        : undefined,
    };
    if (isEdit) updateMutation.mutate(payload);
    else createMutation.mutate(payload);
  };

  if (isEdit && loadingClient) return <Spin />;

  const isSubmitting = createMutation.isPending || updateMutation.isPending;

  return (
    <div style={{ maxWidth: 900 }}>
      <div style={{ display: "flex", alignItems: "center", marginBottom: 16, gap: 8 }}>
        <Button onClick={() => navigate("/clients")}>Volver</Button>
        <Title level={4} style={{ margin: 0 }}>
          {isEdit ? "Editar cliente" : "Nuevo cliente"}
        </Title>
      </div>

      <Form form={form} layout="vertical" onFinish={onFinish} initialValues={{ billing_day: 1, status: "active" }}>
        <Row gutter={16}>
          <Col span={24}>
            <Card title="Datos personales" size="small" style={{ marginBottom: 16 }}>
              <Row gutter={16}>
                <Col xs={24} sm={12}>
                  <Form.Item name="first_name" label="Nombre" rules={[{ required: true }]}><Input /></Form.Item>
                </Col>
                <Col xs={24} sm={12}>
                  <Form.Item name="last_name" label="Apellido" rules={[{ required: true }]}><Input /></Form.Item>
                </Col>
                <Col xs={24} sm={8}>
                  <Form.Item name="dni" label="DNI"><Input /></Form.Item>
                </Col>
                <Col xs={24} sm={8}>
                  <Form.Item name="cuit" label="CUIT"><Input /></Form.Item>
                </Col>
                <Col xs={24} sm={8}>
                  <Form.Item name="phone" label="Teléfono"><Input /></Form.Item>
                </Col>
                <Col xs={24} sm={12}>
                  <Form.Item name="email" label="Email"><Input type="email" /></Form.Item>
                </Col>
                <Col xs={24} sm={12}>
                  <Form.Item name="address" label="Dirección"><Input /></Form.Item>
                </Col>
                <Col span={24}>
                  <Form.Item name="notes" label="Notas"><Input.TextArea rows={2} /></Form.Item>
                </Col>
              </Row>
            </Card>
          </Col>

          <Col span={24}>
            <Card title="Configuración de red" size="small" style={{ marginBottom: 16 }}>
              <Row gutter={16}>
                <Col xs={24} sm={8}>
                  <Form.Item
                    name="ip_address"
                    label="Dirección IP"
                    rules={[
                      { required: true },
                      { pattern: /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/, message: "IP inválida" },
                    ]}
                  >
                    <Input placeholder="192.168.1.100" />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={8}>
                  <Form.Item name="mac_address" label="MAC Address">
                    <Input placeholder="AA:BB:CC:DD:EE:FF" />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={8}>
                  <Form.Item name="plan_id" label="Plan" rules={[{ required: true }]}>
                    <Select
                      options={plans.map((p) => ({
                        value: p.id,
                        label: `${p.name} — ${p.download_mbps}/${p.upload_mbps} Mbps ($${p.price})`,
                      }))}
                    />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={8}>
                  <Form.Item name="router_id" label="Router Mikrotik" rules={[{ required: true }]}>
                    <Select
                      options={routers.map((r) => ({
                        value: r.id,
                        label: r.location ? `${r.name} (${r.location})` : r.name,
                      }))}
                    />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={8}>
                  <Form.Item name="status" label="Estado">
                    <Select
                      options={[
                        { value: "active", label: "Activo" },
                        { value: "suspended", label: "Suspendido" },
                        { value: "cancelled", label: "Cancelado" },
                      ]}
                    />
                  </Form.Item>
                </Col>
              </Row>
            </Card>
          </Col>

          <Col span={24}>
            <Card title="Facturación" size="small" style={{ marginBottom: 16 }}>
              <Row gutter={16}>
                <Col xs={24} sm={8}>
                  <Form.Item name="service_start_date" label="Inicio del servicio">
                    <DatePicker style={{ width: "100%" }} format="DD/MM/YYYY" />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={8}>
                  <Form.Item name="billing_day" label="Día de facturación">
                    <InputNumber min={1} max={28} style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
              </Row>
            </Card>
          </Col>
        </Row>

        <Space>
          <Button onClick={() => navigate("/clients")}>Cancelar</Button>
          <Button type="primary" htmlType="submit" loading={isSubmitting}>
            {isEdit ? "Guardar cambios" : "Crear cliente"}
          </Button>
        </Space>
      </Form>
    </div>
  );
}

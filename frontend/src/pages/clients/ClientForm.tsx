import { useEffect } from "react";
import { useNavigate, useParams, useLocation } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
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
import { clientsApi, plansApi, routersApi, ubiquitiApi, zonesApi } from "@/services/api";
import type { Client } from "@/types";

const { Title } = Typography;

export default function ClientForm() {
  const { id } = useParams<{ id: string }>();
  const isEdit = Boolean(id);
  const navigate = useNavigate();
  const location = useLocation();
  const qc = useQueryClient();
  const [form] = Form.useForm();

  const { data: client, isLoading: loadingClient } = useQuery({
    queryKey: ["client", id],
    queryFn: () => clientsApi.get(Number(id)),
    enabled: isEdit,
  });

  const { data: plans = [] } = useQuery({ queryKey: ["plans"], queryFn: () => plansApi.list() });
  const { data: routers = [] } = useQuery({ queryKey: ["routers"], queryFn: routersApi.list });
  const { data: freeDevices = [] } = useQuery({ queryKey: ["ubiquiti-free"], queryFn: ubiquitiApi.listFree });
  const { data: zones = [] } = useQuery({ queryKey: ["zones"], queryFn: zonesApi.list });
  const { data: currentDevice } = useQuery({
    queryKey: ["ubiquiti", client?.ubiquiti_device_id],
    queryFn: () => ubiquitiApi.get(client!.ubiquiti_device_id!),
    enabled: Boolean(client?.ubiquiti_device_id),
  });

  useEffect(() => {
    if (client) {
      form.setFieldsValue({
        ...client,
        service_start_date: client.service_start_date ? dayjs(client.service_start_date) : undefined,
      });
    }
  }, [client, form]);

  useEffect(() => {
    if (!isEdit && location.state) {
      const { ip, mac } = location.state as { ip?: string; mac?: string };
      if (ip) form.setFieldValue("ip_address", ip);
      if (mac) form.setFieldValue("mac_address", mac);
    }
  }, [isEdit, location.state, form]);

  const createMutation = useMutation({
    mutationFn: clientsApi.create,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["clients"] });
      message.success("Cliente creado y sincronizado con Mikrotik");
      navigate("/clients");
    },
    onError: (err: any) => {
      message.error(err.response?.data?.detail ?? "Error al crear cliente");
    },
  });

  const updateMutation = useMutation({
    mutationFn: (data: Partial<Client>) => clientsApi.update(Number(id), data),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["clients"] });
      qc.invalidateQueries({ queryKey: ["client", id] });
      if (data.mikrotik_error) {
        message.warning(`Guardado. Error MikroTik: ${data.mikrotik_error}`, 8);
      } else {
        message.success(`Cliente actualizado${data.mikrotik_sync ? ` · MT: ${data.mikrotik_sync}` : ""}`, 6);
      }
      navigate("/clients");
    },
    onError: (err: any) => {
      message.error(err.response?.data?.detail ?? "Error al actualizar");
    },
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
          {/* Personal data */}
          <Col span={24}>
            <Card title="Datos personales" size="small" style={{ marginBottom: 16 }}>
              <Row gutter={16}>
                <Col xs={24} sm={12}>
                  <Form.Item name="first_name" label="Nombre" rules={[{ required: true }]}>
                    <Input />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12}>
                  <Form.Item name="last_name" label="Apellido" rules={[{ required: true }]}>
                    <Input />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={8}>
                  <Form.Item name="dni" label="DNI">
                    <Input />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={8}>
                  <Form.Item name="cuit" label="CUIT">
                    <Input />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={8}>
                  <Form.Item name="phone" label="Teléfono">
                    <Input />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12}>
                  <Form.Item name="email" label="Email">
                    <Input type="email" />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12}>
                  <Form.Item name="address" label="Dirección">
                    <Input />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={6}>
                  <Form.Item name="latitude" label="Latitud">
                    <InputNumber style={{ width: "100%" }} placeholder="-34.6037" step={0.0001} />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={6}>
                  <Form.Item name="longitude" label="Longitud">
                    <InputNumber style={{ width: "100%" }} placeholder="-58.3816" step={0.0001} />
                  </Form.Item>
                </Col>
                <Col span={24}>
                  <Form.Item name="notes" label="Notas">
                    <Input.TextArea rows={2} />
                  </Form.Item>
                </Col>
              </Row>
            </Card>
          </Col>

          {/* Network data */}
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
                <Col xs={24} sm={8}>
                  <Form.Item name="zone_id" label="Zona">
                    <Select
                      allowClear
                      placeholder="Sin zona"
                      options={zones.map((z) => ({
                        value: z.id,
                        label: z.name,
                      }))}
                    />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={8}>
                  <Form.Item name="ubiquiti_device_id" label="Antena Ubiquiti">
                    <Select
                      allowClear
                      placeholder="Sin antena asignada"
                      options={[
                        ...(currentDevice && !freeDevices.find((d) => d.id === currentDevice.id)
                          ? [{ value: currentDevice.id, label: `${currentDevice.name} (${currentDevice.host}) [actual]` }]
                          : []),
                        ...freeDevices.map((d) => ({
                          value: d.id,
                          label: `${d.name} (${d.host})`,
                        })),
                      ]}
                    />
                  </Form.Item>
                </Col>
              </Row>
            </Card>
          </Col>

          {/* Billing */}
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

          {/* PPPoE */}
          <Col span={24}>
            <Card title="PPPoE (opcional)" size="small" style={{ marginBottom: 16 }}>
              <Row gutter={16}>
                <Col xs={24} sm={12}>
                  <Form.Item name="pppoe_username" label="Usuario PPPoE">
                    <Input placeholder="cliente01" autoComplete="off" />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12}>
                  <Form.Item name="pppoe_password" label="Contraseña PPPoE">
                    <Input.Password placeholder="Dejar en blanco para no cambiar" autoComplete="new-password" />
                  </Form.Item>
                </Col>
              </Row>
            </Card>
          </Col>

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

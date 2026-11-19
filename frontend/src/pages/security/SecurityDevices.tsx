import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Col,
  DatePicker,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Result,
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
import {
  ArrowLeftOutlined,
  ClusterOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  StopOutlined,
  UndoOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";
import { devicesApi } from "@/services/security/api";
import type { DeviceZone, SecurityDevice, SecurityDeviceType } from "@/types/security";

const { Title, Text } = Typography;

const DEVICE_LABELS: Record<SecurityDeviceType, string> = {
  panel:           "Panel de alarma",
  sensor_motion:   "Sensor de movimiento",
  sensor_magnetic: "Sensor magnético",
  sensor_smoke:    "Detector de humo",
  sensor_glass:    "Sensor rotura de vidrio",
  siren:           "Sirena",
  keypad:          "Teclado",
  camera:          "Cámara",
  communicator:    "Comunicador GSM/IP",
  other:           "Otro",
};

const ZONE_TYPES = [
  { value: "instant",  label: "Instantánea" },
  { value: "delayed",  label: "Retardada (entrada)" },
  { value: "24h",      label: "24 horas" },
  { value: "fire",     label: "Incendio" },
  { value: "panic",    label: "Pánico" },
];

function warrantyTag(d: SecurityDevice) {
  if (!d.install_date || !d.warranty_months) return <Text type="secondary">—</Text>;
  const until = dayjs(d.install_date).add(d.warranty_months, "month");
  const daysLeft = until.diff(dayjs(), "day");
  const label = until.format("DD/MM/YYYY");
  if (daysLeft < 0) return <Tag>Vencida {label}</Tag>;
  if (daysLeft <= 60) return <Tag color="orange">Vence {label}</Tag>;
  return <Tag color="green">Hasta {label}</Tag>;
}

export default function SecurityDevices() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const subscriptionId = Number(params.get("subscription_id"));

  const [editing, setEditing] = useState<SecurityDevice | "new" | null>(null);
  const [zonesFor, setZonesFor] = useState<SecurityDevice | null>(null);
  const [form] = Form.useForm();
  const [zonesForm] = Form.useForm<{ zones: DeviceZone[] }>();

  const queryKey = ["security-devices", subscriptionId];
  const { data: devices = [], isLoading } = useQuery({
    queryKey,
    queryFn: () => devicesApi.list(subscriptionId),
    enabled: subscriptionId > 0,
  });

  const onError = (e: any) => message.error(e.response?.data?.detail ?? "Error al guardar");

  const saveMutation = useMutation({
    mutationFn: (values: any) => {
      const payload = {
        ...values,
        install_date: values.install_date ? values.install_date.format("YYYY-MM-DD") : null,
      };
      return editing === "new"
        ? devicesApi.create({ ...payload, subscription_id: subscriptionId })
        : devicesApi.update((editing as SecurityDevice).id, payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey });
      message.success("Equipo guardado");
      setEditing(null);
      form.resetFields();
    },
    onError,
  });

  const toggleActiveMutation = useMutation({
    mutationFn: (d: SecurityDevice) => devicesApi.update(d.id, { is_active: !d.is_active }),
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey });
      message.success(d.is_active ? "Equipo reactivado" : "Equipo dado de baja");
    },
    onError,
  });

  const zonesMutation = useMutation({
    mutationFn: (zones: DeviceZone[]) => devicesApi.replaceZones(zonesFor!.id, zones),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey });
      message.success("Zonas guardadas");
      setZonesFor(null);
    },
    onError,
  });

  const openEdit = (d: SecurityDevice | "new") => {
    setEditing(d);
    form.resetFields();
    if (d !== "new") {
      form.setFieldsValue({ ...d, install_date: d.install_date ? dayjs(d.install_date) : undefined });
    }
  };

  const openZones = (d: SecurityDevice) => {
    setZonesFor(d);
    zonesForm.setFieldsValue({
      zones: [...d.zones].sort((a, b) => a.zone_number - b.zone_number),
    });
  };

  if (!subscriptionId) {
    return (
      <Result
        status="warning"
        title="Falta la suscripción"
        subTitle="Entrá a los equipos desde la lista de abonados."
        extra={<Button onClick={() => navigate("/security/subscriptions")}>Ir a abonados</Button>}
      />
    );
  }

  const columns = [
    {
      title: "Tipo",
      dataIndex: "device_type",
      key: "type",
      render: (v: SecurityDeviceType) => DEVICE_LABELS[v] ?? v,
    },
    {
      title: "Marca / modelo",
      key: "model",
      render: (_: unknown, d: SecurityDevice) =>
        [d.brand, d.model].filter(Boolean).join(" ") || <Text type="secondary">—</Text>,
    },
    { title: "N° de serie", dataIndex: "serial_number", key: "serial", render: (v?: string) => v || "—" },
    { title: "Ubicación", dataIndex: "location_description", key: "location", render: (v?: string) => v || "—" },
    {
      title: "Instalado",
      dataIndex: "install_date",
      key: "install",
      render: (v?: string) => (v ? dayjs(v).format("DD/MM/YYYY") : "—"),
    },
    { title: "Garantía", key: "warranty", render: (_: unknown, d: SecurityDevice) => warrantyTag(d) },
    {
      title: "Zonas",
      key: "zones",
      render: (_: unknown, d: SecurityDevice) =>
        d.device_type === "panel" ? (
          <Button size="small" icon={<ClusterOutlined />} onClick={() => openZones(d)} disabled={!d.is_active}>
            {d.zones.length}
          </Button>
        ) : (
          <Text type="secondary">—</Text>
        ),
    },
    {
      title: "Estado",
      dataIndex: "is_active",
      key: "active",
      render: (v: boolean) => (v ? <Tag color="green">Activo</Tag> : <Tag>De baja</Tag>),
    },
    {
      title: "",
      key: "actions",
      render: (_: unknown, d: SecurityDevice) => (
        <Space size={4}>
          <Tooltip title="Editar">
            <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(d)} />
          </Tooltip>
          <Popconfirm
            title={d.is_active ? "¿Dar de baja este equipo?" : "¿Reactivar este equipo?"}
            onConfirm={() => toggleActiveMutation.mutate(d)}
            okText="Sí"
            cancelText="No"
          >
            <Tooltip title={d.is_active ? "Dar de baja" : "Reactivar"}>
              <Button size="small" icon={d.is_active ? <StopOutlined /> : <UndoOutlined />} />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Space align="center">
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/security/subscriptions")} />
            <Title level={3} style={{ margin: 0 }}>Equipos — Suscripción #{subscriptionId}</Title>
          </Space>
        </Col>
        <Col>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => openEdit("new")}>
            Agregar equipo
          </Button>
        </Col>
      </Row>

      <Table
        dataSource={devices}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        size="small"
        pagination={false}
        rowClassName={(d) => (d.is_active ? "" : "ant-table-row-disabled")}
        locale={{ emptyText: "Sin equipos cargados" }}
      />

      {/* Create / edit */}
      <Modal
        open={!!editing}
        title={editing === "new" ? "Agregar equipo" : "Editar equipo"}
        onCancel={() => { setEditing(null); form.resetFields(); }}
        onOk={() => form.submit()}
        confirmLoading={saveMutation.isPending}
        okText="Guardar"
        width={560}
      >
        <Form form={form} layout="vertical" onFinish={(v) => saveMutation.mutate(v)}>
          <Form.Item name="device_type" label="Tipo" rules={[{ required: true }]}>
            <Select
              options={Object.entries(DEVICE_LABELS).map(([value, label]) => ({ value, label }))}
            />
          </Form.Item>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="brand" label="Marca"><Input /></Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="model" label="Modelo"><Input /></Form.Item>
            </Col>
          </Row>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="serial_number" label="N° de serie"><Input /></Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="firmware_version" label="Firmware"><Input /></Form.Item>
            </Col>
          </Row>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="install_date" label="Fecha de instalación">
                <DatePicker style={{ width: "100%" }} format="DD/MM/YYYY" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="warranty_months" label="Garantía (meses)">
                <InputNumber min={0} max={120} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="location_description" label="Ubicación">
            <Input placeholder="Ej: living, sobre la puerta de entrada" />
          </Form.Item>
          <Form.Item name="notes" label="Notas">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Zones */}
      <Modal
        open={!!zonesFor}
        title={`Zonas del panel${zonesFor?.brand ? ` — ${zonesFor.brand} ${zonesFor.model ?? ""}` : ""}`}
        onCancel={() => setZonesFor(null)}
        onOk={() => zonesForm.submit()}
        confirmLoading={zonesMutation.isPending}
        okText="Guardar zonas"
        width={680}
      >
        <Text type="secondary" style={{ fontSize: 12, display: "block", marginBottom: 12 }}>
          El nombre de la zona aparece en la Central de Monitoreo junto a cada alerta
          (por ejemplo "Intrusión · Zona 3 — Puerta cocina").
        </Text>
        <Form
          form={zonesForm}
          onFinish={(v) => zonesMutation.mutate(v.zones ?? [])}
        >
          <Form.List name="zones">
            {(fields, { add, remove }) => (
              <>
                {fields.map(({ key, name }) => (
                  <Space key={key} align="baseline" style={{ display: "flex", marginBottom: 4 }}>
                    <Form.Item name={[name, "zone_number"]} rules={[{ required: true, message: "N°" }]}>
                      <InputNumber min={1} max={999} placeholder="N°" style={{ width: 70 }} />
                    </Form.Item>
                    <Form.Item name={[name, "zone_name"]}>
                      <Input placeholder="Nombre (ej: Puerta cocina)" style={{ width: 220 }} maxLength={100} />
                    </Form.Item>
                    <Form.Item name={[name, "zone_type"]}>
                      <Select options={ZONE_TYPES} placeholder="Tipo" allowClear style={{ width: 170 }} />
                    </Form.Item>
                    <Form.Item name={[name, "enabled"]} valuePropName="checked" initialValue={true}>
                      <Switch size="small" />
                    </Form.Item>
                    <Button type="text" danger icon={<DeleteOutlined />} onClick={() => remove(name)} />
                  </Space>
                ))}
                <Button
                  type="dashed"
                  block
                  icon={<PlusOutlined />}
                  onClick={() => {
                    const current: DeviceZone[] = zonesForm.getFieldValue("zones") ?? [];
                    const next = current.reduce((m, z) => Math.max(m, z?.zone_number ?? 0), 0) + 1;
                    add({ zone_number: next, enabled: true });
                  }}
                >
                  Agregar zona
                </Button>
              </>
            )}
          </Form.List>
        </Form>
      </Modal>
    </div>
  );
}

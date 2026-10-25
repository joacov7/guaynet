import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Badge,
  Button,
  Card,
  Col,
  Divider,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Progress,
  Row,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Tabs,
  TimePicker,
  Tooltip,
  Typography,
  message,
} from "antd";
import {
  PlusOutlined,
  DeleteOutlined,
  EditOutlined,
  ThunderboltOutlined,
  ClockCircleOutlined,
  ApiOutlined,
  WarningOutlined,
  CheckCircleOutlined,
  StopOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";
import { routersApi, wanApi } from "@/services/api";
import type { WanInterface, WanSchedule } from "@/types";

const { Title, Text } = Typography;

const DAY_OPTIONS = [
  { label: "Lun", value: "mon" },
  { label: "Mar", value: "tue" },
  { label: "Mié", value: "wed" },
  { label: "Jue", value: "thu" },
  { label: "Vie", value: "fri" },
  { label: "Sáb", value: "sat" },
  { label: "Dom", value: "sun" },
];

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

function WanCard({ wan, routerId }: { wan: WanInterface; routerId: number }) {
  const qc = useQueryClient();
  const [schedModal, setSchedModal] = useState(false);
  const [editingSched, setEditingSched] = useState<WanSchedule | null>(null);
  const [lbGateway, setLbGateway] = useState("");
  const [schedForm] = Form.useForm();
  const [editForm] = Form.useForm();

  const toggleMut = useMutation({
    mutationFn: () => wanApi.toggle(routerId, wan.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["wan", routerId] }),
    onError: () => message.error("Error al cambiar estado"),
  });

  const clearOverrideMut = useMutation({
    mutationFn: () => wanApi.clearOverride(routerId, wan.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["wan", routerId] });
      message.success("Override manual desactivado");
    },
  });

  const deleteMut = useMutation({
    mutationFn: () => wanApi.remove(routerId, wan.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["wan", routerId] }),
    onError: () => message.error("Error al eliminar"),
  });

  const addSchedMut = useMutation({
    mutationFn: (vals: { action: string; days: string[]; time_start: string; time_end: string }) =>
      wanApi.createSchedule(routerId, wan.id, {
        ...vals,
        days: vals.days.join(","),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["wan", routerId] });
      setSchedModal(false);
      schedForm.resetFields();
      message.success("Programación guardada en MikroTik");
    },
    onError: () => message.error("Error al guardar programación"),
  });

  const delSchedMut = useMutation({
    mutationFn: (schedId: number) => wanApi.deleteSchedule(routerId, wan.id, schedId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["wan", routerId] }),
  });

  const editSchedMut = useMutation({
    mutationFn: (vals: { action: string; days: string[]; time_start: string; time_end: string }) =>
      wanApi.updateSchedule(routerId, wan.id, editingSched!.id, {
        ...vals,
        days: vals.days.join(","),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["wan", routerId] });
      setEditingSched(null);
      editForm.resetFields();
      message.success("Programación actualizada");
    },
    onError: () => message.error("Error al actualizar programación"),
  });

  const liveRunning = wan.live?.running ?? wan.enabled;
  const liveDisabled = wan.live?.disabled ?? !wan.enabled;

  const capPct = wan.cap_pct ?? null;
  const capColor = capPct !== null ? (capPct > 90 ? "#f5222d" : capPct > 70 ? "#faad14" : "#52c41a") : "#1677ff";

  return (
    <Card
      size="small"
      style={{ marginBottom: 16 }}
      title={
        <Space>
          <Badge status={liveRunning && !liveDisabled ? "success" : "error"} />
          <Text strong>{wan.display_name}</Text>
          <Tag color="default" style={{ fontSize: 11 }}>{wan.interface_name}</Tag>
          {wan.manual_override && (
            <Tag color="orange" icon={<WarningOutlined />}>Override manual</Tag>
          )}
        </Space>
      }
      extra={
        <Space>
          <Tooltip title={wan.enabled ? "Deshabilitar interfaz" : "Habilitar interfaz"}>
            <Switch
              checked={wan.enabled}
              loading={toggleMut.isPending}
              onChange={() => toggleMut.mutate()}
              checkedChildren="ON"
              unCheckedChildren="OFF"
            />
          </Tooltip>
          {wan.manual_override && (
            <Tooltip title="Volver a control automático por programación">
              <Button size="small" onClick={() => clearOverrideMut.mutate()} loading={clearOverrideMut.isPending}>
                Quitar override
              </Button>
            </Tooltip>
          )}
          <Popconfirm title="¿Eliminar esta WAN?" onConfirm={() => deleteMut.mutate()} okText="Sí" cancelText="No">
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      }
    >
      <Row gutter={16}>
        <Col span={12}>
          <Text type="secondary" style={{ fontSize: 11 }}>Peso (balanceo)</Text>
          <div style={{ fontWeight: 600 }}>{wan.weight}</div>
        </Col>
        <Col span={12}>
          <Text type="secondary" style={{ fontSize: 11 }}>Consumo del mes</Text>
          {wan.cap_gb ? (
            <Tooltip title={`${formatBytes(wan.used_bytes)} de ${wan.cap_gb} GB`}>
              <Progress
                percent={Math.round(capPct ?? 0)}
                size="small"
                strokeColor={capColor}
                format={() => `${formatBytes(wan.used_bytes)} / ${wan.cap_gb} GB`}
              />
            </Tooltip>
          ) : (
            <div>{formatBytes(wan.used_bytes)}</div>
          )}
        </Col>
      </Row>

      {wan.live && (
        <Row gutter={16} style={{ marginTop: 8 }}>
          <Col span={12}>
            <Text type="secondary" style={{ fontSize: 11 }}>RX acumulado</Text>
            <div>{formatBytes(wan.live.rx_byte)}</div>
          </Col>
          <Col span={12}>
            <Text type="secondary" style={{ fontSize: 11 }}>TX acumulado</Text>
            <div>{formatBytes(wan.live.tx_byte)}</div>
          </Col>
        </Row>
      )}

      <Divider style={{ margin: "10px 0" }} />

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
        <Text strong style={{ fontSize: 12 }}>
          <ClockCircleOutlined /> Programaciones horarias
        </Text>
        <Button size="small" icon={<PlusOutlined />} onClick={() => setSchedModal(true)}>
          Agregar
        </Button>
      </div>

      {wan.schedules.length === 0 ? (
        <Text type="secondary" style={{ fontSize: 12 }}>Sin programaciones</Text>
      ) : (
        <Table
          size="small"
          dataSource={wan.schedules}
          rowKey="id"
          pagination={false}
          columns={[
            {
              title: "Acción",
              dataIndex: "action",
              render: (v: string) => (
                <Tag color={v === "enable" ? "green" : "orange"} icon={v === "enable" ? <CheckCircleOutlined /> : <StopOutlined />}>
                  {v === "enable" ? "Habilitar" : "Deshabilitar"}
                </Tag>
              ),
            },
            {
              title: "Días",
              dataIndex: "days",
              render: (v: string) => v.split(",").map(d => DAY_OPTIONS.find(o => o.value === d)?.label || d).join(" "),
            },
            { title: "Inicio", dataIndex: "time_start" },
            { title: "Fin", dataIndex: "time_end" },
            {
              title: "",
              key: "actions",
              width: 70,
              render: (_: unknown, s: WanSchedule) => (
                <Space>
                  <Button
                    size="small"
                    icon={<EditOutlined />}
                    onClick={() => {
                      setEditingSched(s);
                      editForm.setFieldsValue({
                        action: s.action,
                        days: s.days.split(","),
                        time_start: dayjs(s.time_start, "HH:mm:ss"),
                        time_end: dayjs(s.time_end, "HH:mm:ss"),
                      });
                    }}
                  />
                  <Popconfirm title="¿Eliminar?" onConfirm={() => delSchedMut.mutate(s.id)} okText="Sí" cancelText="No">
                    <Button size="small" danger icon={<DeleteOutlined />} />
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
      )}

      <Modal
        title="Nueva programación horaria"
        open={schedModal}
        onCancel={() => { setSchedModal(false); schedForm.resetFields(); }}
        onOk={() => schedForm.submit()}
        confirmLoading={addSchedMut.isPending}
      >
        <Form
          form={schedForm}
          layout="vertical"
          initialValues={{ action: "enable", days: ["mon","tue","wed","thu","fri"] }}
          onFinish={(vals) => addSchedMut.mutate({
            action: vals.action,
            days: vals.days,
            time_start: dayjs(vals.time_start).format("HH:mm:00"),
            time_end: dayjs(vals.time_end).format("HH:mm:00"),
          })}
        >
          <Form.Item name="action" label="Acción" rules={[{ required: true }]}>
            <Select options={[
              { value: "enable", label: "Habilitar interfaz" },
              { value: "disable", label: "Deshabilitar interfaz" },
            ]} />
          </Form.Item>
          <Form.Item name="days" label="Días" rules={[{ required: true }]}>
            <Select mode="multiple" options={DAY_OPTIONS} />
          </Form.Item>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="time_start" label="Hora inicio" rules={[{ required: true }]}>
                <TimePicker format="HH:mm" style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="time_end" label="Hora fin" rules={[{ required: true }]}>
                <TimePicker format="HH:mm" style={{ width: "100%" }} />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>

      <Modal
        title="Editar programación horaria"
        open={editingSched !== null}
        onCancel={() => { setEditingSched(null); editForm.resetFields(); }}
        onOk={() => editForm.submit()}
        confirmLoading={editSchedMut.isPending}
      >
        <Form
          form={editForm}
          layout="vertical"
          onFinish={(vals) => editSchedMut.mutate({
            action: vals.action,
            days: vals.days,
            time_start: dayjs(vals.time_start).format("HH:mm:00"),
            time_end: dayjs(vals.time_end).format("HH:mm:00"),
          })}
        >
          <Form.Item name="action" label="Acción" rules={[{ required: true }]}>
            <Select options={[
              { value: "enable", label: "Habilitar interfaz" },
              { value: "disable", label: "Deshabilitar interfaz" },
            ]} />
          </Form.Item>
          <Form.Item name="days" label="Días" rules={[{ required: true }]}>
            <Select mode="multiple" options={DAY_OPTIONS} />
          </Form.Item>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="time_start" label="Hora inicio" rules={[{ required: true }]}>
                <TimePicker format="HH:mm" style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="time_end" label="Hora fin" rules={[{ required: true }]}>
                <TimePicker format="HH:mm" style={{ width: "100%" }} />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>
    </Card>
  );
}

function LoadBalanceWizard({ routerId, wans }: { routerId: number; wans: WanInterface[] }) {
  const [gateways, setGateways] = useState<Record<number, string>>({});
  const [applied, setApplied] = useState(false);

  const applyMut = useMutation({
    mutationFn: () => wanApi.applyLoadBalance(
      routerId,
      wans.map(w => ({ wan_interface_id: w.id, gateway: gateways[w.id] || "" }))
    ),
    onSuccess: () => { setApplied(true); message.success("Balanceo PCC aplicado en MikroTik"); },
    onError: () => message.error("Error al aplicar balanceo"),
  });

  const removeMut = useMutation({
    mutationFn: () => wanApi.removeLoadBalance(routerId),
    onSuccess: () => { setApplied(false); message.success("Reglas de balanceo eliminadas"); },
    onError: () => message.error("Error al eliminar reglas"),
  });

  if (wans.length < 2) {
    return <Alert message="Necesitás al menos 2 interfaces WAN configuradas para usar el balanceo de carga." type="info" showIcon />;
  }

  return (
    <Card title={<><ApiOutlined /> Wizard de Balanceo de Carga (PCC)</>} size="small">
      <Alert
        message="Este wizard genera reglas de mangle PCC + rutas en el MikroTik para distribuir conexiones entre las WAN configuradas."
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
      />
      <Table
        size="small"
        dataSource={wans}
        rowKey="id"
        pagination={false}
        columns={[
          { title: "Interfaz", dataIndex: "display_name" },
          { title: "Peso", dataIndex: "weight", render: (v: number) => `${v}` },
          {
            title: "Gateway (IP del proveedor)",
            key: "gateway",
            render: (_: unknown, w: WanInterface) => (
              <Input
                placeholder="ej: 192.168.1.1"
                value={gateways[w.id] || ""}
                onChange={e => setGateways(prev => ({ ...prev, [w.id]: e.target.value }))}
                style={{ width: 180 }}
              />
            ),
          },
        ]}
      />
      <Space style={{ marginTop: 12 }}>
        <Button
          type="primary"
          icon={<ThunderboltOutlined />}
          loading={applyMut.isPending}
          onClick={() => applyMut.mutate()}
          disabled={wans.some(w => !gateways[w.id])}
        >
          Aplicar balanceo
        </Button>
        <Popconfirm title="¿Eliminar reglas de balanceo del MikroTik?" onConfirm={() => removeMut.mutate()} okText="Sí" cancelText="No">
          <Button danger loading={removeMut.isPending}>Eliminar reglas</Button>
        </Popconfirm>
      </Space>
      {applied && (
        <Alert message="Balanceo PCC activo. El tráfico se distribuye entre las WAN configuradas." type="success" showIcon style={{ marginTop: 12 }} />
      )}
    </Card>
  );
}

export default function WanManagement() {
  const qc = useQueryClient();
  const [routerId, setRouterId] = useState<number | undefined>();
  const [addModal, setAddModal] = useState(false);
  const [addForm] = Form.useForm();

  const { data: routers = [] } = useQuery({ queryKey: ["routers"], queryFn: routersApi.list });

  const { data: wans = [], isLoading } = useQuery({
    queryKey: ["wan", routerId],
    queryFn: () => wanApi.list(routerId!),
    enabled: routerId != null,
    refetchInterval: 30_000,
  });

  const createMut = useMutation({
    mutationFn: (vals: { interface_name: string; display_name?: string; weight: number; cap_gb?: number }) =>
      wanApi.create(routerId!, vals),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["wan", routerId] });
      setAddModal(false);
      addForm.resetFields();
      message.success("Interfaz WAN agregada");
    },
    onError: () => message.error("Error al agregar"),
  });

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>Gestión WAN</Title>
        <Space>
          <Select
            placeholder="Seleccionar router"
            style={{ width: 240 }}
            value={routerId}
            onChange={setRouterId}
            options={routers.map(r => ({
              value: r.id,
              label: r.location ? `${r.name} (${r.location})` : r.name,
            }))}
          />
          {routerId && (
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setAddModal(true)}>
              Agregar WAN
            </Button>
          )}
        </Space>
      </div>

      {!routerId ? (
        <Alert message="Seleccioná un router para gestionar sus interfaces WAN." type="info" showIcon />
      ) : (
        <Tabs
          items={[
            {
              key: "interfaces",
              label: "Interfaces WAN",
              children: (
                <div>
                  {isLoading ? null : wans.length === 0 ? (
                    <Alert
                      message="No hay interfaces WAN configuradas para este router."
                      description="Hacé clic en «Agregar WAN» para registrar una interfaz WAN del MikroTik."
                      type="info"
                      showIcon
                    />
                  ) : (
                    wans.map(w => <WanCard key={w.id} wan={w} routerId={routerId!} />)
                  )}
                </div>
              ),
            },
            {
              key: "loadbalance",
              label: "Balanceo de carga",
              children: <LoadBalanceWizard routerId={routerId!} wans={wans} />,
            },
          ]}
        />
      )}

      <Modal
        title="Agregar interfaz WAN"
        open={addModal}
        onCancel={() => { setAddModal(false); addForm.resetFields(); }}
        onOk={() => addForm.submit()}
        confirmLoading={createMut.isPending}
      >
        <Form form={addForm} layout="vertical" onFinish={(vals) => createMut.mutate(vals)} initialValues={{ weight: 1 }}>
          <Form.Item name="interface_name" label="Nombre en MikroTik" rules={[{ required: true }]} extra="Ej: ether1, ether2-wan">
            <Input placeholder="ether1" />
          </Form.Item>
          <Form.Item name="display_name" label="Nombre visible">
            <Input placeholder="WAN Principal" />
          </Form.Item>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="weight" label="Peso (balanceo)" rules={[{ required: true }]}>
                <InputNumber min={1} max={100} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="cap_gb" label="Tope mensual (GB)" extra="Vacío = sin límite">
                <InputNumber min={1} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>
    </div>
  );
}

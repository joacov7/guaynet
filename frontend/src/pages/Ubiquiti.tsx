import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Badge,
  Button,
  Card,
  Col,
  Descriptions,
  Drawer,
  Form,
  Input,
  Modal,
  Popconfirm,
  Progress,
  Row,
  Select,
  Space,
  Spin,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import {
  ApiOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
  WifiOutlined,
} from "@ant-design/icons";
import { routersApi, ubiquitiApi } from "@/services/api";
import type {
  FrequencyRecommendation,
  UbiquitiDevice,
  UbiquitiStation,
  UbiquitiSurveyScan,
} from "@/types";

const { Title, Text } = Typography;

const deviceTypeLabel: Record<string, string> = {
  airmax_ap: "AirMax AP",
  airmax_station: "AirMax Station",
  unifi_ap: "UniFi AP",
  unifi_switch: "UniFi Switch",
  unifi_gateway: "UniFi Gateway",
};

function signalColor(dbm?: number) {
  if (!dbm) return "default";
  if (dbm >= -60) return "green";
  if (dbm >= -75) return "orange";
  return "red";
}

function ccqColor(ccq?: number) {
  if (!ccq) return "default";
  if (ccq >= 80) return "green";
  if (ccq >= 50) return "orange";
  return "red";
}

function secondsToUptime(s: number): string {
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  return d > 0 ? `${d}d ${h}h ${m}m` : `${h}h ${m}m`;
}

// ── Device detail drawer ──────────────────────────────────────────────────────

function DeviceDrawer({
  device,
  onClose,
  onUpdated,
}: {
  device: UbiquitiDevice;
  onClose: () => void;
  onUpdated: () => void;
}) {
  const navigate = useNavigate();
  const [surveyRan, setSurveyRan] = useState(false);
  const [applyFreqModal, setApplyFreqModal] = useState<FrequencyRecommendation | null>(null);
  const [applyForm] = Form.useForm();

  const testMutation = useMutation({
    mutationFn: () => ubiquitiApi.test(device.id),
    onSuccess: () => { message.success("Conexión exitosa"); onUpdated(); },
    onError: (e: any) => message.error(e.response?.data?.detail ?? "No se pudo conectar"),
  });

  const { data: info, isLoading: infoLoading } = useQuery({
    queryKey: ["ubiquiti-info", device.id],
    queryFn: () => ubiquitiApi.getInfo(device.id),
    retry: false,
  });

  const { data: wireless, isLoading: wirelessLoading, refetch: refetchWireless } = useQuery({
    queryKey: ["ubiquiti-wireless", device.id],
    queryFn: () => ubiquitiApi.getWireless(device.id),
    retry: false,
  });

  const { data: link, isLoading: linkLoading } = useQuery({
    queryKey: ["ubiquiti-link", device.id],
    queryFn: () => ubiquitiApi.getLink(device.id),
    retry: false,
    enabled: device.device_type === "airmax_station",
  });

  const { data: stations = [], isLoading: stationsLoading, refetch: refetchStations } = useQuery({
    queryKey: ["ubiquiti-stations", device.id],
    queryFn: () => ubiquitiApi.getStations(device.id),
    retry: false,
    enabled: device.device_type === "airmax_ap" || device.device_type === "unifi_ap",
  });

  const { data: dbClients = [] } = useQuery({
    queryKey: ["ubiquiti-clients", device.id],
    queryFn: () => ubiquitiApi.clients(device.id),
  });

  const { data: survey = [], isLoading: surveyLoading, refetch: refetchSurvey } = useQuery({
    queryKey: ["ubiquiti-survey", device.id],
    queryFn: () => ubiquitiApi.survey(device.id),
    enabled: surveyRan,
    retry: false,
  });

  const { data: recommendations = [], isLoading: recLoading, refetch: refetchRec } = useQuery({
    queryKey: ["ubiquiti-rec", device.id],
    queryFn: () => ubiquitiApi.recommendations(device.id),
    enabled: surveyRan,
    retry: false,
  });

  const setWirelessMutation = useMutation({
    mutationFn: (data: { frequency_mhz?: number; channel_width_mhz?: number; tx_power_dbm?: number }) =>
      ubiquitiApi.setWireless(device.id, data),
    onSuccess: () => {
      message.success("Configuración aplicada. El dispositivo puede desconectarse brevemente.");
      refetchWireless();
      onUpdated();
      setApplyFreqModal(null);
    },
    onError: (e: any) => message.error(e.response?.data?.detail ?? "Error al aplicar configuración"),
  });

  const handleSurvey = () => {
    setSurveyRan(true);
    setTimeout(() => { refetchSurvey(); refetchRec(); }, 100);
  };

  const isAP = device.device_type === "airmax_ap" || device.device_type === "unifi_ap";
  const isStation = device.device_type === "airmax_station";

  const stationColumns = [
    { title: "MAC", dataIndex: "mac", key: "mac" },
    { title: "IP", dataIndex: "ip", key: "ip", render: (v: string) => v || "—" },
    { title: "Nombre", dataIndex: "name", key: "name", render: (v: string) => v || "—" },
    {
      title: "Señal",
      dataIndex: "signal_dbm",
      key: "signal",
      render: (v: number) => v ? <Tag color={signalColor(v)}>{v} dBm</Tag> : "—",
    },
    {
      title: "CCQ",
      dataIndex: "ccq",
      key: "ccq",
      render: (v: number) => v != null ? (
        <Progress percent={v} size="small" strokeColor={ccqColor(v) === "green" ? "#52c41a" : ccqColor(v) === "orange" ? "#faad14" : "#f5222d"} />
      ) : "—",
    },
    {
      title: "RX / TX",
      key: "rates",
      render: (_: unknown, r: UbiquitiStation) =>
        r.rx_rate_mbps ? `${r.rx_rate_mbps} / ${r.tx_rate_mbps} Mbps` : "—",
    },
    {
      title: "Uptime",
      dataIndex: "uptime_seconds",
      key: "uptime",
      render: (v: number) => v ? secondsToUptime(v) : "—",
    },
  ];

  const surveyColumns = [
    { title: "SSID", dataIndex: "ssid", key: "ssid", render: (v: string) => v || "(oculto)" },
    { title: "MAC", dataIndex: "mac", key: "mac" },
    {
      title: "Frecuencia",
      dataIndex: "frequency_mhz",
      key: "freq",
      render: (v: number) => v ? `${v} MHz` : "—",
    },
    {
      title: "Ancho",
      dataIndex: "channel_width_mhz",
      key: "width",
      render: (v: number) => v ? `${v} MHz` : "—",
    },
    {
      title: "Señal",
      dataIndex: "signal_dbm",
      key: "signal",
      render: (v: number) => v ? <Tag color={signalColor(v)}>{v} dBm</Tag> : "—",
    },
    { title: "Seguridad", dataIndex: "security", key: "sec", render: (v: string) => v || "—" },
  ];

  const recColor: Record<string, string> = {
    Excelente: "success",
    Buena: "processing",
    Regular: "warning",
    Congestionada: "error",
  };

  return (
    <Drawer
      title={
        <Space>
          <span>{device.name}</span>
          <Tag>{deviceTypeLabel[device.device_type]}</Tag>
          <Badge status={device.status === "online" ? "success" : device.status === "offline" ? "error" : "default"} text={device.status} />
        </Space>
      }
      open
      onClose={onClose}
      width={760}
      extra={
        <Button
          icon={<ApiOutlined />}
          onClick={() => testMutation.mutate()}
          loading={testMutation.isPending}
        >
          Probar conexión
        </Button>
      }
    >
      <Tabs
        items={[
          {
            key: "info",
            label: "Info",
            children: infoLoading ? (
              <Spin />
            ) : info ? (
              <Descriptions column={2} bordered size="small">
                <Descriptions.Item label="Modelo">{info.model || device.model_name || "—"}</Descriptions.Item>
                <Descriptions.Item label="Firmware">{info.firmware || device.firmware_version || "—"}</Descriptions.Item>
                <Descriptions.Item label="Hostname">{info.hostname || "—"}</Descriptions.Item>
                <Descriptions.Item label="Uptime">{secondsToUptime(info.uptime_seconds)}</Descriptions.Item>
                <Descriptions.Item label="CPU">{info.cpu_load}%</Descriptions.Item>
                <Descriptions.Item label="RAM usada">{info.ram_used_pct}%</Descriptions.Item>
                <Descriptions.Item label="Host">{device.host}</Descriptions.Item>
                <Descriptions.Item label="Ubicación">{device.location || "—"}</Descriptions.Item>
              </Descriptions>
            ) : (
              <Alert type="warning" message="No se pudo obtener info. Probá la conexión primero." />
            ),
          },
          {
            key: "wireless",
            label: "Wireless",
            children: wirelessLoading ? (
              <Spin />
            ) : wireless ? (
              <div>
                <Descriptions column={2} bordered size="small" style={{ marginBottom: 16 }}>
                  <Descriptions.Item label="Modo">
                    <Tag color="blue">{wireless.mode || "—"}</Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="SSID">{wireless.ssid || "—"}</Descriptions.Item>
                  <Descriptions.Item label="Frecuencia">
                    {wireless.frequency_mhz ? `${wireless.frequency_mhz} MHz` : "—"}
                  </Descriptions.Item>
                  <Descriptions.Item label="Ancho de canal">
                    {wireless.channel_width_mhz ? `${wireless.channel_width_mhz} MHz` : "—"}
                  </Descriptions.Item>
                  <Descriptions.Item label="TX Power">
                    {wireless.tx_power_dbm ? `${wireless.tx_power_dbm} dBm` : "—"}
                  </Descriptions.Item>
                  <Descriptions.Item label="Seguridad">{wireless.security || "—"}</Descriptions.Item>
                </Descriptions>
                {isStation && link && !linkLoading && (
                  <Card title="Calidad de enlace" size="small">
                    <Row gutter={16}>
                      <Col span={8}>
                        <div style={{ textAlign: "center" }}>
                          <div style={{ fontSize: 28, fontWeight: 700, color: signalColor(link.signal_dbm) === "green" ? "#52c41a" : signalColor(link.signal_dbm) === "orange" ? "#faad14" : "#f5222d" }}>
                            {link.signal_dbm ?? "—"}
                          </div>
                          <Text type="secondary">dBm señal</Text>
                        </div>
                      </Col>
                      <Col span={8}>
                        <div style={{ textAlign: "center" }}>
                          <div style={{ fontSize: 28, fontWeight: 700 }}>
                            {link.ccq ?? "—"}
                          </div>
                          <Text type="secondary">% CCQ</Text>
                        </div>
                      </Col>
                      <Col span={8}>
                        <div style={{ textAlign: "center" }}>
                          <div style={{ fontSize: 28, fontWeight: 700 }}>
                            {link.snr_db ?? "—"}
                          </div>
                          <Text type="secondary">dB SNR</Text>
                        </div>
                      </Col>
                    </Row>
                    <Descriptions column={2} size="small" style={{ marginTop: 12 }}>
                      <Descriptions.Item label="AP remoto">{link.remote_name || link.remote_mac || "—"}</Descriptions.Item>
                      <Descriptions.Item label="Distancia">{link.distance_m ? `${link.distance_m} m` : "—"}</Descriptions.Item>
                      <Descriptions.Item label="RX">{link.rx_rate_mbps ? `${link.rx_rate_mbps} Mbps` : "—"}</Descriptions.Item>
                      <Descriptions.Item label="TX">{link.tx_rate_mbps ? `${link.tx_rate_mbps} Mbps` : "—"}</Descriptions.Item>
                      <Descriptions.Item label="Ruido">{link.noise_dbm ? `${link.noise_dbm} dBm` : "—"}</Descriptions.Item>
                    </Descriptions>
                  </Card>
                )}
              </div>
            ) : (
              <Alert type="warning" message="No se pudo obtener config wireless." />
            ),
          },
          ...(isAP
            ? [
                {
                  key: "stations",
                  label: (
                    <span>
                      Estaciones
                      <Badge count={stations.length} style={{ marginLeft: 6, backgroundColor: "#1677ff" }} />
                    </span>
                  ),
                  children: (
                    <div>
                      <Button
                        size="small"
                        icon={<ReloadOutlined />}
                        onClick={() => refetchStations()}
                        style={{ marginBottom: 12 }}
                        loading={stationsLoading}
                      >
                        Actualizar
                      </Button>
                      <Table
                        loading={stationsLoading}
                        dataSource={stations}
                        rowKey="mac"
                        columns={stationColumns}
                        size="small"
                        pagination={{ pageSize: 20 }}
                      />
                    </div>
                  ),
                },
              ]
            : []),
          {
            key: "clients",
            label: (
              <span>
                Clientes DB
                <Badge count={dbClients.length} style={{ marginLeft: 6, backgroundColor: "#722ed1" }} />
              </span>
            ),
            children: (
              <div>
                <Table
                  dataSource={dbClients}
                  rowKey="id"
                  size="small"
                  pagination={{ pageSize: 20 }}
                  columns={[
                    {
                      title: "Cliente",
                      dataIndex: "full_name",
                      key: "name",
                      render: (v: string, r: any) => (
                        <a onClick={() => navigate(`/clients/${r.id}`)}>{v}</a>
                      ),
                    },
                    { title: "IP", dataIndex: "ip_address", key: "ip" },
                    { title: "MAC", dataIndex: "mac_address", key: "mac", render: (v: string) => v || "—" },
                    {
                      title: "Estado",
                      dataIndex: "status",
                      key: "status",
                      render: (v: string) => (
                        <Tag color={v === "active" ? "green" : v === "suspended" ? "orange" : "default"}>{v}</Tag>
                      ),
                    },
                  ]}
                />
              </div>
            ),
          },
          {
            key: "survey",
            label: <span><WifiOutlined /> Site Survey</span>,
            children: (
              <div>
                <Space style={{ marginBottom: 16 }}>
                  <Button
                    type="primary"
                    icon={<WifiOutlined />}
                    onClick={handleSurvey}
                    loading={surveyLoading || recLoading}
                  >
                    Escanear frecuencias
                  </Button>
                  <Text type="secondary">Detecta redes cercanas y recomienda frecuencias libres</Text>
                </Space>

                {recommendations.length > 0 && (
                  <div style={{ marginBottom: 16 }}>
                    <Title level={5}>Recomendaciones</Title>
                    <Row gutter={[8, 8]}>
                      {recommendations.map((r) => (
                        <Col key={r.frequency_mhz} xs={24} sm={12} md={8}>
                          <Card
                            size="small"
                            style={{
                              borderColor:
                                r.recommendation === "Excelente" ? "#52c41a" :
                                r.recommendation === "Buena" ? "#1677ff" :
                                r.recommendation === "Regular" ? "#faad14" : "#f5222d",
                            }}
                            actions={[
                              <Popconfirm
                                key="apply"
                                title={`¿Cambiar a ${r.frequency_mhz} MHz? El dispositivo puede desconectarse brevemente.`}
                                onConfirm={() => setWirelessMutation.mutate({ frequency_mhz: r.frequency_mhz })}
                              >
                                <Button
                                  size="small"
                                  type="primary"
                                  icon={<ThunderboltOutlined />}
                                  loading={setWirelessMutation.isPending}
                                >
                                  Aplicar
                                </Button>
                              </Popconfirm>,
                            ]}
                          >
                            <div style={{ textAlign: "center" }}>
                              <div style={{ fontSize: 22, fontWeight: 700 }}>{r.frequency_mhz} MHz</div>
                              <Tag color={recColor[r.recommendation] as any}>{r.recommendation}</Tag>
                              <div style={{ marginTop: 4 }}>
                                <Text type="secondary">{r.network_count} redes · score {r.congestion_score}</Text>
                              </div>
                            </div>
                          </Card>
                        </Col>
                      ))}
                    </Row>
                  </div>
                )}

                {survey.length > 0 && (
                  <>
                    <Title level={5}>Redes detectadas ({survey.length})</Title>
                    <Table
                      dataSource={survey}
                      rowKey={(r: UbiquitiSurveyScan) => `${r.mac}-${r.frequency_mhz}`}
                      columns={surveyColumns}
                      size="small"
                      pagination={{ pageSize: 25 }}
                    />
                  </>
                )}
              </div>
            ),
          },
        ]}
      />
    </Drawer>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Ubiquiti() {
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editDevice, setEditDevice] = useState<UbiquitiDevice | null>(null);
  const [detailDevice, setDetailDevice] = useState<UbiquitiDevice | null>(null);
  const [form] = Form.useForm();

  const { data: devices = [], isLoading } = useQuery({
    queryKey: ["ubiquiti"],
    queryFn: ubiquitiApi.list,
  });
  const { data: routers = [] } = useQuery({ queryKey: ["routers"], queryFn: routersApi.list });

  const saveMutation = useMutation({
    mutationFn: (values: any) =>
      editDevice
        ? ubiquitiApi.update(editDevice.id, values)
        : ubiquitiApi.create(values),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ubiquiti"] });
      message.success(editDevice ? "Dispositivo actualizado" : "Dispositivo creado");
      closeModal();
    },
    onError: (e: any) => message.error(e.response?.data?.detail ?? "Error al guardar"),
  });

  const deleteMutation = useMutation({
    mutationFn: ubiquitiApi.delete,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["ubiquiti"] }); message.success("Eliminado"); },
    onError: () => message.error("Error al eliminar"),
  });

  const testMutation = useMutation({
    mutationFn: ubiquitiApi.test,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["ubiquiti"] }); message.success("Online"); },
    onError: (e: any) => message.warning(e.response?.data?.detail ?? "Sin conexión"),
  });

  const openCreate = () => {
    setEditDevice(null);
    form.resetFields();
    form.setFieldsValue({ username: "ubnt", device_type: "airmax_ap" });
    setModalOpen(true);
  };

  const openEdit = (d: UbiquitiDevice) => {
    setEditDevice(d);
    form.setFieldsValue({ ...d, password: "" });
    setModalOpen(true);
  };

  const closeModal = () => { setModalOpen(false); setEditDevice(null); form.resetFields(); };

  const columns = [
    {
      title: "Nombre",
      key: "name",
      render: (_: unknown, r: UbiquitiDevice) => (
        <a onClick={() => setDetailDevice(r)}>{r.name}</a>
      ),
    },
    {
      title: "Tipo",
      dataIndex: "device_type",
      key: "type",
      render: (v: string) => <Tag>{deviceTypeLabel[v]}</Tag>,
    },
    { title: "Host", dataIndex: "host", key: "host" },
    { title: "Ubicación", dataIndex: "location", key: "location", render: (v: string) => v || "—" },
    {
      title: "Estado",
      dataIndex: "status",
      key: "status",
      render: (v: string) => (
        <Badge
          status={v === "online" ? "success" : v === "offline" ? "error" : "default"}
          text={v}
        />
      ),
    },
    {
      title: "Frecuencia",
      dataIndex: "frequency_mhz",
      key: "freq",
      render: (v: number) => v ? `${v} MHz` : "—",
    },
    {
      title: "Señal",
      dataIndex: "signal_dbm",
      key: "signal",
      render: (v: number) => v ? <Tag color={signalColor(v)}>{v} dBm</Tag> : "—",
    },
    {
      title: "CCQ",
      dataIndex: "ccq",
      key: "ccq",
      render: (v: number) => v != null ? (
        <Tag color={ccqColor(v)}>{v}%</Tag>
      ) : "—",
    },
    { title: "Clientes", dataIndex: "client_count", key: "clients", align: "right" as const },
    {
      title: "",
      key: "actions",
      align: "right" as const,
      render: (_: unknown, r: UbiquitiDevice) => (
        <Space size={4}>
          <Tooltip title="Ver detalle">
            <Button size="small" icon={<WifiOutlined />} onClick={() => setDetailDevice(r)} />
          </Tooltip>
          <Tooltip title="Probar conexión">
            <Button
              size="small"
              icon={<ApiOutlined />}
              onClick={() => testMutation.mutate(r.id)}
              loading={testMutation.isPending}
            />
          </Tooltip>
          <Tooltip title="Editar">
            <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)} />
          </Tooltip>
          <Popconfirm title="¿Eliminar dispositivo?" onConfirm={() => deleteMutation.mutate(r.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          Ubiquiti
          <Badge count={devices.length} style={{ marginLeft: 8, backgroundColor: "#1677ff" }} />
        </Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          Nuevo dispositivo
        </Button>
      </div>

      <Table
        loading={isLoading}
        dataSource={devices}
        rowKey="id"
        columns={columns}
        size="small"
        pagination={false}
      />

      {/* Create / Edit modal */}
      <Modal
        title={editDevice ? "Editar dispositivo" : "Nuevo dispositivo Ubiquiti"}
        open={modalOpen}
        onCancel={closeModal}
        onOk={() => form.submit()}
        confirmLoading={saveMutation.isPending}
        width={520}
      >
        <Form form={form} layout="vertical" onFinish={(v) => saveMutation.mutate(v)}>
          <Form.Item name="name" label="Nombre" rules={[{ required: true }]}>
            <Input placeholder="Ej: Panel Norte - LiteBeam 5AC" />
          </Form.Item>
          <Row gutter={12}>
            <Col span={16}>
              <Form.Item name="host" label="Host / IP" rules={[{ required: true }]}>
                <Input placeholder="192.168.1.20" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="device_type" label="Tipo" rules={[{ required: true }]}>
                <Select
                  options={Object.entries(deviceTypeLabel).map(([k, v]) => ({ value: k, label: v }))}
                />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="username" label="Usuario">
                <Input />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="password"
                label="Contraseña"
                rules={editDevice ? [] : [{ required: true }]}
              >
                <Input.Password placeholder={editDevice ? "(sin cambios)" : ""} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="location" label="Ubicación / Torre">
            <Input placeholder="Ej: Torre Norte" />
          </Form.Item>
          <Form.Item name="mikrotik_router_id" label="Router Mikrotik asociado">
            <Select
              allowClear
              placeholder="Opcional"
              options={routers.map((r) => ({
                value: r.id,
                label: r.location ? `${r.name} (${r.location})` : r.name,
              }))}
            />
          </Form.Item>
          <Form.Item name="mac_address" label="MAC Address">
            <Input placeholder="FC:EC:DA:xx:xx:xx" />
          </Form.Item>
          <Form.Item name="notes" label="Notas">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Detail drawer */}
      {detailDevice && (
        <DeviceDrawer
          device={detailDevice}
          onClose={() => setDetailDevice(null)}
          onUpdated={() => {
            qc.invalidateQueries({ queryKey: ["ubiquiti"] });
            // Refresh the device in drawer state
            ubiquitiApi.get(detailDevice.id).then(setDetailDevice).catch(() => {});
          }}
        />
      )}
    </div>
  );
}

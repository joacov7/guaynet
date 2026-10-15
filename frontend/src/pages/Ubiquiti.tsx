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
  InputNumber,
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
  Upload,
  message,
} from "antd";
import {
  ApiOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  CloudUploadOutlined,
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
  airmax_ap: "AirMax AP (M)",
  airmax_station: "AirMax Station (M)",
  airmax_ac_ap: "AirMax AC AP",
  airmax_ac_station: "AirMax AC Station",
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
    enabled: device.device_type === "airmax_station" || device.device_type === "airmax_ac_station",
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

  const isAP = device.device_type === "airmax_ap" || device.device_type === "airmax_ac_ap" || device.device_type === "unifi_ap";
  const isStation = device.device_type === "airmax_station" || device.device_type === "airmax_ac_station";

  // Build lookup maps to cross-reference live stations with registered clients
  const clientByIp = Object.fromEntries(dbClients.map((c: any) => [c.ip_address, c]));
  const clientByMac = Object.fromEntries(
    dbClients.filter((c: any) => c.mac_address).map((c: any) => [c.mac_address?.toLowerCase(), c])
  );
  const enrichedStations = stations.map((s) => ({
    ...s,
    _client: clientByIp[s.ip] || clientByMac[s.mac?.toLowerCase()] || null,
  }));

  const stationColumns = [
    {
      title: "Cliente",
      key: "client",
      render: (_: unknown, r: any) =>
        r._client ? (
          <a onClick={() => navigate(`/clients/${r._client.id}`)}>{r._client.full_name}</a>
        ) : (
          <Text type="secondary">{r.name || "Desconocido"}</Text>
        ),
    },
    { title: "IP", dataIndex: "ip", key: "ip", render: (v: string) => v || "—" },
    { title: "MAC", dataIndex: "mac", key: "mac" },
    {
      title: "Señal",
      dataIndex: "signal_dbm",
      key: "signal",
      sorter: (a: any, b: any) => (a.signal_dbm ?? -999) - (b.signal_dbm ?? -999),
      render: (v: number) => v ? <Tag color={signalColor(v)}>{v} dBm</Tag> : "—",
    },
    {
      title: "CCQ",
      dataIndex: "ccq",
      key: "ccq",
      sorter: (a: any, b: any) => (a.ccq ?? 0) - (b.ccq ?? 0),
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
          ...(isAP
            ? [
                {
                  key: "mejoras",
                  label: (() => {
                    const badSignalCount = enrichedStations.filter((s) => s.signal_dbm && s.signal_dbm < -75).length;
                    const lowCcqCount = enrichedStations.filter((s) => s.ccq != null && s.ccq < 50).length;
                    const issues = badSignalCount + lowCcqCount;
                    return (
                      <span>
                        Mejoras
                        {issues > 0 && <Badge count={issues} style={{ marginLeft: 6 }} />}
                      </span>
                    );
                  })(),
                  children: (() => {
                    const badSignal = enrichedStations.filter((s) => s.signal_dbm && s.signal_dbm < -75);
                    const lowCcq = enrichedStations.filter((s) => s.ccq != null && s.ccq < 50 && !(s.signal_dbm && s.signal_dbm < -75));
                    const connectedIps = new Set(stations.map((s) => s.ip).filter(Boolean));
                    const offlineClients = dbClients.filter((c: any) => c.ip_address && !connectedIps.has(c.ip_address));

                    const issueRow = (label: string, clients: any[], advice: string, color: string) => (
                      clients.length > 0 ? (
                        <Alert
                          key={label}
                          type={color as any}
                          showIcon
                          style={{ marginBottom: 12 }}
                          message={<strong>{label} ({clients.length})</strong>}
                          description={
                            <div>
                              <div style={{ marginBottom: 6, color: "#595959" }}>{advice}</div>
                              <ul style={{ margin: 0, paddingLeft: 20 }}>
                                {clients.map((s: any, i: number) => (
                                  <li key={i}>
                                    {s._client || s.full_name ? (
                                      <a onClick={() => s._client && navigate(`/clients/${s._client.id}`)}>
                                        {s._client?.full_name || s.full_name}
                                      </a>
                                    ) : (
                                      <span>{s.mac || s.ip_address || "Desconocido"}</span>
                                    )}
                                    {s.signal_dbm && <Tag color={signalColor(s.signal_dbm)} style={{ marginLeft: 8 }}>{s.signal_dbm} dBm</Tag>}
                                    {s.ccq != null && <Tag color={ccqColor(s.ccq)} style={{ marginLeft: 4 }}>CCQ {s.ccq}%</Tag>}
                                    {s.ip_address && <Text type="secondary" style={{ marginLeft: 4 }}>{s.ip_address}</Text>}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          }
                        />
                      ) : null
                    );

                    const hasIssues = badSignal.length + lowCcq.length + offlineClients.length > 0;
                    return (
                      <div>
                        {!hasIssues && (
                          <Alert type="success" showIcon message="Todo en orden" description="No se detectaron problemas de señal en los clientes conectados." />
                        )}
                        {issueRow("Señal débil (< -75 dBm)", badSignal, "Revisar orientación y alineación de antena. Verificar obstrucciones o distancia excesiva.", "error")}
                        {issueRow("CCQ bajo (< 50%)", lowCcq, "Alta interferencia en el canal. Usar Site Survey para cambiar a una frecuencia menos congestionada.", "warning")}
                        {issueRow("Clientes no conectados", offlineClients, "Clientes registrados en la base de datos que no están presentes en el AP. Pueden estar apagados o con problemas de enlace.", "info")}
                      </div>
                    );
                  })(),
                },
              ]
            : []),
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

  // ── Firmware update state ──────────────────────────────────────────────────
  const [firmwareModalOpen, setFirmwareModalOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [firmwareFileList, setFirmwareFileList] = useState<any[]>([]);
  const [selectedDeviceIds, setSelectedDeviceIds] = useState<number[]>([]);
  const [updateProgress, setUpdateProgress] = useState<Record<number, { status: "pending" | "updating" | "done" | "error"; message?: string }>>({});
  const [isUpdating, setIsUpdating] = useState(false);

  const closeFirmwareModal = () => {
    if (isUpdating) return;
    setFirmwareModalOpen(false);
    setSelectedFile(null);
    setFirmwareFileList([]);
    setSelectedDeviceIds([]);
    setUpdateProgress({});
  };

  const startFirmwareUpdate = async () => {
    if (!selectedFile || selectedDeviceIds.length === 0) return;
    setIsUpdating(true);
    const initial: Record<number, { status: "pending" | "updating" | "done" | "error"; message?: string }> = {};
    for (const id of selectedDeviceIds) initial[id] = { status: "pending" };
    setUpdateProgress(initial);
    for (const id of selectedDeviceIds) {
      setUpdateProgress((prev) => ({ ...prev, [id]: { status: "updating" } }));
      try {
        await ubiquitiApi.uploadFirmware(id, selectedFile);
        setUpdateProgress((prev) => ({ ...prev, [id]: { status: "done" } }));
      } catch (e: any) {
        const msg = e.response?.data?.detail ?? e.message ?? "Error desconocido";
        setUpdateProgress((prev) => ({ ...prev, [id]: { status: "error", message: msg } }));
      }
    }
    setIsUpdating(false);
  };

  const firmwareDeviceColumns = [
    { title: "Nombre", dataIndex: "name", key: "name" },
    {
      title: "Tipo",
      dataIndex: "device_type",
      key: "type",
      render: (v: string) => <Tag>{deviceTypeLabel[v]}</Tag>,
    },
    { title: "Host", dataIndex: "host", key: "host" },
    {
      title: "Estado actual",
      dataIndex: "status",
      key: "status",
      render: (v: string) => (
        <Badge
          status={v === "online" ? "success" : v === "offline" ? "error" : "default"}
          text={v}
        />
      ),
    },
  ];

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
        <Space>
          <Button icon={<CloudUploadOutlined />} onClick={() => setFirmwareModalOpen(true)}>
            Actualizar firmware
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            Nuevo dispositivo
          </Button>
        </Space>
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
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="latitude" label="Latitud">
                <InputNumber style={{ width: "100%" }} placeholder="-34.6037" step={0.0001} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="longitude" label="Longitud">
                <InputNumber style={{ width: "100%" }} placeholder="-58.3816" step={0.0001} />
              </Form.Item>
            </Col>
          </Row>
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

      {/* Firmware update modal */}
      <Modal
        title={<Space><CloudUploadOutlined /> Actualizar firmware</Space>}
        open={firmwareModalOpen}
        onCancel={closeFirmwareModal}
        closable={!isUpdating}
        maskClosable={!isUpdating}
        width={700}
        footer={[
          <Button key="cancel" onClick={closeFirmwareModal} disabled={isUpdating}>
            Cancelar
          </Button>,
          <Button
            key="start"
            type="primary"
            icon={<CloudUploadOutlined />}
            disabled={!selectedFile || selectedDeviceIds.length === 0 || isUpdating}
            loading={isUpdating}
            onClick={startFirmwareUpdate}
          >
            Iniciar actualización
          </Button>,
        ]}
      >
        <Space direction="vertical" style={{ width: "100%" }} size="middle">
          <Upload.Dragger
            multiple={false}
            fileList={firmwareFileList}
            beforeUpload={(file) => {
              setSelectedFile(file);
              setFirmwareFileList([{ uid: file.uid, name: file.name, status: "done", originFileObj: file }]);
              return false;
            }}
            onRemove={() => {
              setSelectedFile(null);
              setFirmwareFileList([]);
            }}
          >
            <p className="ant-upload-drag-icon"><CloudUploadOutlined style={{ fontSize: 32 }} /></p>
            <p>Hacé clic o arrastrá el archivo de firmware aquí</p>
            <p><Text type="secondary">Cualquier archivo binario de firmware (.bin, .img, etc.)</Text></p>
          </Upload.Dragger>

          <div>
            <Text strong>Seleccioná los dispositivos a actualizar</Text>
            <Table
              dataSource={devices}
              rowKey="id"
              size="small"
              pagination={false}
              style={{ marginTop: 8 }}
              rowSelection={{
                type: "checkbox",
                selectedRowKeys: selectedDeviceIds,
                onChange: (keys) => setSelectedDeviceIds(keys as number[]),
                getCheckboxProps: () => ({ disabled: isUpdating }),
              }}
              columns={firmwareDeviceColumns}
            />
          </div>

          {isUpdating && (
            <Alert
              type="info"
              showIcon
              message="Actualización en progreso — no cierre esta ventana. No es posible cancelar una vez iniciada."
            />
          )}

          {Object.keys(updateProgress).length > 0 && (
            <div>
              <Text strong>Progreso</Text>
              <div style={{ marginTop: 8 }}>
                {selectedDeviceIds.map((id) => {
                  const dev = devices.find((d) => d.id === id);
                  const prog = updateProgress[id];
                  return (
                    <div key={id} style={{ display: "flex", alignItems: "flex-start", gap: 8, marginBottom: 6 }}>
                      {prog?.status === "pending" && <ClockCircleOutlined style={{ color: "#8c8c8c", marginTop: 3 }} />}
                      {prog?.status === "updating" && <Spin size="small" style={{ marginTop: 1 }} />}
                      {prog?.status === "done" && <CheckCircleOutlined style={{ color: "#52c41a", marginTop: 3 }} />}
                      {prog?.status === "error" && <CloseCircleOutlined style={{ color: "#f5222d", marginTop: 3 }} />}
                      <div>
                        <Text>{dev?.name ?? `Dispositivo ${id}`}</Text>
                        {prog?.status === "done" && (
                          <div><Text type="success" style={{ fontSize: 12 }}>Firmware subido correctamente</Text></div>
                        )}
                        {prog?.status === "error" && prog.message && (
                          <div><Text type="danger" style={{ fontSize: 12 }}>{prog.message}</Text></div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </Space>
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

/**
 * Client self-service portal.
 * Accessed at /seguridad — identified by IP, by link (?token=) or, in the mobile app, by device credential.
 * Shows plan info, invoices, and a speed test comparing measured vs contracted speed.
 */
import { useEffect, useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Card,
  Col,
  DatePicker,
  Descriptions,
  Form,
  Input,
  Checkbox,
  Modal,
  Progress,
  Result,
  Row,
  Space,
  Spin,
  Statistic,
  Table,
  Tag,
  Typography,
} from "antd";
import dayjs from "dayjs";
import {
  ArrowDownOutlined,
  ArrowUpOutlined,
  CalendarOutlined,
  CheckCircleOutlined,
  ReloadOutlined,
  FileProtectOutlined,
  ExclamationCircleOutlined,
  SafetyOutlined,
  ThunderboltOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import axios from "axios";

const { Title, Text, Paragraph } = Typography;

interface PortalData {
  client: {
    id: number;
    full_name: string;
    ip_address: string;
    status: string;
  };
  plan: {
    name: string;
    download_mbps: number;
    upload_mbps: number;
    burst_download_mbps?: number;
    burst_upload_mbps?: number;
  } | null;
  invoices: {
    id: number;
    amount: number;
    status: string;
    due_date: string | null;
    period: string | null;
  }[];
}

interface SecurityData {
  has_subscription: boolean;
  subscription?: {
    id: number;
    status: string;
    plan_name: string;
    beat_account_id?: string;
    property_name: string;
    property_address: string;
    entry_secure_enabled: boolean;
  };
  active_alerts: number;
  recent_events: {
    event_type: string;
    occurred_at: string;
    zone_number?: number;
    description?: string;
  }[];
  last_report?: {
    period: string;
    event_count: number;
    alert_count: number;
  } | null;
}

interface ContractState {
  enabled: boolean;
  template?: { version: string; title: string; body: string; body_hash: string } | null;
  accepted?: { accepted_at: string; signer_name?: string; has_pdf: boolean } | null;
}

interface SpeedResult {
  download_mbps: number | null;
  upload_mbps: number | null;
  ping_ms: number | null;
}

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  active: { label: "Activo", color: "green" },
  suspended: { label: "Suspendido", color: "orange" },
  cancelled: { label: "Cancelado", color: "red" },
};

const EVENT_LABELS: Record<string, string> = {
  armed: "Armado", disarmed: "Desarmado", intrusion: "Intrusión",
  battery_low: "Batería baja", power_failure: "Falla de energía",
  power_restored: "Energía restaurada", communication_lost: "Sin señal",
  tamper: "Manipulación", zone_open: "Zona abierta",
  test: "Prueba", panic: "Pánico", duress: "Coacción", other: "Otro",
};

const EVENT_COLORS: Record<string, string> = {
  intrusion: "red", panic: "red", duress: "red", tamper: "red",
  armed: "blue", disarmed: "green", test: "default",
  battery_low: "orange", power_failure: "orange", communication_lost: "orange",
};

const INVOICE_STATUS: Record<string, { label: string; color: string }> = {
  pending: { label: "Pendiente", color: "gold" },
  paid: { label: "Pagado", color: "green" },
  overdue: { label: "Vencida", color: "red" },
  cancelled: { label: "Cancelada", color: "default" },
};

// ── Speed test engine ─────────────────────────────────────────────────────────

const DOWNLOAD_URL = "/api/v1/portal/speedtest/download";
const UPLOAD_URL = "/api/v1/portal/speedtest/upload";
const UPLOAD_SIZE_MB = 3;

async function measureDownload(onProgress: (mbps: number) => void): Promise<number> {
  const start = performance.now();
  const res = await fetch(DOWNLOAD_URL, { cache: "no-store" });
  const reader = res.body!.getReader();
  let bytes = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    bytes += value.byteLength;
    const elapsed = (performance.now() - start) / 1000;
    onProgress(Math.round((bytes * 8) / elapsed / 1_000_000));
  }
  const elapsed = (performance.now() - start) / 1000;
  return Math.round((bytes * 8) / elapsed / 1_000_000);
}

async function measureUpload(onProgress: (mbps: number) => void): Promise<number> {
  const payload = new Uint8Array(UPLOAD_SIZE_MB * 1024 * 1024);
  crypto.getRandomValues(payload);
  const start = performance.now();
  await fetch(UPLOAD_URL, {
    method: "POST",
    body: payload,
    cache: "no-store",
  });
  const elapsed = (performance.now() - start) / 1000;
  const mbps = Math.round((payload.byteLength * 8) / elapsed / 1_000_000);
  onProgress(mbps);
  return mbps;
}

async function measurePing(): Promise<number> {
  const times: number[] = [];
  for (let i = 0; i < 4; i++) {
    const t0 = performance.now();
    await fetch(DOWNLOAD_URL + "?ping=1", { cache: "no-store", method: "HEAD" }).catch(() => {});
    times.push(performance.now() - t0);
  }
  times.sort((a, b) => a - b);
  return Math.round(times.slice(1, 3).reduce((a, b) => a + b, 0) / 2);
}

// ── Gauge ─────────────────────────────────────────────────────────────────────

function SpeedGauge({
  label,
  measured,
  contracted,
  icon,
  color,
}: {
  label: string;
  measured: number | null;
  contracted: number;
  icon: React.ReactNode;
  color: string;
}) {
  const pct = measured != null ? Math.min(100, Math.round((measured / contracted) * 100)) : 0;
  const gaugeColor =
    pct >= 80 ? "#52c41a" : pct >= 50 ? "#faad14" : "#f5222d";

  return (
    <Card size="small" style={{ textAlign: "center" }}>
      <div style={{ fontSize: 13, color: "#8c8c8c", marginBottom: 4 }}>
        {icon} {label}
      </div>
      <div style={{ fontSize: 36, fontWeight: 700, color: gaugeColor, lineHeight: 1.1 }}>
        {measured != null ? measured : "—"}
      </div>
      <div style={{ fontSize: 12, color: "#8c8c8c" }}>Mbps medidos</div>
      <Progress
        percent={pct}
        strokeColor={gaugeColor}
        size="small"
        style={{ marginTop: 8 }}
        format={() => `${pct}%`}
      />
      <div style={{ marginTop: 4, fontSize: 12 }}>
        <Text type="secondary">Contratado: </Text>
        <Text strong>{contracted} Mbps</Text>
      </div>
      {measured != null && (
        <div style={{ marginTop: 4 }}>
          {pct >= 80 ? (
            <Tag color="green">Velocidad correcta</Tag>
          ) : pct >= 50 ? (
            <Tag color="orange">Por debajo de lo esperado</Tag>
          ) : (
            <Tag color="red">Muy por debajo</Tag>
          )}
        </div>
      )}
    </Card>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Portal({ appMode = false }: { appMode?: boolean } = {}) {
  // In the mobile app the device credential travels in the Authorization header
  const portalToken = appMode ? null : new URLSearchParams(window.location.search).get("token");

  const [data, setData] = useState<PortalData | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState<string | null>(null);

  const [security, setSecurity] = useState<SecurityData | null>(null);
  const [entryLoading, setEntryLoading] = useState(false);
  const [entryResult, setEntryResult] = useState<{ expires_at: string; duration_minutes: number } | null>(null);
  const [entryError, setEntryError] = useState<string | null>(null);

  const [vacation, setVacation] = useState<{ active: boolean; start_date: string | null; end_date: string | null; vacation_mode_enabled: boolean } | null>(null);
  const [vacationLoading, setVacationLoading] = useState(false);
  const [vacationError, setVacationError] = useState<string | null>(null);
  const [showVacationForm, setShowVacationForm] = useState(false);
  const [showCancelPin, setShowCancelPin] = useState(false);
  const [cancelPin, setCancelPin] = useState("");

  const [contract, setContract] = useState<ContractState | null>(null);
  const [signOpen, setSignOpen] = useState(false);
  const [signLoading, setSignLoading] = useState(false);
  const [signError, setSignError] = useState<string | null>(null);
  const [signForm] = Form.useForm();
  const [vacationForm] = Form.useForm();

  const [testing, setTesting] = useState(false);
  const [phase, setPhase] = useState<"idle" | "ping" | "download" | "upload" | "done">("idle");
  const [liveDown, setLiveDown] = useState<number | null>(null);
  const [liveUp, setLiveUp] = useState<number | null>(null);
  const [result, setResult] = useState<SpeedResult>({
    download_mbps: null,
    upload_mbps: null,
    ping_ms: null,
  });

  function loadAppData() {
    axios
      .get<SecurityData>("/api/v1/mobile/security")
      .then((r) => { setSecurity(r.data); setNotFound(null); })
      .catch((e) => {
        if (e.response?.status !== 401) setNotFound(e.response?.data?.detail ?? "No se pudo conectar con el servidor");
      })
      .finally(() => setLoading(false));
    axios
      .get("/api/v1/portal/security/vacation")
      .then((r) => setVacation(r.data))
      .catch(() => {});
    loadContract();
  }

  useEffect(() => {
    if (!appMode) return;
    loadAppData();
    const id = setInterval(() => {
      if (document.visibilityState === "visible") loadAppData();
    }, 30_000);
    return () => clearInterval(id);
  }, [appMode]);

  useEffect(() => {
    if (appMode) return;
    if (portalToken) {
      // Security-only client: identified by portal token, no internet service
      axios
        .get<SecurityData>(`/api/v1/portal/security/token/${portalToken}`)
        .then((r) => setSecurity(r.data))
        .catch((e) => setNotFound(e.response?.data?.detail ?? "Enlace inválido o suscripción inactiva"))
        .finally(() => setLoading(false));

      axios
        .get("/api/v1/portal/security/vacation", { params: { token: portalToken } })
        .then((r) => setVacation(r.data))
        .catch(() => {});
    } else {
      axios
        .get<PortalData>("/api/v1/portal/by-ip")
        .then((r) => setData(r.data))
        .catch((e) => setNotFound(e.response?.data?.detail ?? "Error al cargar datos"))
        .finally(() => setLoading(false));

      axios
        .get<SecurityData>("/api/v1/portal/security")
        .then((r) => setSecurity(r.data))
        .catch(() => setSecurity(null));

      axios
        .get("/api/v1/portal/security/vacation")
        .then((r) => setVacation(r.data))
        .catch(() => {});
    }

    loadContract();
  }, [portalToken, appMode]);

  function loadContract() {
    axios
      .get<ContractState>("/api/v1/portal/security/contract", { params: portalToken ? { token: portalToken } : {} })
      .then((r) => setContract(r.data))
      .catch(() => setContract(null));
  }

  async function signContract({ full_name, dni, pin }: { full_name: string; dni: string; pin: string }) {
    if (!contract?.template) return;
    setSignLoading(true);
    setSignError(null);
    try {
      await axios.post("/api/v1/portal/security/contract/accept", {
        full_name,
        dni,
        pin,
        document_hash: contract.template.body_hash,
        ...(portalToken ? { token: portalToken } : {}),
      });
      setSignOpen(false);
      signForm.resetFields();
      loadContract();
    } catch (e: any) {
      const d = e.response?.data?.detail;
      setSignError(Array.isArray(d) ? d[0]?.msg?.replace("Value error, ", "") : d ?? "No se pudo firmar el contrato");
      signForm.setFieldValue("pin", "");
      if (e.response?.status === 409) loadContract();
    } finally {
      setSignLoading(false);
    }
  }

  async function activateVacation(values: { start_date: dayjs.Dayjs; end_date: dayjs.Dayjs }) {
    setVacationLoading(true);
    setVacationError(null);
    try {
      const r = await axios.post("/api/v1/portal/security/vacation", {
        start_date: values.start_date.format("YYYY-MM-DD"),
        end_date: values.end_date.format("YYYY-MM-DD"),
        ...(portalToken ? { token: portalToken } : {}),
      });
      setVacation({ active: true, start_date: r.data.start_date, end_date: r.data.end_date, vacation_mode_enabled: true });
      setShowVacationForm(false);
      vacationForm.resetFields();
    } catch (e: any) {
      setVacationError(e.response?.data?.detail ?? "Error al activar modo ausencia");
    } finally {
      setVacationLoading(false);
    }
  }

  async function cancelVacation() {
    if (!cancelPin) {
      setVacationError("Ingresá el PIN de tu alarma");
      return;
    }
    setVacationLoading(true);
    setVacationError(null);
    try {
      await axios.post("/api/v1/portal/security/vacation/cancel", {
        pin: cancelPin,
        ...(portalToken ? { token: portalToken } : {}),
      });
      setVacation((v) => v ? { ...v, active: false } : null);
      setShowCancelPin(false);
    } catch (e: any) {
      setVacationError(e.response?.data?.detail ?? "Error al cancelar");
    } finally {
      setCancelPin("");
      setVacationLoading(false);
    }
  }

  async function startEntrySession() {
    setEntryLoading(true);
    setEntryError(null);
    setEntryResult(null);
    try {
      const r = await axios.post<{ expires_at: string; duration_minutes: number }>(
        "/api/v1/portal/security/entry-session",
        { duration_minutes: 5, ...(portalToken ? { token: portalToken } : {}) },
      );
      setEntryResult(r.data);
    } catch (e: any) {
      setEntryError(e.response?.data?.detail ?? "Error al iniciar sesión");
    } finally {
      setEntryLoading(false);
    }
  }

  async function runSpeedTest() {
    setTesting(true);
    setPhase("ping");
    setLiveDown(null);
    setLiveUp(null);
    setResult({ download_mbps: null, upload_mbps: null, ping_ms: null });

    try {
      const ping = await measurePing();
      setResult((r) => ({ ...r, ping_ms: ping }));

      setPhase("download");
      const dl = await measureDownload(setLiveDown);
      setResult((r) => ({ ...r, download_mbps: dl }));
      setLiveDown(dl);

      setPhase("upload");
      const ul = await measureUpload(setLiveUp);
      setResult((r) => ({ ...r, upload_mbps: ul }));
      setLiveUp(ul);

      setPhase("done");
    } catch {
      setPhase("idle");
    } finally {
      setTesting(false);
    }
  }

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "100vh" }}>
        <Spin size="large" />
      </div>
    );
  }

  if (notFound) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "100vh", padding: 24 }}>
        <Result
          status="404"
          title="No encontrado"
          subTitle={notFound}
        />
      </div>
    );
  }

  if (!portalToken && !appMode && !data) return null;

  const plan = data?.plan ?? null;
  const statusInfo = data ? (STATUS_LABELS[data.client.status] ?? { label: data.client.status, color: "default" }) : null;
  const pendingInvoices = data?.invoices.filter((i) => i.status === "pending" || i.status === "overdue") ?? [];

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: "24px 16px" }}>
      {/* Header */}
      <div style={{ marginBottom: 24, textAlign: "center" }}>
        <Title level={3} style={{ margin: 0 }}>{appMode ? "Mi propiedad" : "Portal de clientes"}</Title>
        <Text type="secondary">{appMode ? "Guaynet Seguridad" : "Guaynet WISP"}</Text>
        {appMode && (
          <div style={{ marginTop: 8 }}>
            <Button size="small" icon={<ReloadOutlined />} onClick={loadAppData}>Actualizar</Button>
          </div>
        )}
      </div>

      {/* Client info — internet clients only */}
      {data && statusInfo && (
        <Card style={{ marginBottom: 16 }}>
          <Descriptions column={2} size="small">
            <Descriptions.Item label="Nombre">{data.client.full_name}</Descriptions.Item>
            <Descriptions.Item label="Estado">
              <Tag color={statusInfo.color}>{statusInfo.label}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="IP">{data.client.ip_address}</Descriptions.Item>
            {plan && (
              <Descriptions.Item label="Plan">
                <Text strong>{plan.name}</Text>
              </Descriptions.Item>
            )}
          </Descriptions>
        </Card>
      )}

      {/* Suspended alert */}
      {data?.client.status === "suspended" && (
        <Alert
          type="warning"
          showIcon
          message="Servicio suspendido"
          description="Tu servicio está temporalmente suspendido. Contactá a tu proveedor para regularizar tu situación."
          style={{ marginBottom: 16 }}
        />
      )}

      {/* Pending invoices */}
      {pendingInvoices.length > 0 && (
        <Alert
          type="error"
          showIcon
          message={`Tenés ${pendingInvoices.length} factura(s) pendiente(s) de pago`}
          description="Contactá a tu proveedor para abonar y mantener el servicio activo."
          style={{ marginBottom: 16 }}
        />
      )}

      {/* Plan contracted speeds */}
      {plan && (
        <Card title="Plan contratado" style={{ marginBottom: 16 }}>
          <Row gutter={16}>
            <Col span={12}>
              <Statistic
                title="Bajada contratada"
                value={plan.download_mbps}
                suffix="Mbps"
                prefix={<ArrowDownOutlined style={{ color: "#1677ff" }} />}
              />
            </Col>
            <Col span={12}>
              <Statistic
                title="Subida contratada"
                value={plan.upload_mbps}
                suffix="Mbps"
                prefix={<ArrowUpOutlined style={{ color: "#52c41a" }} />}
              />
            </Col>
          </Row>
          {(plan.burst_download_mbps || plan.burst_upload_mbps) && (
            <div style={{ marginTop: 8 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                Ráfaga: {plan.burst_download_mbps} Mbps bajada / {plan.burst_upload_mbps} Mbps subida
              </Text>
            </div>
          )}
        </Card>
      )}

      {/* Speed test */}
      {plan && (
        <Card
          title={<span><ThunderboltOutlined /> Test de velocidad</span>}
          style={{ marginBottom: 16 }}
          extra={
            <Button
              type="primary"
              onClick={runSpeedTest}
              loading={testing}
              disabled={testing}
            >
              {phase === "idle" || phase === "done" ? "Medir velocidad" : "Midiendo..."}
            </Button>
          }
        >
          {phase === "idle" && !result.download_mbps && (
            <Paragraph type="secondary" style={{ margin: 0 }}>
              Presioná "Medir velocidad" para comparar tu conexión actual con lo que contrataste.
            </Paragraph>
          )}

          {testing && (
            <div style={{ textAlign: "center", padding: "12px 0" }}>
              <Spin />
              <div style={{ marginTop: 8, color: "#8c8c8c" }}>
                {phase === "ping" && "Midiendo latencia..."}
                {phase === "download" && `Midiendo bajada... ${liveDown != null ? liveDown + " Mbps" : ""}`}
                {phase === "upload" && `Midiendo subida... ${liveUp != null ? liveUp + " Mbps" : ""}`}
              </div>
            </div>
          )}

          {(phase === "done" || result.download_mbps != null) && !testing && (
            <div>
              {result.ping_ms != null && (
                <div style={{ textAlign: "center", marginBottom: 12 }}>
                  <Text type="secondary">Latencia: </Text>
                  <Text strong>{result.ping_ms} ms</Text>
                  {"  "}
                  <Tag color={result.ping_ms < 30 ? "green" : result.ping_ms < 80 ? "orange" : "red"}>
                    {result.ping_ms < 30 ? "Excelente" : result.ping_ms < 80 ? "Normal" : "Alta"}
                  </Tag>
                </div>
              )}
              <Row gutter={16}>
                <Col xs={24} sm={12}>
                  <SpeedGauge
                    label="Bajada"
                    measured={result.download_mbps}
                    contracted={plan.download_mbps}
                    icon={<ArrowDownOutlined />}
                    color="#1677ff"
                  />
                </Col>
                <Col xs={24} sm={12} style={{ marginTop: 16 }}>
                  <SpeedGauge
                    label="Subida"
                    measured={result.upload_mbps}
                    contracted={plan.upload_mbps}
                    icon={<ArrowUpOutlined />}
                    color="#52c41a"
                  />
                </Col>
              </Row>
              <Paragraph type="secondary" style={{ marginTop: 12, fontSize: 12 }}>
                Si la velocidad medida está consistentemente por debajo del 80% de lo contratado,
                contactá a tu proveedor.
              </Paragraph>
            </div>
          )}
        </Card>
      )}

      {/* Invoices */}
      {data && data.invoices.length > 0 && (
        <Card title="Últimas facturas">
          <Table
            dataSource={data.invoices}
            rowKey="id"
            size="small"
            pagination={false}
            columns={[
              {
                title: "Período",
                dataIndex: "period",
                key: "period",
                render: (v: string) => v || "—",
              },
              {
                title: "Vencimiento",
                dataIndex: "due_date",
                key: "due_date",
                render: (v: string) => v ? new Date(v).toLocaleDateString("es-AR") : "—",
              },
              {
                title: "Monto",
                dataIndex: "amount",
                key: "amount",
                render: (v: number) => `$${v.toFixed(2)}`,
              },
              {
                title: "Estado",
                dataIndex: "status",
                key: "status",
                render: (v: string) => {
                  const s = INVOICE_STATUS[v] ?? { label: v, color: "default" };
                  return <Tag color={s.color}>{s.label}</Tag>;
                },
              },
            ]}
          />
        </Card>
      )}

      {/* Security section */}
      {security?.has_subscription && security.subscription && (
        <>
          <Card
            title={<span><SafetyOutlined /> Guaynet Seguridad</span>}
            style={{ marginBottom: 16, marginTop: 16 }}
            extra={
              security.active_alerts > 0 ? (
                <Tag color="red" icon={<WarningOutlined />}>
                  {security.active_alerts} alerta{security.active_alerts > 1 ? "s" : ""} activa{security.active_alerts > 1 ? "s" : ""}
                </Tag>
              ) : (
                <Tag color="green" icon={<CheckCircleOutlined />}>Sin alertas</Tag>
              )
            }
          >
            <Descriptions column={{ xs: 1, sm: 2 }} size="small" style={{ marginBottom: 12 }}>
              <Descriptions.Item label="Propiedad">{security.subscription.property_name}</Descriptions.Item>
              <Descriptions.Item label="Plan">{security.subscription.plan_name}</Descriptions.Item>
              <Descriptions.Item label="Estado">
                <Tag color={security.subscription.status === "active" ? "green" : "orange"}>
                  {security.subscription.status === "active" ? "Activo" : security.subscription.status}
                </Tag>
              </Descriptions.Item>
              {security.subscription.beat_account_id && (
                <Descriptions.Item label="Cuenta monitoreo">
                  {security.subscription.beat_account_id}
                </Descriptions.Item>
              )}
            </Descriptions>

            {/* Recent events */}
            {security.recent_events.length > 0 && (
              <>
                <Text type="secondary" style={{ fontSize: 12 }}>Últimos eventos</Text>
                <Table
                  dataSource={security.recent_events}
                  rowKey={(r) => r.occurred_at}
                  size="small"
                  pagination={false}
                  style={{ marginTop: 6, marginBottom: 12 }}
                  columns={[
                    {
                      title: "Tipo",
                      dataIndex: "event_type",
                      key: "event_type",
                      render: (t: string) => (
                        <Tag color={EVENT_COLORS[t] ?? "default"}>
                          {EVENT_LABELS[t] ?? t}
                        </Tag>
                      ),
                    },
                    {
                      title: "Fecha/Hora",
                      dataIndex: "occurred_at",
                      key: "occurred_at",
                      render: (v: string) => new Date(v).toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short" }),
                    },
                    {
                      title: "Zona",
                      dataIndex: "zone_number",
                      key: "zone_number",
                      render: (v?: number) => v != null ? `Zona ${v}` : "—",
                    },
                  ]}
                />
              </>
            )}

            {/* Entry secure */}
            {security.subscription.entry_secure_enabled && (
              <div style={{ borderTop: "1px solid #f0f0f0", paddingTop: 12 }}>
                <div style={{ marginBottom: 8 }}>
                  <Text strong>Entrada segura</Text>
                  <br />
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    Iniciá una cuenta regresiva de 5 minutos. Si no ingresás tu PIN en el teclado antes de que expire, se notifica a la central.
                  </Text>
                </div>
                {entryResult ? (
                  <Alert
                    type="success"
                    icon={<CheckCircleOutlined />}
                    showIcon
                    message={`Sesión activa — tenés ${entryResult.duration_minutes} min para ingresar tu PIN`}
                    description={`Expira: ${new Date(entryResult.expires_at).toLocaleTimeString("es-AR")}`}
                  />
                ) : (
                  <>
                    {entryError && (
                      <Alert type="error" message={entryError} showIcon style={{ marginBottom: 8 }} />
                    )}
                    <Button
                      icon={<SafetyOutlined />}
                      loading={entryLoading}
                      onClick={startEntrySession}
                    >
                      Iniciar entrada segura
                    </Button>
                  </>
                )}
              </div>
            )}

            {/* Vacation mode */}
            {vacation?.vacation_mode_enabled && (
              <div style={{ borderTop: "1px solid #f0f0f0", paddingTop: 12, marginTop: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                  <Text strong><CalendarOutlined /> Modo ausencia</Text>
                  {vacation.active ? (
                    vacation.start_date && dayjs(vacation.start_date).isAfter(dayjs(), "day") ? (
                      <Tag color="blue">
                        Programado {dayjs(vacation.start_date).format("DD/MM")} → {dayjs(vacation.end_date).format("DD/MM/YYYY")}
                      </Tag>
                    ) : (
                      <Tag color="orange">Activo hasta {vacation.end_date ? dayjs(vacation.end_date).format("DD/MM/YYYY") : "—"}</Tag>
                    )
                  ) : (
                    <Tag color="default">Inactivo</Tag>
                  )}
                </div>
                {vacationError && <Alert type="error" message={vacationError} showIcon style={{ marginBottom: 8 }} />}
                {vacation.active ? (
                  <div>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      El monitoreo está en modo elevado. Cualquier apertura de zona generará una alerta inmediata.
                    </Text>
                    <br />
                    {!showCancelPin ? (
                      <Button
                        size="small"
                        danger
                        style={{ marginTop: 8 }}
                        onClick={() => { setShowCancelPin(true); setVacationError(null); }}
                      >
                        Cancelar modo ausencia
                      </Button>
                    ) : (
                      <Space wrap style={{ marginTop: 8 }}>
                        <Input.Password
                          size="small"
                          placeholder="PIN de la alarma"
                          inputMode="numeric"
                          autoComplete="off"
                          maxLength={8}
                          value={cancelPin}
                          onChange={(e) => setCancelPin(e.target.value)}
                          onPressEnter={cancelVacation}
                          style={{ width: 160 }}
                        />
                        <Button size="small" danger loading={vacationLoading} onClick={cancelVacation}>
                          Confirmar
                        </Button>
                        <Button size="small" onClick={() => { setShowCancelPin(false); setCancelPin(""); }}>
                          Volver
                        </Button>
                      </Space>
                    )}
                  </div>
                ) : (
                  <>
                    {!showVacationForm ? (
                      <Button
                        size="small"
                        icon={<CalendarOutlined />}
                        onClick={() => setShowVacationForm(true)}
                      >
                        Activar modo ausencia
                      </Button>
                    ) : (
                      <Form form={vacationForm} layout="inline" onFinish={activateVacation} style={{ marginTop: 8, flexWrap: "wrap", gap: 8 }}>
                        <Form.Item name="start_date" rules={[{ required: true }]} style={{ marginBottom: 8 }}>
                          <DatePicker placeholder="Salida" format="DD/MM/YYYY" />
                        </Form.Item>
                        <Form.Item name="end_date" rules={[{ required: true }]} style={{ marginBottom: 8 }}>
                          <DatePicker placeholder="Regreso" format="DD/MM/YYYY" />
                        </Form.Item>
                        <Space>
                          <Button type="primary" htmlType="submit" size="small" loading={vacationLoading}>
                            Confirmar
                          </Button>
                          <Button size="small" onClick={() => setShowVacationForm(false)}>
                            Cancelar
                          </Button>
                        </Space>
                      </Form>
                    )}
                  </>
                )}
              </div>
            )}

            {/* Electronic contract */}
            {contract?.enabled && contract.template && (
              <div style={{ borderTop: "1px solid #f0f0f0", paddingTop: 12, marginTop: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                  <Text strong><FileProtectOutlined /> Contrato</Text>
                  {contract.accepted ? (
                    <Space size={8} wrap>
                      <Tag color="green">Firmado el {dayjs(contract.accepted.accepted_at).format("DD/MM/YYYY")}</Tag>
                      {contract.accepted.has_pdf && !appMode && (
                        <a
                          href={`/api/v1/portal/security/contract/pdf${portalToken ? `?token=${encodeURIComponent(portalToken)}` : ""}`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Descargar copia
                        </a>
                      )}
                    </Space>
                  ) : (
                    <Tag color="gold">Pendiente de firma</Tag>
                  )}
                </div>
                {!contract.accepted && (
                  <div style={{ marginTop: 8 }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {contract.template.title} (versión {contract.template.version}). Leelo y firmalo con el PIN de tu alarma.
                    </Text>
                    <br />
                    <Button size="small" type="primary" style={{ marginTop: 8 }} onClick={() => { setSignError(null); setSignOpen(true); }}>
                      Leer y firmar
                    </Button>
                  </div>
                )}
              </div>
            )}

            {/* Last report */}
            {security.last_report && (
              <div style={{ borderTop: "1px solid #f0f0f0", paddingTop: 12, marginTop: 12 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  Último reporte mensual ({security.last_report.period}): {security.last_report.event_count} eventos · {security.last_report.alert_count} alertas
                </Text>
              </div>
            )}
          </Card>
        </>
      )}

      <Modal
        open={signOpen && !!contract?.template}
        title={contract?.template ? `${contract.template.title} — versión ${contract.template.version}` : ""}
        onCancel={() => setSignOpen(false)}
        footer={null}
        width={720}
      >
        {contract?.template && (
          <>
            <div
              style={{
                whiteSpace: "pre-wrap",
                maxHeight: "45vh",
                overflow: "auto",
                fontSize: 13,
                border: "1px solid #f0f0f0",
                borderRadius: 6,
                padding: 12,
                marginBottom: 16,
              }}
            >
              {contract.template.body}
            </div>
            {signError && <Alert type="error" showIcon message={signError} style={{ marginBottom: 12 }} />}
            <Form form={signForm} layout="vertical" onFinish={signContract} requiredMark={false}>
              <Row gutter={12}>
                <Col xs={24} sm={14}>
                  <Form.Item name="full_name" label="Nombre y apellido" rules={[{ required: true, min: 3, message: "Ingresá tu nombre completo" }]}>
                    <Input maxLength={150} autoComplete="name" />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={10}>
                  <Form.Item name="dni" label="DNI" rules={[{ required: true, message: "Ingresá tu DNI" }]}>
                    <Input inputMode="numeric" maxLength={11} />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item name="pin" label="PIN de tu alarma" rules={[{ required: true, message: "Ingresá el PIN" }]}>
                <Input.Password inputMode="numeric" autoComplete="off" maxLength={12} style={{ maxWidth: 200 }} />
              </Form.Item>
              <Form.Item
                name="agree"
                valuePropName="checked"
                rules={[{ validator: (_, v) => (v ? Promise.resolve() : Promise.reject(new Error("Tenés que aceptar el contrato"))) }]}
              >
                <Checkbox>Leí el contrato completo y lo acepto.</Checkbox>
              </Form.Item>
              <Text type="secondary" style={{ fontSize: 11, display: "block", marginBottom: 12 }}>
                Se registrarán tu nombre, DNI, la fecha, tu dirección IP y una huella del texto aceptado.
                Vas a poder descargar una copia en PDF.
              </Text>
              <Space>
                <Button type="primary" htmlType="submit" loading={signLoading}>Firmar contrato</Button>
                <Button onClick={() => setSignOpen(false)}>Cancelar</Button>
              </Space>
            </Form>
          </>
        )}
      </Modal>

      <div style={{ textAlign: "center", marginTop: 24 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>{appMode ? "Guaynet Seguridad" : "Guaynet WISP — Portal del cliente"}</Text>
      </div>
    </div>
  );
}

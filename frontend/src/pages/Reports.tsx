import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Card, Col, Progress, Row, Statistic, Table, Tag, Tooltip, Typography } from "antd";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as ChartTooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, ComposedChart,
} from "recharts";
import { reportsApi } from "@/services/api";

const { Title } = Typography;

const STATUS_COLORS: Record<string, string> = {
  paid: "#52c41a",
  pending: "#1677ff",
  overdue: "#ff4d4f",
  draft: "#8c8c8c",
  cancelled: "#bfbfbf",
};

const STATUS_LABELS: Record<string, string> = {
  paid: "Pagada",
  pending: "Pendiente",
  overdue: "Vencida",
  draft: "Borrador",
  cancelled: "Cancelada",
};

const METHOD_LABELS: Record<string, string> = {
  cash: "Efectivo",
  transfer: "Transferencia",
  mercadopago: "MercadoPago",
  other: "Otro",
};

const PIE_COLORS = ["#1677ff", "#52c41a", "#fa8c16", "#eb2f96", "#722ed1"];

const formatARS = (v: number) =>
  new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 }).format(v);

export default function Reports() {
  const { data: monthly = [] } = useQuery({
    queryKey: ["reports-monthly"],
    queryFn: () => reportsApi.monthlyRevenue(12),
  });

  const { data: statusBreakdown = [] } = useQuery({
    queryKey: ["reports-status"],
    queryFn: reportsApi.invoiceStatusBreakdown,
  });

  const { data: clientsByPlan = [] } = useQuery({
    queryKey: ["reports-clients-plan"],
    queryFn: reportsApi.clientsByPlan,
  });

  const { data: paymentMethods = [] } = useQuery({
    queryKey: ["reports-methods"],
    queryFn: reportsApi.paymentMethods,
  });

  const { data: arpu = [] } = useQuery({
    queryKey: ["reports-arpu"],
    queryFn: reportsApi.arpu,
  });

  const { data: churn = [] } = useQuery({
    queryKey: ["reports-churn"],
    queryFn: () => reportsApi.churn(12),
  });

  const { data: revenueZone = [] } = useQuery({
    queryKey: ["reports-zone"],
    queryFn: reportsApi.revenueByZone,
  });

  const { data: oversubscription = [] } = useQuery({
    queryKey: ["reports-oversubscription"],
    queryFn: reportsApi.oversubscription,
  });

  const { data: upgradeCandidates = [] } = useQuery({
    queryKey: ["reports-upgrade-candidates"],
    queryFn: () => reportsApi.upgradeCandidates(30, 80),
  });

  const navigate = useNavigate();

  const totalRevenue = monthly.reduce((s, m) => s + m.revenue, 0);
  const lastMonth = monthly[monthly.length - 1];
  const prevMonth = monthly[monthly.length - 2];
  const paidInvoices = statusBreakdown.find((s) => s.status === "paid");
  const pendingInvoices = statusBreakdown.find((s) => s.status === "pending");
  const overdueInvoices = statusBreakdown.find((s) => s.status === "overdue");

  const avgArpu = arpu.length > 0 ? arpu.reduce((s, a) => s + a.avg_invoice, 0) / arpu.length : 0;
  const lastChurn = churn[churn.length - 1];
  const churnRate = lastChurn && lastChurn.total_active > 0
    ? ((lastChurn.suspended + lastChurn.cancelled) / lastChurn.total_active) * 100
    : 0;

  return (
    <div style={{ padding: 24 }}>
      <Title level={4}>Reportes financieros</Title>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic
              title="Facturado (últimos 12 meses)"
              value={totalRevenue}
              formatter={(v) => formatARS(Number(v))}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic
              title="Mes actual"
              value={lastMonth?.revenue ?? 0}
              formatter={(v) => formatARS(Number(v))}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic
              title="Pendientes de cobro"
              value={pendingInvoices?.total ?? 0}
              formatter={(v) => formatARS(Number(v))}
              valueStyle={{ color: "#1677ff" }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic
              title="Vencidas sin cobrar"
              value={overdueInvoices?.total ?? 0}
              formatter={(v) => formatARS(Number(v))}
              valueStyle={{ color: "#ff4d4f" }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col xs={24} lg={16}>
          <Card title="Ingresos mensuales (facturación cobrada)">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={monthly} margin={{ top: 4, right: 8, left: 8, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="period" tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 11 }} />
                <ChartTooltip formatter={(v: number) => formatARS(v)} />
                <Bar dataKey="revenue" fill="#1677ff" name="Cobrado" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="Estado de facturas">
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie
                  data={statusBreakdown.map((s) => ({
                    name: STATUS_LABELS[s.status] ?? s.status,
                    value: s.total,
                    count: s.count,
                  }))}
                  cx="50%"
                  cy="50%"
                  outerRadius={90}
                  dataKey="value"
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  labelLine={false}
                >
                  {statusBreakdown.map((s) => (
                    <Cell key={s.status} fill={STATUS_COLORS[s.status] ?? "#8c8c8c"} />
                  ))}
                </Pie>
                <ChartTooltip formatter={(v: number) => formatARS(v)} />
              </PieChart>
            </ResponsiveContainer>
          </Card>
        </Col>
      </Row>

      {/* Advanced analytics summary */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col xs={12} sm={8}>
          <Card>
            <Statistic
              title="ARPU Promedio"
              value={avgArpu}
              formatter={(v) => formatARS(Number(v))}
              valueStyle={{ color: "#722ed1" }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={8}>
          <Card>
            <Statistic
              title="Churn rate último mes"
              value={churnRate}
              precision={1}
              suffix="%"
              valueStyle={{ color: churnRate > 5 ? "#ff4d4f" : "#52c41a" }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={8}>
          <Card>
            <Statistic title="Zonas activas" value={revenueZone.filter(z => z.zone_name !== "Sin zona").length} />
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col xs={24} lg={12}>
          <Card title="Clientes por plan">
            <ResponsiveContainer width="100%" height={240}>
              <BarChart
                data={clientsByPlan}
                layout="vertical"
                margin={{ top: 4, right: 24, left: 8, bottom: 4 }}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="plan" width={120} tick={{ fontSize: 11 }} />
                <ChartTooltip />
                <Bar dataKey="count" fill="#52c41a" name="Clientes" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="Métodos de pago">
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie
                  data={paymentMethods.map((m) => ({
                    name: METHOD_LABELS[m.method] ?? m.method,
                    value: m.total,
                    count: m.count,
                  }))}
                  cx="50%"
                  cy="50%"
                  outerRadius={90}
                  dataKey="value"
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  labelLine={false}
                >
                  {paymentMethods.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <ChartTooltip formatter={(v: number) => formatARS(v)} />
              </PieChart>
            </ResponsiveContainer>
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginTop: 24 }}>
        <Col xs={24} lg={12}>
          <Card title="ARPU por Plan">
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={arpu} margin={{ top: 4, right: 8, left: 8, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="plan_name" tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 11 }} />
                <ChartTooltip formatter={(v: number) => formatARS(v)} />
                <Bar dataKey="avg_invoice" name="ARPU" radius={[4, 4, 0, 0]}>
                  {arpu.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="Revenue por Zona">
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie
                  data={revenueZone.map((z) => ({ name: z.zone_name, value: z.total_revenue, color: z.color }))}
                  cx="50%"
                  cy="50%"
                  outerRadius={90}
                  dataKey="value"
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  labelLine={false}
                >
                  {revenueZone.map((z, i) => (
                    <Cell key={i} fill={z.color} />
                  ))}
                </Pie>
                <ChartTooltip formatter={(v: number) => formatARS(v)} />
              </PieChart>
            </ResponsiveContainer>
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginTop: 24, marginBottom: 8 }}>
        <Col xs={24}>
          <Card title="Churn Mensual (suspendidos + cancelados)">
            <ResponsiveContainer width="100%" height={260}>
              <ComposedChart data={churn} margin={{ top: 4, right: 8, left: 8, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="period" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <ChartTooltip />
                <Legend />
                <Bar dataKey="suspended" name="Suspendidos" fill="#fa8c16" radius={[4, 4, 0, 0]} stackId="a" />
                <Bar dataKey="cancelled" name="Cancelados" fill="#ff4d4f" radius={[4, 4, 0, 0]} stackId="a" />
              </ComposedChart>
            </ResponsiveContainer>
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginTop: 24 }}>
        <Col xs={24}>
          <Card title="Sobresubscripción por Router">
            <Table
              dataSource={oversubscription}
              rowKey="router_id"
              size="small"
              pagination={false}
              columns={[
                {
                  title: "Router",
                  key: "router",
                  render: (_: unknown, r: typeof oversubscription[0]) => (
                    <span>{r.router_name}{r.location ? ` (${r.location})` : ""}</span>
                  ),
                },
                { title: "Clientes activos", dataIndex: "active_clients", key: "clients" },
                {
                  title: "Capacidad DL",
                  key: "cap_dl",
                  render: (_: unknown, r: typeof oversubscription[0]) =>
                    r.uplink_download_mbps ? `${r.uplink_download_mbps} Mbps` : "—",
                },
                {
                  title: "Suscripto DL",
                  key: "sub_dl",
                  render: (_: unknown, r: typeof oversubscription[0]) => `${r.subscribed_download_mbps} Mbps`,
                },
                {
                  title: "Ratio DL",
                  key: "ratio_dl",
                  render: (_: unknown, r: typeof oversubscription[0]) => {
                    if (r.oversubscription_dl == null) return "—";
                    const v = r.oversubscription_dl;
                    return (
                      <Tag color={v > 5 ? "red" : v > 3 ? "orange" : "green"}>
                        {v}x
                      </Tag>
                    );
                  },
                },
                {
                  title: "Ratio UL",
                  key: "ratio_ul",
                  render: (_: unknown, r: typeof oversubscription[0]) => {
                    if (r.oversubscription_ul == null) return "—";
                    const v = r.oversubscription_ul;
                    return (
                      <Tag color={v > 5 ? "red" : v > 3 ? "orange" : "green"}>
                        {v}x
                      </Tag>
                    );
                  },
                },
              ]}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginTop: 24, marginBottom: 24 }}>
        <Col xs={24}>
          <Card title="Candidatos a upgrade de plan (últimos 30 días, pico ≥ 80%)">
            <Table
              dataSource={upgradeCandidates}
              rowKey="client_id"
              size="small"
              pagination={{ pageSize: 20 }}
              columns={[
                {
                  title: "Cliente",
                  key: "client",
                  render: (_: unknown, r: typeof upgradeCandidates[0]) => (
                    <a onClick={() => navigate(`/clients/${r.client_id}`)}>{r.client_name}</a>
                  ),
                },
                { title: "Plan actual", dataIndex: "plan_name", key: "plan" },
                {
                  title: "Velocidad",
                  key: "speed",
                  render: (_: unknown, r: typeof upgradeCandidates[0]) =>
                    `↓${r.plan_download_mbps} / ↑${r.plan_upload_mbps} Mbps`,
                },
                {
                  title: "Pico descarga",
                  dataIndex: "peak_download_pct",
                  key: "dl_pct",
                  render: (v: number) => (
                    <Tooltip title={`${v}%`}>
                      <Progress
                        percent={Math.round(v)}
                        size="small"
                        strokeColor={v >= 95 ? "#f5222d" : v >= 80 ? "#fa8c16" : "#52c41a"}
                        format={(p) => `${p}%`}
                      />
                    </Tooltip>
                  ),
                },
                {
                  title: "Pico subida",
                  dataIndex: "peak_upload_pct",
                  key: "ul_pct",
                  render: (v: number) => (
                    <Tooltip title={`${v}%`}>
                      <Progress
                        percent={Math.round(v)}
                        size="small"
                        strokeColor={v >= 95 ? "#f5222d" : v >= 80 ? "#fa8c16" : "#52c41a"}
                        format={(p) => `${p}%`}
                      />
                    </Tooltip>
                  ),
                },
              ]}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}

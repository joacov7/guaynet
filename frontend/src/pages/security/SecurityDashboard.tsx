import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Badge,
  Button,
  Card,
  Col,
  Empty,
  Row,
  Spin,
  Statistic,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import {
  AlertOutlined,
  ArrowRightOutlined,
  CalendarOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ReloadOutlined,
  ShieldOutlined,
  UnorderedListOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { securityDashboardApi } from "@/services/security/api";

const { Title, Text } = Typography;

// ── Alert metadata ────────────────────────────────────────────────────────────

const ALERT_META: Record<string, { label: string; color: string }> = {
  PANIC:              { label: "Pánico",            color: "#cf1322" },
  DURESS:             { label: "Coacción",           color: "#cf1322" },
  INTRUSION:          { label: "Intrusión",          color: "#d46b08" },
  ENTRY_TIMEOUT:      { label: "Entrada expirada",   color: "#d46b08" },
  CHECKIN_MISSED:     { label: "Sin check-in",       color: "#7c3aed" },
  INACTIVITY:         { label: "Inactividad",        color: "#7c3aed" },
  SYSTEM_FAULT:       { label: "Falla sistema",      color: "#595959" },
  CONNECTION_LOST:    { label: "Sin señal",           color: "#595959" },
  SCHEDULE_VIOLATION: { label: "Fuera de horario",   color: "#595959" },
};

const EVENT_LABELS: Record<string, string> = {
  armed: "Armado", disarmed: "Desarmado", intrusion: "Intrusión",
  battery_low: "Batería baja", power_failure: "Corte de luz",
  power_restored: "Luz restaurada", communication_lost: "Sin señal",
  tamper: "Manipulación", zone_open: "Zona abierta",
  test: "Prueba", panic: "Pánico", duress: "Coacción", other: "Otro",
};

const EVENT_COLORS: Record<string, string> = {
  intrusion: "red", panic: "red", duress: "red", tamper: "red",
  zone_open: "orange", armed: "blue", disarmed: "green",
  battery_low: "orange", power_failure: "orange", communication_lost: "orange",
};

// ── Mini bar chart ────────────────────────────────────────────────────────────

function MiniBarChart({ data }: { data: { date: string; count: number }[] }) {
  const max = Math.max(...data.map((d) => d.count), 1);
  const days = ["D", "L", "M", "M", "J", "V", "S"];

  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 4, height: 56 }}>
      {data.map((d, i) => {
        const h = Math.max(4, Math.round((d.count / max) * 48));
        const dayLabel = days[new Date(d.date + "T12:00:00").getDay()];
        return (
          <Tooltip key={d.date} title={`${d.date}: ${d.count} alertas`}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", flex: 1 }}>
              <div
                style={{
                  width: "100%",
                  height: h,
                  background: d.count > 0 ? "#1677ff" : "#d9d9d9",
                  borderRadius: 2,
                  transition: "height 0.3s",
                }}
              />
              <div style={{ fontSize: 10, color: "#8c8c8c", marginTop: 2 }}>{dayLabel}</div>
            </div>
          </Tooltip>
        );
      })}
    </div>
  );
}

// ── Live countdown helper ─────────────────────────────────────────────────────

function useNow(ms = 1000) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), ms);
    return () => clearInterval(id);
  }, [ms]);
  return now;
}

function countdown(expiresAt: string, now: number): string {
  const secs = Math.max(0, Math.floor((new Date(expiresAt).getTime() - now) / 1000));
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

// ── Main dashboard ────────────────────────────────────────────────────────────

export default function SecurityDashboard() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const now = useNow();

  const { data, isLoading, dataUpdatedAt } = useQuery({
    queryKey: ["security-dashboard"],
    queryFn: () => securityDashboardApi.get(),
    refetchInterval: 30_000,
  });

  if (isLoading || !data) {
    return (
      <div style={{ padding: 24, textAlign: "center" }}>
        <Spin size="large" />
      </div>
    );
  }

  const { stats, open_alerts, active_entry_sessions, recent_events, alerts_by_day, alerts_by_type } = data;
  const lastUpdated = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString("es-AR", { timeStyle: "medium" })
    : "—";

  return (
    <div style={{ padding: 24 }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <div>
          <Title level={3} style={{ margin: 0 }}>Panel de Seguridad</Title>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Actualización automática cada 30 s · Última: {lastUpdated}
          </Text>
        </div>
        <Button
          icon={<ReloadOutlined />}
          onClick={() => qc.invalidateQueries({ queryKey: ["security-dashboard"] })}
        >
          Actualizar
        </Button>
      </div>

      {/* KPI tiles */}
      <Row gutter={[12, 12]} style={{ marginBottom: 20 }}>
        <Col xs={12} sm={8} lg={4}>
          <Card size="small">
            <Statistic
              title="Abonados activos"
              value={stats.active_subscriptions}
              prefix={<ShieldOutlined />}
              valueStyle={{ color: "#52c41a" }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={8} lg={4}>
          <Card size="small">
            <Statistic
              title="Alertas abiertas"
              value={stats.open_alerts}
              prefix={stats.open_alerts > 0 ? <WarningOutlined /> : <CheckCircleOutlined />}
              valueStyle={{ color: stats.open_alerts > 0 ? "#cf1322" : "#52c41a" }}
            />
            {stats.open_alerts > 0 && (
              <div style={{ fontSize: 11, color: "#8c8c8c", marginTop: 2 }}>
                {stats.new_alerts} nueva{stats.new_alerts !== 1 ? "s" : ""} · {stats.acknowledged_alerts} atendiendo
              </div>
            )}
          </Card>
        </Col>
        <Col xs={12} sm={8} lg={4}>
          <Card size="small">
            <Statistic
              title="Entradas activas"
              value={stats.active_entry_sessions}
              prefix={<ClockCircleOutlined />}
              valueStyle={{ color: stats.active_entry_sessions > 0 ? "#faad14" : "#8c8c8c" }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={8} lg={4}>
          <Card size="small">
            <Statistic
              title="Modo ausencia"
              value={stats.vacation_active}
              prefix={<CalendarOutlined />}
              valueStyle={{ color: stats.vacation_active > 0 ? "#d46b08" : "#8c8c8c" }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={8} lg={4}>
          <Card size="small">
            <Statistic
              title="Alertas hoy"
              value={stats.alerts_today}
              prefix={<AlertOutlined />}
              valueStyle={{ color: stats.alerts_today > 0 ? "#d46b08" : "#8c8c8c" }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={8} lg={4}>
          <Card size="small">
            <Statistic
              title="Esta semana"
              value={stats.alerts_this_week}
              prefix={<AlertOutlined />}
              valueStyle={{ color: "#8c8c8c" }}
            />
            {stats.suspended_subscriptions > 0 && (
              <div style={{ fontSize: 11, color: "#faad14", marginTop: 2 }}>
                {stats.suspended_subscriptions} suspendido{stats.suspended_subscriptions !== 1 ? "s" : ""}
              </div>
            )}
          </Card>
        </Col>
      </Row>

      {/* Second row: open alerts + trend + sessions */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        {/* Open alerts */}
        <Col xs={24} lg={14}>
          <Card
            size="small"
            title={
              <span>
                <AlertOutlined /> Alertas abiertas
                {stats.open_alerts > 0 && (
                  <Badge count={stats.open_alerts} style={{ marginLeft: 8 }} />
                )}
              </span>
            }
            extra={
              <Button
                size="small"
                type="link"
                icon={<ArrowRightOutlined />}
                onClick={() => navigate("/security/operator-panel")}
              >
                Central
              </Button>
            }
          >
            {open_alerts.length === 0 ? (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={<Text type="secondary">Sin alertas abiertas</Text>}
                style={{ margin: "8px 0" }}
              />
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {open_alerts.map((a) => {
                  const meta = ALERT_META[a.alert_type] ?? { label: a.alert_type, color: "#595959" };
                  const secs = Math.floor((Date.now() - new Date(a.triggered_at).getTime()) / 1000);
                  const elapsed = secs < 60 ? `${secs}s` : secs < 3600 ? `${Math.floor(secs / 60)}m` : `${Math.floor(secs / 3600)}h`;
                  return (
                    <div
                      key={a.id}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        padding: "6px 10px",
                        background: a.status === "new" ? "#fff1f0" : "#fffbe6",
                        borderRadius: 4,
                        borderLeft: `3px solid ${meta.color}`,
                      }}
                    >
                      <div>
                        <Text strong style={{ color: meta.color, fontSize: 12 }}>{meta.label}</Text>
                        <Text style={{ fontSize: 12, marginLeft: 8 }}>{a.property_name}</Text>
                        {a.status === "new" && <Tag color="red" style={{ marginLeft: 6, fontSize: 10 }}>Nueva</Tag>}
                      </div>
                      <Text type="secondary" style={{ fontSize: 12, fontVariantNumeric: "tabular-nums" }}>
                        {elapsed}
                      </Text>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>
        </Col>

        {/* Trend + type breakdown */}
        <Col xs={24} lg={10}>
          <Card size="small" title="Actividad — últimos 7 días" style={{ marginBottom: 12 }}>
            <MiniBarChart data={alerts_by_day} />
          </Card>
          <Card size="small" title="Por tipo — últimos 30 días">
            {alerts_by_type.length === 0 ? (
              <Text type="secondary" style={{ fontSize: 12 }}>Sin alertas en el período</Text>
            ) : (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {alerts_by_type.map((t) => {
                  const meta = ALERT_META[t.type] ?? { label: t.type, color: "#595959" };
                  return (
                    <Tag key={t.type} style={{ borderColor: meta.color, color: meta.color, fontSize: 12 }}>
                      {meta.label} · {t.count}
                    </Tag>
                  );
                })}
              </div>
            )}
          </Card>
        </Col>
      </Row>

      {/* Third row: entry sessions + recent events */}
      <Row gutter={[16, 16]}>
        {/* Active entry sessions */}
        <Col xs={24} sm={10}>
          <Card
            size="small"
            title={<span><ClockCircleOutlined /> Entradas activas</span>}
            extra={
              <Button size="small" type="link" icon={<ArrowRightOutlined />} onClick={() => navigate("/security/entry-secure")}>
                Ver
              </Button>
            }
          >
            {active_entry_sessions.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={<Text type="secondary">Sin entradas activas</Text>} style={{ margin: "8px 0" }} />
            ) : (
              active_entry_sessions.map((s) => {
                const remaining = Math.max(0, Math.floor((new Date(s.expires_at).getTime() - now) / 1000));
                const urgent = remaining < 60;
                return (
                  <div
                    key={s.id}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      padding: "5px 0",
                      borderBottom: "1px solid #f0f0f0",
                    }}
                  >
                    <Text style={{ fontSize: 12 }}>{s.property_name}</Text>
                    <Text
                      strong
                      style={{
                        fontSize: 13,
                        color: urgent ? "#cf1322" : "#d46b08",
                        fontVariantNumeric: "tabular-nums",
                      }}
                    >
                      {countdown(s.expires_at, now)}
                    </Text>
                  </div>
                );
              })
            )}
          </Card>
        </Col>

        {/* Recent events */}
        <Col xs={24} sm={14}>
          <Card
            size="small"
            title={<span><UnorderedListOutlined /> Últimos eventos</span>}
            extra={
              <Button size="small" type="link" icon={<ArrowRightOutlined />} onClick={() => navigate("/security/events")}>
                Ver
              </Button>
            }
          >
            {recent_events.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={<Text type="secondary">Sin eventos recientes</Text>} style={{ margin: "8px 0" }} />
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {recent_events.map((e) => (
                  <div
                    key={e.id}
                    style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 12 }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <Tag color={EVENT_COLORS[e.event_type] ?? "default"} style={{ fontSize: 11, margin: 0 }}>
                        {EVENT_LABELS[e.event_type] ?? e.event_type}
                      </Tag>
                      <Text style={{ fontSize: 12 }}>{e.property_name}</Text>
                      {e.zone_number != null && (
                        <Text type="secondary" style={{ fontSize: 11 }}>z{e.zone_number}</Text>
                      )}
                    </div>
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      {new Date(e.occurred_at).toLocaleTimeString("es-AR", { timeStyle: "short" })}
                    </Text>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}

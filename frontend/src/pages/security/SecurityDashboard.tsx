import { useQuery } from "@tanstack/react-query";
import { Alert, Badge, Card, Col, Row, Spin, Statistic, Table, Tag, Typography } from "antd";
import {
  AlertOutlined,
  SafetyOutlined,
  ShieldOutlined,
  ClockCircleOutlined,
} from "@ant-design/icons";
import { alertsApi, subscriptionsApi, entrySessionsApi } from "@/services/security/api";
import type { SecurityAlert, EntrySession } from "@/types/security";

const { Title } = Typography;

const alertStatusColor: Record<string, string> = {
  new: "red",
  acknowledged: "orange",
  resolved: "green",
  false_alarm: "default",
};

const alertTypeLabel: Record<string, string> = {
  PANIC: "Pánico",
  ENTRY_TIMEOUT: "Entrada expirada",
  DURESS: "Coacción",
  INTRUSION: "Intrusión",
  CHECKIN_MISSED: "Check-in perdido",
  INACTIVITY: "Inactividad",
  SYSTEM_FAULT: "Falla sistema",
  CONNECTION_LOST: "Sin comunicación",
  SCHEDULE_VIOLATION: "Violación horario",
};

export default function SecurityDashboard() {
  const { data: subscriptions = [], isLoading: loadingSubs } = useQuery({
    queryKey: ["security-subscriptions"],
    queryFn: () => subscriptionsApi.list(),
  });

  const { data: alerts = [], isLoading: loadingAlerts } = useQuery({
    queryKey: ["security-alerts"],
    queryFn: () => alertsApi.list(),
  });

  const { data: activeSessions = [], isLoading: loadingSessions } = useQuery({
    queryKey: ["security-entry-sessions-active"],
    queryFn: () => entrySessionsApi.listActive(),
  });

  const openAlerts = alerts.filter((a) => a.status === "new" || a.status === "acknowledged");
  const activeSubs = subscriptions.filter((s) => s.status === "active");

  const alertColumns = [
    {
      title: "Tipo",
      dataIndex: "alert_type",
      key: "type",
      render: (v: string) => alertTypeLabel[v] ?? v,
    },
    {
      title: "Suscripción",
      dataIndex: "subscription_id",
      key: "sub",
      render: (v: number) => `#${v}`,
    },
    {
      title: "Estado",
      dataIndex: "status",
      key: "status",
      render: (v: string) => (
        <Tag color={alertStatusColor[v] ?? "default"}>
          {v === "new" ? "Nueva" : v === "acknowledged" ? "Atendiendo" : v}
        </Tag>
      ),
    },
    {
      title: "Cuando",
      dataIndex: "triggered_at",
      key: "when",
      render: (v: string) => new Date(v).toLocaleString("es-AR"),
    },
  ];

  const sessionColumns = [
    {
      title: "Suscripción",
      dataIndex: "subscription_id",
      key: "sub",
      render: (v: number) => `#${v}`,
    },
    {
      title: "Expira",
      dataIndex: "expires_at",
      key: "expires",
      render: (v: string) => {
        const d = new Date(v);
        const remaining = Math.round((d.getTime() - Date.now()) / 60000);
        return remaining > 0 ? `${remaining} min` : "Expirado";
      },
    },
  ];

  if (loadingSubs || loadingAlerts || loadingSessions) {
    return <Spin size="large" style={{ margin: 40 }} />;
  }

  return (
    <div style={{ padding: 24 }}>
      <Title level={3}>Panel de Seguridad</Title>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="Abonados activos"
              value={activeSubs.length}
              prefix={<ShieldOutlined />}
              valueStyle={{ color: "#52c41a" }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="Alertas abiertas"
              value={openAlerts.length}
              prefix={<AlertOutlined />}
              valueStyle={{ color: openAlerts.length > 0 ? "#ff4d4f" : "#52c41a" }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="Entradas activas"
              value={activeSessions.length}
              prefix={<ClockCircleOutlined />}
              valueStyle={{ color: activeSessions.length > 0 ? "#faad14" : "#52c41a" }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col xs={24} lg={14}>
          <Card
            title={
              <>
                <AlertOutlined /> Alertas recientes
                {openAlerts.length > 0 && (
                  <Badge count={openAlerts.length} style={{ marginLeft: 8 }} />
                )}
              </>
            }
          >
            <Table
              dataSource={alerts.slice(0, 10)}
              columns={alertColumns}
              rowKey="id"
              size="small"
              pagination={false}
              locale={{ emptyText: "Sin alertas" }}
            />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card
            title={
              <>
                <SafetyOutlined /> Entradas activas
              </>
            }
          >
            <Table
              dataSource={activeSessions}
              columns={sessionColumns}
              rowKey="id"
              size="small"
              pagination={false}
              locale={{ emptyText: "Sin entradas activas" }}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}

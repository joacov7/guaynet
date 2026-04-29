import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Alert,
  Card,
  Col,
  Row,
  Statistic,
  Table,
  Tag,
  Typography,
} from "antd";
import {
  TeamOutlined,
  PauseCircleOutlined,
  DollarOutlined,
  ApartmentOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { dashboardApi } from "@/services/api";

const { Title } = Typography;

function StatCard({
  title,
  value,
  icon,
  color,
  suffix,
}: {
  title: string;
  value: number | string;
  icon: React.ReactNode;
  color?: string;
  suffix?: string;
}) {
  return (
    <Card>
      <Statistic
        title={title}
        value={value}
        prefix={<span style={{ color: color ?? "#1677ff" }}>{icon}</span>}
        suffix={suffix}
        valueStyle={{ color: color }}
      />
    </Card>
  );
}

const statusTag: Record<string, React.ReactNode> = {
  online: <Tag color="green">Online</Tag>,
  offline: <Tag color="red">Offline</Tag>,
  unknown: <Tag color="default">Desconocido</Tag>,
};

export default function Dashboard() {
  const navigate = useNavigate();
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard"],
    queryFn: dashboardApi.stats,
    refetchInterval: 60_000,
  });

  if (error) return <Alert type="error" message="No se pudieron cargar las estadísticas" />;

  const formatARS = (v: number) =>
    new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS" }).format(v);

  return (
    <div>
      <Title level={4} style={{ marginTop: 0 }}>Dashboard</Title>

      <Row gutter={[16, 16]}>
        <Col xs={12} sm={6}>
          <StatCard title="Clientes activos" value={data?.active_clients ?? 0} icon={<TeamOutlined />} color="#52c41a" />
        </Col>
        <Col xs={12} sm={6}>
          <StatCard title="Suspendidos" value={data?.suspended_clients ?? 0} icon={<PauseCircleOutlined />} color="#faad14" />
        </Col>
        <Col xs={12} sm={6}>
          <StatCard title="Facturas vencidas" value={data?.invoices_overdue ?? 0} icon={<WarningOutlined />} color="#ff4d4f" />
        </Col>
        <Col xs={12} sm={6}>
          <StatCard
            title="Routers online"
            value={`${data?.routers_online ?? 0} / ${data?.total_routers ?? 0}`}
            icon={<ApartmentOutlined />}
            color={data && data.routers_offline > 0 ? "#ff4d4f" : "#52c41a"}
          />
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic
              title="Ingresos este mes"
              value={data?.revenue_this_month ?? 0}
              formatter={(v) => formatARS(Number(v))}
              prefix={<DollarOutlined style={{ color: "#1677ff" }} />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic
              title="Ingresos mes anterior"
              value={data?.revenue_last_month ?? 0}
              formatter={(v) => formatARS(Number(v))}
              prefix={<DollarOutlined style={{ color: "#8c8c8c" }} />}
              valueStyle={{ color: "#8c8c8c" }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <StatCard title="Facturas pendientes" value={data?.invoices_pending ?? 0} icon={<DollarOutlined />} color="#faad14" />
        </Col>
        <Col xs={12} sm={6}>
          <StatCard title="Total clientes" value={data?.total_clients ?? 0} icon={<TeamOutlined />} />
        </Col>
      </Row>

      <Card title="Estado de routers" style={{ marginTop: 16 }}>
        <Table
          loading={isLoading}
          dataSource={data?.router_statuses ?? []}
          rowKey="id"
          size="small"
          pagination={false}
          onRow={() => ({ onClick: () => navigate("/routers"), style: { cursor: "pointer" } })}
          columns={[
            { title: "Nombre", dataIndex: "name", key: "name" },
            { title: "Ubicación", dataIndex: "location", key: "location", render: (v) => v ?? "—" },
            { title: "Estado", dataIndex: "status", key: "status", render: (v) => statusTag[v] ?? <Tag>{v}</Tag> },
            { title: "Clientes", dataIndex: "client_count", key: "client_count", align: "right" },
          ]}
        />
      </Card>
    </div>
  );
}

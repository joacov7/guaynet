import { useQuery } from "@tanstack/react-query";
import { Badge, Card, Space, Table, Tag, Tabs, Typography } from "antd";
import { BellOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { alarmsApi } from "@/services/api";
import type { Alarm } from "@/types";

const { Title, Text } = Typography;

const TYPE_LABEL: Record<string, string> = {
  router_offline: "Router offline",
  cpu_high: "CPU alta",
  wan_down: "WAN caída",
  uplink_saturated: "Uplink saturado",
  ram_high: "RAM alta",
};
const TYPE_COLOR: Record<string, string> = {
  router_offline: "red",
  cpu_high: "orange",
  wan_down: "volcano",
  uplink_saturated: "purple",
  ram_high: "magenta",
};

function formatDetails(details?: Record<string, unknown>): string {
  if (!details) return "—";
  return Object.entries(details)
    .map(([k, v]) => `${k}: ${v}`)
    .join(" · ");
}

const columns = [
  {
    title: "Router",
    key: "router",
    render: (_: unknown, r: Alarm) => (
      <Space direction="vertical" size={0}>
        <Text strong>{r.router_name ?? `#${r.router_id}`}</Text>
        <Text type="secondary" style={{ fontSize: 12 }}>{r.router_host}</Text>
      </Space>
    ),
  },
  {
    title: "Tipo",
    dataIndex: "type",
    key: "type",
    render: (v: string) => (
      <Tag color={TYPE_COLOR[v] ?? "default"}>{TYPE_LABEL[v] ?? v}</Tag>
    ),
  },
  {
    title: "Estado",
    dataIndex: "status",
    key: "status",
    render: (v: string) => (
      <Tag color={v === "active" ? "red" : "green"}>
        {v === "active" ? "Activa" : "Resuelta"}
      </Tag>
    ),
  },
  {
    title: "Desde",
    dataIndex: "triggered_at",
    key: "triggered_at",
    render: (v: string) => dayjs(v).format("DD/MM/YYYY HH:mm"),
  },
  {
    title: "Resuelta",
    dataIndex: "resolved_at",
    key: "resolved_at",
    render: (v?: string) => v ? dayjs(v).format("DD/MM/YYYY HH:mm") : "—",
  },
  {
    title: "Detalles",
    dataIndex: "details",
    key: "details",
    render: (v?: Record<string, unknown>) => (
      <Text type="secondary" style={{ fontSize: 12 }}>{formatDetails(v)}</Text>
    ),
  },
];

export default function Alarms() {
  const { data: active = [], isLoading: loadingActive } = useQuery({
    queryKey: ["alarms-active"],
    queryFn: () => alarmsApi.list("active"),
    refetchInterval: 30_000,
  });

  const { data: all = [], isLoading: loadingAll } = useQuery({
    queryKey: ["alarms-all"],
    queryFn: () => alarmsApi.list(),
    refetchInterval: 60_000,
  });

  return (
    <div style={{ padding: 24 }}>
      <Space align="center" style={{ marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          <BellOutlined style={{ marginRight: 8 }} />
          Alarmas
        </Title>
        {active.length > 0 && (
          <Badge count={active.length} style={{ backgroundColor: "#ff4d4f" }} />
        )}
      </Space>

      <Tabs
        items={[
          {
            key: "active",
            label: (
              <span>
                Activas
                <Badge
                  count={active.length}
                  style={{ marginLeft: 6, backgroundColor: active.length > 0 ? "#ff4d4f" : "#8c8c8c" }}
                />
              </span>
            ),
            children: (
              <Table
                loading={loadingActive}
                dataSource={active}
                rowKey="id"
                columns={columns}
                size="small"
                pagination={{ pageSize: 50 }}
                locale={{ emptyText: "Sin alarmas activas ✅" }}
              />
            ),
          },
          {
            key: "history",
            label: "Historial",
            children: (
              <Table
                loading={loadingAll}
                dataSource={all}
                rowKey="id"
                columns={columns}
                size="small"
                pagination={{ pageSize: 50 }}
              />
            ),
          },
        ]}
      />
    </div>
  );
}

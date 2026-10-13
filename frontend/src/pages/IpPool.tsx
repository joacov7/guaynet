import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Badge,
  Button,
  Card,
  Col,
  Input,
  Row,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
} from "antd";
import { adminApi } from "@/services/api";
import type { IpPoolEntry } from "@/types";

const statusColor: Record<string, string> = {
  active: "green",
  suspended: "orange",
  cancelled: "default",
};

export default function IpPool() {
  const navigate = useNavigate();
  const [subnet, setSubnet] = useState("192.168.1.0/24");
  const [query, setQuery] = useState(subnet);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["ip-pool", query],
    queryFn: () => adminApi.ipPool(query),
    enabled: !!query,
  });

  const columns = [
    {
      title: "IP",
      dataIndex: "ip",
      width: 150,
      render: (ip: string, r: IpPoolEntry) => (
        <span style={{ fontFamily: "monospace" }}>{ip}</span>
      ),
    },
    {
      title: "Estado",
      dataIndex: "free",
      width: 110,
      render: (free: boolean) =>
        free ? <Badge status="success" text="Libre" /> : <Badge status="error" text="En uso" />,
      filters: [
        { text: "Libre", value: true },
        { text: "En uso", value: false },
      ],
      onFilter: (value: unknown, record: IpPoolEntry) => record.free === value,
    },
    {
      title: "Cliente",
      render: (_: unknown, r: IpPoolEntry) =>
        r.client_id ? (
          <Space>
            <span>#{r.client_id} — {r.client_name}</span>
            <Tag color={statusColor[r.status ?? ""] ?? "default"}>{r.status}</Tag>
          </Space>
        ) : "—",
    },
    {
      title: "",
      width: 120,
      render: (_: unknown, r: IpPoolEntry) =>
        r.free ? (
          <Button
            size="small"
            type="link"
            onClick={() => navigate("/clients/new", { state: { ip_address: r.ip } })}
          >
            Crear cliente
          </Button>
        ) : (
          <Button
            size="small"
            type="link"
            onClick={() => navigate(`/clients/${r.client_id}`)}
          >
            Ver cliente
          </Button>
        ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Typography.Title level={3} style={{ marginBottom: 16 }}>
        Pool de IPs
      </Typography.Title>

      <Card style={{ marginBottom: 16 }}>
        <Row gutter={16} align="middle">
          <Col flex="280px">
            <Input
              value={subnet}
              onChange={(e) => setSubnet(e.target.value)}
              placeholder="192.168.1.0/24"
              onPressEnter={() => setQuery(subnet)}
              addonBefore="Subnet"
            />
          </Col>
          <Col>
            <Button type="primary" onClick={() => setQuery(subnet)} loading={isLoading}>
              Consultar
            </Button>
          </Col>
        </Row>
      </Card>

      {data && (
        <>
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={6}>
              <Card>
                <Statistic title="Total IPs" value={data.total_hosts} />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic title="En uso" value={data.used} valueStyle={{ color: "#cf1322" }} />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic title="Libres" value={data.free} valueStyle={{ color: "#3f8600" }} />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="Ocupación"
                  value={Math.round((data.used / data.total_hosts) * 100)}
                  suffix="%"
                />
              </Card>
            </Col>
          </Row>

          <Table
            rowKey="ip"
            size="small"
            dataSource={data.ips}
            columns={columns}
            pagination={{ pageSize: 50 }}
            rowClassName={(r) => (r.free ? "" : "ant-table-row-used")}
          />
        </>
      )}
    </div>
  );
}

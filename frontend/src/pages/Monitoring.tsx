import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Badge,
  Button,
  Empty,
  Progress,
  Select,
  Space,
  Table,
  Tag,
  Tabs,
  Tooltip,
  Typography,
} from "antd";
import { ReloadOutlined, WifiOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { routersApi } from "@/services/api";
import type { BandwidthEntry, OnlineClient } from "@/types";

const { Title, Text } = Typography;

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

function maxLimitMbps(limit: string): number {
  const parts = limit.split("/");
  const dl = parseFloat(parts[1] ?? parts[0]);
  return isNaN(dl) ? 0 : dl;
}

export default function Monitoring() {
  const navigate = useNavigate();
  const [routerId, setRouterId] = useState<number | undefined>();

  const { data: routers = [] } = useQuery({ queryKey: ["routers"], queryFn: routersApi.list });

  const {
    data: bandwidth = [],
    isLoading: bwLoading,
    refetch: refetchBw,
  } = useQuery({
    queryKey: ["bandwidth", routerId],
    queryFn: () => routersApi.bandwidth(routerId!),
    enabled: routerId != null,
    refetchInterval: 30_000,
  });

  const {
    data: online = [],
    isLoading: onlineLoading,
    refetch: refetchOnline,
  } = useQuery({
    queryKey: ["online-clients", routerId],
    queryFn: () => routersApi.onlineClients(routerId!),
    enabled: routerId != null,
    refetchInterval: 30_000,
  });

  const onlineCount = online.filter((c) => c.online).length;
  const unregisteredCount = online.filter((c) => c.online && !c.client_id).length;

  const bwColumns = [
    {
      title: "Cliente",
      key: "client",
      render: (_: unknown, r: BandwidthEntry) =>
        r.client_id ? (
          <a onClick={() => navigate(`/clients/${r.client_id}`)}>{r.client_name}</a>
        ) : (
          <Text type="secondary">{r.queue_name}</Text>
        ),
    },
    { title: "IP", dataIndex: "ip_address", key: "ip" },
    { title: "Límite", dataIndex: "max_limit", key: "limit" },
    {
      title: "Estado",
      dataIndex: "disabled",
      key: "disabled",
      render: (v: boolean) => (
        <Tag color={v ? "orange" : "green"}>{v ? "Suspendido" : "Activo"}</Tag>
      ),
    },
    {
      title: "Descarga total",
      dataIndex: "download_bytes",
      key: "dl",
      render: (v: number, r: BandwidthEntry) => {
        const maxMb = maxLimitMbps(r.max_limit);
        const pct = maxMb > 0 ? Math.min((v / (maxMb * 1024 * 1024)) * 100, 100) : 0;
        return (
          <Tooltip title={formatBytes(v)}>
            <Progress
              percent={Math.round(pct)}
              size="small"
              format={() => formatBytes(v)}
              strokeColor={pct > 80 ? "#f5222d" : pct > 50 ? "#faad14" : "#52c41a"}
            />
          </Tooltip>
        );
      },
    },
    {
      title: "Subida total",
      dataIndex: "upload_bytes",
      key: "ul",
      render: (v: number) => formatBytes(v),
    },
  ];

  const onlineColumns = [
    {
      title: "IP",
      dataIndex: "ip_address",
      key: "ip",
      render: (v: string, r: OnlineClient) => (
        <Space>
          <Badge status={r.online ? "success" : "default"} />
          <span>{v}</span>
        </Space>
      ),
    },
    { title: "MAC", dataIndex: "mac_address", key: "mac", render: (v: string) => v || "—" },
    {
      title: "Cliente",
      key: "client",
      render: (_: unknown, r: OnlineClient) =>
        r.client_id ? (
          <a onClick={() => navigate(`/clients/${r.client_id}`)}>{r.client_name}</a>
        ) : (
          <Tag color="orange">Sin registrar</Tag>
        ),
    },
    {
      title: "Estado",
      dataIndex: "status",
      key: "status",
      render: (v: string) =>
        v ? (
          <Tag color={v === "active" ? "green" : v === "suspended" ? "orange" : "default"}>
            {v === "active" ? "Activo" : v === "suspended" ? "Suspendido" : v}
          </Tag>
        ) : (
          "—"
        ),
    },
    {
      title: "Online",
      dataIndex: "online",
      key: "online",
      render: (v: boolean) => (
        <Tag color={v ? "green" : "default"}>{v ? "Conectado" : "Desconectado"}</Tag>
      ),
    },
  ];

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 16,
        }}
      >
        <Title level={4} style={{ margin: 0 }}>
          Monitoreo
        </Title>
        <Select
          placeholder="Seleccionar router"
          style={{ width: 240 }}
          value={routerId}
          onChange={setRouterId}
          options={routers.map((r) => ({
            value: r.id,
            label: r.location ? `${r.name} (${r.location})` : r.name,
          }))}
        />
      </div>

      {!routerId ? (
        <Empty description="Seleccioná un router para comenzar" />
      ) : (
        <Tabs
          items={[
            {
              key: "online",
              label: (
                <span>
                  <WifiOutlined /> Clientes online
                  <Badge
                    count={onlineCount}
                    style={{ marginLeft: 6, backgroundColor: "#52c41a" }}
                  />
                  {unregisteredCount > 0 && (
                    <Badge
                      count={unregisteredCount}
                      style={{ marginLeft: 4, backgroundColor: "#faad14" }}
                    />
                  )}
                </span>
              ),
              children: (
                <div>
                  <Space style={{ marginBottom: 12 }}>
                    <Tag color="green">Online: {onlineCount}</Tag>
                    {unregisteredCount > 0 && (
                      <Tag color="orange">Sin registrar: {unregisteredCount}</Tag>
                    )}
                    <Tag>Total: {online.length}</Tag>
                    <Button
                      size="small"
                      icon={<ReloadOutlined />}
                      onClick={() => refetchOnline()}
                      loading={onlineLoading}
                    >
                      Actualizar
                    </Button>
                  </Space>
                  <Table
                    loading={onlineLoading}
                    dataSource={online}
                    rowKey="ip_address"
                    columns={onlineColumns}
                    size="small"
                    pagination={{ pageSize: 50 }}
                    rowClassName={(r: OnlineClient) => (!r.online ? "ant-table-row-secondary" : "")}
                  />
                </div>
              ),
            },
            {
              key: "bandwidth",
              label: (
                <span>
                  <ThunderboltOutlined /> Uso de ancho de banda
                  <Badge
                    count={bandwidth.length}
                    style={{ marginLeft: 6, backgroundColor: "#1677ff" }}
                  />
                </span>
              ),
              children: (
                <div>
                  <Space style={{ marginBottom: 12 }}>
                    <Text type="secondary">
                      Estadísticas acumuladas desde el último reset del router. Se actualiza cada 30s.
                    </Text>
                    <Button
                      size="small"
                      icon={<ReloadOutlined />}
                      onClick={() => refetchBw()}
                      loading={bwLoading}
                    >
                      Actualizar
                    </Button>
                  </Space>
                  <Table
                    loading={bwLoading}
                    dataSource={bandwidth}
                    rowKey="queue_name"
                    columns={bwColumns}
                    size="small"
                    pagination={{ pageSize: 50 }}
                  />
                </div>
              ),
            },
          ]}
        />
      )}
    </div>
  );
}

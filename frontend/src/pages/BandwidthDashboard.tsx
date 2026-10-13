import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Card, Col, Row, Select, Segmented, Spin, Table, Tag, Typography, Empty, Statistic,
} from "antd";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import dayjs from "dayjs";
import { routersApi, adminApi } from "../services/api";
import type { BandwidthHistoryEntry, BandwidthEntry } from "../types";

const { Text } = Typography;

const RANGES: { label: string; hours: number }[] = [
  { label: "1h", hours: 1 },
  { label: "6h", hours: 6 },
  { label: "24h", hours: 24 },
  { label: "7d", hours: 168 },
];

function toMbps(bytes: number, dtSeconds: number) {
  if (dtSeconds <= 0) return 0;
  return (bytes * 8) / dtSeconds / 1_000_000;
}

function buildChartData(samples: BandwidthHistoryEntry[]) {
  // Group by queue_name
  const byQueue = new Map<string, BandwidthHistoryEntry[]>();
  for (const s of samples) {
    const arr = byQueue.get(s.queue_name) ?? [];
    arr.push(s);
    byQueue.set(s.queue_name, arr);
  }

  // Calculate per-queue deltas and group by timestamp
  const byTime = new Map<string, { upload: number; download: number }>();

  for (const queueSamples of byQueue.values()) {
    const sorted = [...queueSamples].sort(
      (a, b) => new Date(a.sampled_at).getTime() - new Date(b.sampled_at).getTime()
    );
    for (let i = 1; i < sorted.length; i++) {
      const prev = sorted[i - 1];
      const curr = sorted[i];
      const dtSeconds =
        (new Date(curr.sampled_at).getTime() - new Date(prev.sampled_at).getTime()) / 1000;
      const uploadMbps = toMbps(
        Math.max(0, curr.upload_bytes - prev.upload_bytes),
        dtSeconds
      );
      const downloadMbps = toMbps(
        Math.max(0, curr.download_bytes - prev.download_bytes),
        dtSeconds
      );
      const existing = byTime.get(curr.sampled_at) ?? { upload: 0, download: 0 };
      byTime.set(curr.sampled_at, {
        upload: existing.upload + uploadMbps,
        download: existing.download + downloadMbps,
      });
    }
  }

  return Array.from(byTime.entries())
    .sort(([a], [b]) => new Date(a).getTime() - new Date(b).getTime())
    .map(([time, { upload, download }]) => ({
      time,
      label: dayjs(time).format("HH:mm"),
      upload: +upload.toFixed(2),
      download: +download.toFixed(2),
    }));
}

function StatCards({ data }: { data: ReturnType<typeof buildChartData> }) {
  const uploads = data.map((d) => d.upload);
  const downloads = data.map((d) => d.download);
  const avg = (arr: number[]) =>
    arr.length ? +(arr.reduce((a, b) => a + b, 0) / arr.length).toFixed(2) : 0;
  const max = (arr: number[]) => (arr.length ? +Math.max(...arr).toFixed(2) : 0);

  return (
    <Row gutter={12} style={{ marginBottom: 16 }}>
      <Col xs={12} sm={6}>
        <Card size="small">
          <Statistic title="Pico subida" value={max(uploads)} suffix="Mbps" precision={2} valueStyle={{ color: "#1677ff" }} />
        </Card>
      </Col>
      <Col xs={12} sm={6}>
        <Card size="small">
          <Statistic title="Pico bajada" value={max(downloads)} suffix="Mbps" precision={2} valueStyle={{ color: "#52c41a" }} />
        </Card>
      </Col>
      <Col xs={12} sm={6}>
        <Card size="small">
          <Statistic title="Promedio subida" value={avg(uploads)} suffix="Mbps" precision={2} />
        </Card>
      </Col>
      <Col xs={12} sm={6}>
        <Card size="small">
          <Statistic title="Promedio bajada" value={avg(downloads)} suffix="Mbps" precision={2} />
        </Card>
      </Col>
    </Row>
  );
}

function TopConsumers({ routerId }: { routerId: number }) {
  const { data = [], isLoading } = useQuery({
    queryKey: ["bw-live", routerId],
    queryFn: () => routersApi.bandwidth(routerId),
    refetchInterval: 30_000,
  });

  const sorted = [...data].sort(
    (a, b) => b.download_bytes + b.upload_bytes - (a.download_bytes + a.upload_bytes)
  );

  function fmtBytes(n: number) {
    if (n >= 1e9) return `${(n / 1e9).toFixed(1)} GB`;
    if (n >= 1e6) return `${(n / 1e6).toFixed(1)} MB`;
    return `${(n / 1e3).toFixed(0)} KB`;
  }

  return (
    <Card title="Top consumidores (actual)" size="small" style={{ marginTop: 16 }}>
      <Table
        dataSource={sorted.slice(0, 10)}
        rowKey="queue_name"
        loading={isLoading}
        size="small"
        pagination={false}
      >
        <Table.Column title="Cliente" dataIndex="client_name"
          render={(v: string, row: BandwidthEntry) => v ?? row.ip_address} />
        <Table.Column title="IP" dataIndex="ip_address" width={140} />
        <Table.Column title="Plan" dataIndex="max_limit" width={120} />
        <Table.Column title="Estado" dataIndex="disabled" width={90}
          render={(v: boolean) => <Tag color={v ? "red" : "green"}>{v ? "Bloqueado" : "Activo"}</Tag>} />
        <Table.Column title="Descarga" dataIndex="download_bytes" width={110}
          render={(v: number) => <Text style={{ color: "#52c41a" }}>{fmtBytes(v)}</Text>} />
        <Table.Column title="Subida" dataIndex="upload_bytes" width={110}
          render={(v: number) => <Text style={{ color: "#1677ff" }}>{fmtBytes(v)}</Text>} />
      </Table>
    </Card>
  );
}

export default function BandwidthDashboard() {
  const [routerId, setRouterId] = useState<number | undefined>();
  const [hours, setHours] = useState(24);

  const { data: routers = [] } = useQuery({
    queryKey: ["routers"],
    queryFn: () => routersApi.list(),
  });

  const { data: history = [], isLoading } = useQuery({
    queryKey: ["bw-history", routerId, hours],
    queryFn: () => adminApi.bandwidthHistory(routerId!, hours),
    enabled: routerId !== undefined,
    refetchInterval: 60_000,
  });

  const chartData = useMemo(() => buildChartData(history), [history]);

  const routerOptions = routers.map((r) => ({ value: r.id, label: r.name }));

  return (
    <div style={{ padding: 24 }}>
      <Row gutter={12} align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Select
            style={{ width: 220 }}
            placeholder="Seleccionar router"
            options={routerOptions}
            value={routerId}
            onChange={setRouterId}
          />
        </Col>
        <Col>
          <Segmented
            options={RANGES.map((r) => ({ label: r.label, value: r.hours }))}
            value={hours}
            onChange={(v) => setHours(v as number)}
          />
        </Col>
      </Row>

      {!routerId ? (
        <Empty description="Seleccioná un router para ver el historial" />
      ) : isLoading ? (
        <div style={{ textAlign: "center", padding: 80 }}>
          <Spin size="large" />
        </div>
      ) : chartData.length === 0 ? (
        <Empty description="Sin datos históricos. Las muestras se recopilan cada 5 minutos con Celery." />
      ) : (
        <>
          <StatCards data={chartData} />
          <Card title="Ancho de banda (Mbps)" size="small">
            <ResponsiveContainer width="100%" height={340}>
              <AreaChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorUpload" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#1677ff" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#1677ff" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="colorDownload" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#52c41a" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#52c41a" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#303030" />
                <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                <YAxis unit=" Mbps" tick={{ fontSize: 11 }} width={70} />
                <Tooltip
                  formatter={(value: number, name: string) => [
                    `${value.toFixed(2)} Mbps`,
                    name === "upload" ? "Subida" : "Bajada",
                  ]}
                  labelFormatter={(label) => `Hora: ${label}`}
                  contentStyle={{ background: "#141414", border: "1px solid #303030" }}
                />
                <Legend formatter={(v) => (v === "upload" ? "Subida" : "Bajada")} />
                <Area
                  type="monotone" dataKey="upload" stroke="#1677ff"
                  fill="url(#colorUpload)" strokeWidth={2}
                />
                <Area
                  type="monotone" dataKey="download" stroke="#52c41a"
                  fill="url(#colorDownload)" strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </Card>
          <TopConsumers routerId={routerId} />
        </>
      )}
    </div>
  );
}

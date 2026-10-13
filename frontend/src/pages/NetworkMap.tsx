import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { useEffect, useRef, useState } from "react";
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";
import { useQuery } from "@tanstack/react-query";
import {
  Badge,
  Card,
  Checkbox,
  Col,
  Row,
  Select,
  Spin,
  Statistic,
  Tag,
  Typography,
} from "antd";
import { adminApi } from "@/services/api";

// Fix default marker icons broken by webpack/vite
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

const routerIcon = new L.Icon({
  iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34],
});

const apIcon = new L.Icon({
  iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-violet.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34],
});

const clientActiveIcon = new L.Icon({
  iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [20, 33], iconAnchor: [10, 33], popupAnchor: [1, -28],
});

const clientSuspendedIcon = new L.Icon({
  iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-orange.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [20, 33], iconAnchor: [10, 33], popupAnchor: [1, -28],
});

const clientCancelledIcon = new L.Icon({
  iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [20, 33], iconAnchor: [10, 33], popupAnchor: [1, -28],
});

const clientDefaultIcon = new L.Icon({
  iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-grey.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [20, 33], iconAnchor: [10, 33], popupAnchor: [1, -28],
});

function getClientIcon(status: string) {
  switch (status) {
    case "active": return clientActiveIcon;
    case "suspended": return clientSuspendedIcon;
    case "cancelled": return clientCancelledIcon;
    default: return clientDefaultIcon;
  }
}

function AutoCenter({ points }: { points: [number, number][] }) {
  const map = useMap();
  useEffect(() => {
    if (points.length > 0) {
      map.fitBounds(points, { padding: [40, 40] });
    }
  }, [map, points]);
  return null;
}

const statusColor: Record<string, string> = {
  online: "green", offline: "red", active: "green", suspended: "orange", cancelled: "default",
};

function useSecondsSince(timestamp: number | null) {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    if (timestamp === null) return;
    const update = () => setSeconds(Math.floor((Date.now() - timestamp) / 1000));
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, [timestamp]);

  return seconds;
}

export default function NetworkMap() {
  const [showRouters, setShowRouters] = useState(true);
  const [showAPs, setShowAPs] = useState(true);
  const [showClients, setShowClients] = useState(true);
  const [clientStatusFilter, setClientStatusFilter] = useState<string>("all");

  const lastFetchedAt = useRef<number | null>(null);

  const { data, isLoading, dataUpdatedAt } = useQuery({
    queryKey: ["map-data"],
    queryFn: adminApi.mapData,
    refetchInterval: 60_000,
  });

  useEffect(() => {
    if (dataUpdatedAt) {
      lastFetchedAt.current = dataUpdatedAt;
    }
  }, [dataUpdatedAt]);

  const secondsSinceUpdate = useSecondsSince(dataUpdatedAt ?? null);

  if (isLoading) return <Spin size="large" style={{ display: "block", margin: "80px auto" }} />;

  const routers = data?.routers ?? [];
  const aps = data?.access_points ?? [];
  const clients = data?.clients ?? [];

  const filteredClients = clientStatusFilter === "all"
    ? clients
    : clients.filter((c: any) => c.status === clientStatusFilter);

  const activeCount = clients.filter((c: any) => c.status === "active").length;
  const suspendedCount = clients.filter((c: any) => c.status === "suspended").length;
  const cancelledCount = clients.filter((c: any) => c.status === "cancelled").length;

  const visiblePoints: [number, number][] = [
    ...(showRouters ? routers.map((r: any) => [r.latitude, r.longitude] as [number, number]) : []),
    ...(showAPs ? aps.map((a: any) => [a.latitude, a.longitude] as [number, number]) : []),
    ...(showClients ? filteredClients.map((c: any) => [c.latitude, c.longitude] as [number, number]) : []),
  ];

  const allPoints: [number, number][] = [
    ...routers.map((r: any) => [r.latitude, r.longitude] as [number, number]),
    ...aps.map((a: any) => [a.latitude, a.longitude] as [number, number]),
    ...clients.map((c: any) => [c.latitude, c.longitude] as [number, number]),
  ];

  const defaultCenter: [number, number] = allPoints.length > 0
    ? allPoints[0]
    : [-34.6037, -58.3816];

  const refreshLabel =
    dataUpdatedAt
      ? secondsSinceUpdate < 5
        ? "Actualizado ahora"
        : `Actualizado hace ${secondsSinceUpdate} seg`
      : "";

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 16, marginBottom: 16 }}>
        <Typography.Title level={3} style={{ marginBottom: 0 }}>Mapa de Red</Typography.Title>
        {refreshLabel && (
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {refreshLabel}
          </Typography.Text>
        )}
      </div>

      {/* Stats row */}
      <Row gutter={12} style={{ marginBottom: 16 }}>
        <Col>
          <Card size="small" style={{ minWidth: 120 }}>
            <Statistic
              title="Total clientes"
              value={clients.length}
              valueStyle={{ fontSize: 20 }}
            />
          </Card>
        </Col>
        <Col>
          <Card size="small" style={{ minWidth: 120 }}>
            <Statistic
              title="Activos"
              value={activeCount}
              valueStyle={{ fontSize: 20, color: "#52c41a" }}
            />
          </Card>
        </Col>
        <Col>
          <Card size="small" style={{ minWidth: 120 }}>
            <Statistic
              title="Suspendidos"
              value={suspendedCount}
              valueStyle={{ fontSize: 20, color: "#fa8c16" }}
            />
          </Card>
        </Col>
        <Col>
          <Card size="small" style={{ minWidth: 120 }}>
            <Statistic
              title="Cancelados"
              value={cancelledCount}
              valueStyle={{ fontSize: 20, color: "#ff4d4f" }}
            />
          </Card>
        </Col>
      </Row>

      {/* Filter bar */}
      <Card
        size="small"
        style={{ marginBottom: 12, borderRadius: 8 }}
        bodyStyle={{ padding: "10px 16px" }}
      >
        <Row align="middle" gutter={24} wrap={false}>
          <Col>
            <Typography.Text strong style={{ fontSize: 13, marginRight: 8 }}>
              Mostrar:
            </Typography.Text>
            <Checkbox
              checked={showRouters}
              onChange={(e) => setShowRouters(e.target.checked)}
              style={{ marginRight: 12 }}
            >
              <Badge color="blue" text={`Routers (${routers.length})`} />
            </Checkbox>
            <Checkbox
              checked={showAPs}
              onChange={(e) => setShowAPs(e.target.checked)}
              style={{ marginRight: 12 }}
            >
              <Badge color="purple" text={`APs Ubiquiti (${aps.length})`} />
            </Checkbox>
            <Checkbox
              checked={showClients}
              onChange={(e) => setShowClients(e.target.checked)}
            >
              <Badge color="default" text={`Clientes (${clients.length})`} />
            </Checkbox>
          </Col>
          {showClients && (
            <Col>
              <Typography.Text style={{ fontSize: 13, marginRight: 8 }}>Estado cliente:</Typography.Text>
              <Select
                size="small"
                value={clientStatusFilter}
                onChange={setClientStatusFilter}
                style={{ width: 150 }}
                options={[
                  { value: "all", label: "Todos" },
                  { value: "active", label: "Activo" },
                  { value: "suspended", label: "Suspendido" },
                  { value: "cancelled", label: "Cancelado" },
                ]}
              />
            </Col>
          )}
          <Col flex="auto" style={{ textAlign: "right" }}>
            <Typography.Text type="secondary" style={{ fontSize: 11 }}>
              Solo se muestran elementos con coordenadas cargadas.
            </Typography.Text>
          </Col>
        </Row>
      </Card>

      <Card bodyStyle={{ padding: 0 }} style={{ borderRadius: 8, overflow: "hidden" }}>
        <MapContainer center={defaultCenter} zoom={13} style={{ height: 600, width: "100%" }}>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {allPoints.length > 0 && <AutoCenter points={allPoints} />}

          {showRouters && routers.map((r: any) => (
            <Marker key={`router-${r.id}`} position={[r.latitude, r.longitude]} icon={routerIcon}>
              <Popup>
                <div style={{ minWidth: 160 }}>
                  <strong style={{ fontSize: 14 }}>{r.name}</strong>
                  <br />
                  <span style={{ color: "#666", fontSize: 12 }}>{r.host}</span>
                  <br />
                  <Tag color={statusColor[r.status] ?? "default"} style={{ marginTop: 4 }}>
                    {r.status}
                  </Tag>
                  {r.location && (
                    <div style={{ marginTop: 4, fontSize: 12 }}>{r.location}</div>
                  )}
                  {r.client_count !== undefined && (
                    <div style={{ marginTop: 4, fontSize: 12 }}>
                      <strong>{r.client_count}</strong> clientes conectados
                    </div>
                  )}
                </div>
              </Popup>
            </Marker>
          ))}

          {showAPs && aps.map((a: any) => (
            <Marker key={`ap-${a.id}`} position={[a.latitude, a.longitude]} icon={apIcon}>
              <Popup>
                <div style={{ minWidth: 160 }}>
                  <strong style={{ fontSize: 14 }}>{a.name}</strong>
                  <br />
                  <span style={{ color: "#666", fontSize: 12 }}>{a.device_type}</span>
                  <br />
                  <Tag color={statusColor[a.status] ?? "default"} style={{ marginTop: 4 }}>
                    {a.status}
                  </Tag>
                  {a.ssid && (
                    <div style={{ marginTop: 4, fontSize: 12 }}>
                      SSID: <strong>{a.ssid}</strong>
                    </div>
                  )}
                  {a.frequency_mhz && (
                    <div style={{ fontSize: 12 }}>{a.frequency_mhz} MHz</div>
                  )}
                </div>
              </Popup>
            </Marker>
          ))}

          {showClients && filteredClients.map((c: any) => (
            <Marker
              key={`client-${c.id}`}
              position={[c.latitude, c.longitude]}
              icon={getClientIcon(c.status)}
            >
              <Popup>
                <div style={{ minWidth: 170 }}>
                  <strong style={{ fontSize: 14 }}>{c.full_name}</strong>
                  <br />
                  <span style={{ color: "#666", fontSize: 12 }}>{c.ip_address}</span>
                  <br />
                  <Tag color={statusColor[c.status] ?? "default"} style={{ marginTop: 4 }}>
                    {c.status}
                  </Tag>
                  {c.plan_name && (
                    <div style={{ marginTop: 4, fontSize: 12 }}>
                      Plan: <strong>{c.plan_name}</strong>
                    </div>
                  )}
                  {c.address && (
                    <div style={{ fontSize: 12, color: "#555" }}>{c.address}</div>
                  )}
                  <div style={{ marginTop: 6 }}>
                    <a href={`/clients/${c.id}`} style={{ fontSize: 12 }}>
                      Ver cliente
                    </a>
                  </div>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </Card>
    </div>
  );
}

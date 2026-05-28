import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { useEffect } from "react";
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";
import { useQuery } from "@tanstack/react-query";
import { Badge, Card, Col, Row, Spin, Tag, Typography } from "antd";
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
  iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34],
});

const clientIcon = new L.Icon({
  iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-grey.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [20, 33], iconAnchor: [10, 33], popupAnchor: [1, -28],
});

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

export default function NetworkMap() {
  const { data, isLoading } = useQuery({
    queryKey: ["map-data"],
    queryFn: adminApi.mapData,
    refetchInterval: 60_000,
  });

  if (isLoading) return <Spin size="large" style={{ display: "block", margin: "80px auto" }} />;

  const routers = data?.routers ?? [];
  const aps = data?.access_points ?? [];
  const clients = data?.clients ?? [];

  const allPoints: [number, number][] = [
    ...routers.map((r: any) => [r.latitude, r.longitude] as [number, number]),
    ...aps.map((a: any) => [a.latitude, a.longitude] as [number, number]),
    ...clients.map((c: any) => [c.latitude, c.longitude] as [number, number]),
  ];

  const defaultCenter: [number, number] = allPoints.length > 0
    ? allPoints[0]
    : [-34.6037, -58.3816]; // Buenos Aires por defecto

  return (
    <div style={{ padding: 24 }}>
      <Typography.Title level={3} style={{ marginBottom: 16 }}>Mapa de Red</Typography.Title>

      <Row gutter={12} style={{ marginBottom: 16 }}>
        <Col>
          <Badge color="blue" text={`Routers (${routers.length})`} />
        </Col>
        <Col>
          <Badge color="green" text={`APs Ubiquiti (${aps.length})`} />
        </Col>
        <Col>
          <Badge color="default" text={`Clientes (${clients.length})`} />
        </Col>
        <Col>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            Solo se muestran elementos con coordenadas cargadas. Editá el router/AP/cliente para agregar lat/lon.
          </Typography.Text>
        </Col>
      </Row>

      <Card bodyStyle={{ padding: 0 }} style={{ borderRadius: 8, overflow: "hidden" }}>
        <MapContainer
          center={defaultCenter}
          zoom={13}
          style={{ height: 600, width: "100%" }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {allPoints.length > 0 && <AutoCenter points={allPoints} />}

          {routers.map((r: any) => (
            <Marker key={`router-${r.id}`} position={[r.latitude, r.longitude]} icon={routerIcon}>
              <Popup>
                <strong>{r.name}</strong><br />
                {r.host}<br />
                <Tag color={statusColor[r.status] ?? "default"}>{r.status}</Tag>
                {r.location && <><br />{r.location}</>}
                {r.client_count !== undefined && <><br />{r.client_count} clientes</>}
              </Popup>
            </Marker>
          ))}

          {aps.map((a: any) => (
            <Marker key={`ap-${a.id}`} position={[a.latitude, a.longitude]} icon={apIcon}>
              <Popup>
                <strong>{a.name}</strong><br />
                {a.device_type}<br />
                <Tag color={statusColor[a.status] ?? "default"}>{a.status}</Tag>
                {a.ssid && <><br />SSID: {a.ssid}</>}
                {a.frequency_mhz && <><br />{a.frequency_mhz} MHz</>}
              </Popup>
            </Marker>
          ))}

          {clients.map((c: any) => (
            <Marker key={`client-${c.id}`} position={[c.latitude, c.longitude]} icon={clientIcon}>
              <Popup>
                <strong>{c.full_name}</strong><br />
                {c.ip_address}<br />
                <Tag color={statusColor[c.status] ?? "default"}>{c.status}</Tag>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </Card>
    </div>
  );
}

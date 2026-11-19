import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Col,
  DatePicker,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import { eventsApi, subscriptionsApi } from "@/services/security/api";
import type { SecurityEvent, SecuritySubscription } from "@/types/security";

const { Title } = Typography;
const { RangePicker } = DatePicker;

// ── Display helpers ─────────────────────────────────────────────────────────

const eventTypeColor: Record<string, string> = {
  armed:              "green",
  disarmed:           "cyan",
  intrusion:          "red",
  battery_low:        "orange",
  power_failure:      "volcano",
  power_restored:     "lime",
  communication_lost: "magenta",
  tamper:             "red",
  zone_open:          "gold",
  test:               "blue",
  panic:              "red",
  duress:             "red",
  other:              "default",
};

const eventTypeLabel: Record<string, string> = {
  armed:              "Armado",
  disarmed:           "Desarmado",
  intrusion:          "Intrusión",
  battery_low:        "Batería baja",
  power_failure:      "Corte de luz",
  power_restored:     "Energía restaurada",
  communication_lost: "Pérdida de señal",
  tamper:             "Manipulación",
  zone_open:          "Zona abierta",
  test:               "Prueba",
  panic:              "Pánico",
  duress:             "Coacción",
  other:              "Otro",
};

const sourceLabel: Record<string, string> = {
  beat:   "BEAT",
  mock:   "Simulado",
  manual: "Manual",
};

const EVENT_TYPE_OPTIONS = Object.entries(eventTypeLabel).map(([value, label]) => ({
  value,
  label,
}));

// ── Columns ─────────────────────────────────────────────────────────────────

const columns: ColumnsType<SecurityEvent> = [
  {
    title: "Fecha / Hora",
    dataIndex: "occurred_at",
    key: "occurred_at",
    width: 160,
    render: (v: string) => dayjs(v).format("DD/MM/YY HH:mm:ss"),
    sorter: (a, b) => dayjs(a.occurred_at).unix() - dayjs(b.occurred_at).unix(),
    defaultSortOrder: "descend",
  },
  {
    title: "Tipo",
    dataIndex: "event_type",
    key: "event_type",
    width: 160,
    render: (v: string) => (
      <Tag color={eventTypeColor[v] ?? "default"}>
        {eventTypeLabel[v] ?? v}
      </Tag>
    ),
  },
  {
    title: "Zona",
    dataIndex: "zone_number",
    key: "zone_number",
    width: 70,
    render: (v: number | null) => v != null ? `Z${v}` : "—",
  },
  {
    title: "Partición",
    dataIndex: "partition",
    key: "partition",
    width: 80,
    render: (v: number | null) => v != null ? v : "—",
  },
  {
    title: "Descripción",
    dataIndex: "description",
    key: "description",
    render: (v: string | null) => v ?? <span style={{ color: "#aaa" }}>—</span>,
  },
  {
    title: "Usuario",
    dataIndex: "user_code",
    key: "user_code",
    width: 90,
    render: (v: string | null) => v ?? "—",
  },
  {
    title: "Origen",
    dataIndex: "source",
    key: "source",
    width: 90,
    render: (v: string) => (
      <Tag color={v === "beat" ? "geekblue" : v === "mock" ? "purple" : "default"}>
        {sourceLabel[v] ?? v}
      </Tag>
    ),
  },
];

// ── Page ────────────────────────────────────────────────────────────────────

export default function SecurityEvents() {
  const [subscriptionId, setSubscriptionId] = useState<number | null>(null);
  const [eventType, setEventType] = useState<string | undefined>(undefined);
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null);

  const { data: subscriptions = [], isLoading: subsLoading } = useQuery<SecuritySubscription[]>({
    queryKey: ["security-subscriptions"],
    queryFn: () => subscriptionsApi.list(),
  });

  const { data: events = [], isLoading: eventsLoading } = useQuery<SecurityEvent[]>({
    queryKey: ["security-events", subscriptionId, eventType, dateRange],
    queryFn: () =>
      eventsApi.list({
        subscription_id: subscriptionId!,
        event_type: eventType,
        from_date: dateRange?.[0]?.toISOString(),
        to_date: dateRange?.[1]?.endOf("day").toISOString(),
        limit: 500,
      }),
    enabled: !!subscriptionId,
  });

  return (
    <div style={{ padding: 24 }}>
      <Title level={3} style={{ margin: 0, marginBottom: 16 }}>
        Historial de Eventos
      </Title>

      <Row gutter={12} style={{ marginBottom: 16 }} align="middle">
        <Col>
          <Select
            style={{ width: 220 }}
            placeholder="Seleccionar suscripción"
            loading={subsLoading}
            value={subscriptionId ?? undefined}
            onChange={(v) => setSubscriptionId(v)}
            options={subscriptions.map((s) => ({
              value: s.id,
              label: `#${s.id} — Prop. ${s.property_id}`,
            }))}
          />
        </Col>
        <Col>
          <Select
            style={{ width: 180 }}
            placeholder="Tipo de evento"
            allowClear
            value={eventType}
            onChange={(v) => setEventType(v)}
            options={EVENT_TYPE_OPTIONS}
          />
        </Col>
        <Col>
          <RangePicker
            format="DD/MM/YYYY"
            value={dateRange as any}
            onChange={(v) => setDateRange(v as any)}
            allowClear
          />
        </Col>
        <Col>
          <Space style={{ color: "#888", fontSize: 12 }}>
            {subscriptionId
              ? `${events.length} evento${events.length !== 1 ? "s" : ""}`
              : "Seleccioná una suscripción"}
          </Space>
        </Col>
      </Row>

      <Table<SecurityEvent>
        dataSource={events}
        columns={columns}
        rowKey="id"
        loading={eventsLoading}
        size="small"
        pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: ["25", "50", "100"] }}
        rowClassName={(r) =>
          ["intrusion", "panic", "duress", "tamper"].includes(r.event_type)
            ? "security-event-row-alert"
            : ""
        }
        locale={{ emptyText: subscriptionId ? "Sin eventos para los filtros seleccionados" : "Seleccioná una suscripción para ver eventos" }}
      />

      <style>{`
        .security-event-row-alert td {
          background: #fff1f0 !important;
        }
      `}</style>
    </div>
  );
}

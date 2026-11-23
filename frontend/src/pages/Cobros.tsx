import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Button, Card, Col, DatePicker, Empty, Row, Select, Space, Statistic, Table, Tag, Typography } from "antd";
import { DollarOutlined, ReloadOutlined } from "@ant-design/icons";
import dayjs, { type Dayjs } from "dayjs";
import { accountApi, type Cobro } from "@/services/api";
import { usePermissions } from "@/contexts/PermissionsContext";
import CollectModal, { METHODS, VoidCobroModal, money } from "@/components/billing/CollectModal";

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

/** Cobros (caja): what came in, by day, by method and by who collected it. */
export default function Cobros() {
  const { canEdit, canView } = usePermissions();
  const canCollect = canEdit("billing") && canView("act_payments");
  const canVoid = canEdit("billing") && canView("act_payment_void");
  const [range, setRange] = useState<[Dayjs, Dayjs]>([dayjs(), dayjs()]);
  const [method, setMethod] = useState<string | undefined>();
  const [collector, setCollector] = useState<string | undefined>();
  const [collecting, setCollecting] = useState(false);
  const [voiding, setVoiding] = useState<{ id: number; total: number } | null>(null);

  const { data, isFetching, refetch } = useQuery({
    queryKey: ["cobros", range[0].format("YYYY-MM-DD"), range[1].format("YYYY-MM-DD"), method, collector],
    queryFn: () =>
      accountApi.cobros({
        date_from: range[0].format("YYYY-MM-DD"),
        date_to: range[1].format("YYYY-MM-DD"),
        method,
        received_by: collector,
      }),
    placeholderData: (prev) => prev,
  });
  const single = range[0].isSame(range[1], "day");
  const title = single
    ? range[0].isSame(dayjs(), "day") ? "Cobros de hoy" : `Cobros del ${range[0].format("DD/MM/YYYY")}`
    : `Cobros del ${range[0].format("DD/MM")} al ${range[1].format("DD/MM/YYYY")}`;

  return (
    <div>
      <Space style={{ justifyContent: "space-between", width: "100%", marginBottom: 16 }} wrap>
        <Title level={3} style={{ margin: 0 }}>{title}</Title>
        {canCollect && (
          <Button type="primary" icon={<DollarOutlined />} onClick={() => setCollecting(true)}>Registrar cobro</Button>
        )}
      </Space>

      <Card style={{ marginBottom: 16 }}>
        <Space wrap>
          <RangePicker
            value={range}
            format="DD/MM/YYYY"
            allowClear={false}
            onChange={(v) => v && v[0] && v[1] && setRange([v[0], v[1]])}
            presets={[
              { label: "Hoy", value: [dayjs(), dayjs()] },
              { label: "Ayer", value: [dayjs().subtract(1, "day"), dayjs().subtract(1, "day")] },
              { label: "Esta semana", value: [dayjs().startOf("week"), dayjs()] },
              { label: "Este mes", value: [dayjs().startOf("month"), dayjs()] },
              { label: "Mes pasado", value: [dayjs().subtract(1, "month").startOf("month"), dayjs().subtract(1, "month").endOf("month")] },
            ]}
          />
          <Select
            allowClear
            placeholder="Medio de pago"
            style={{ width: 170 }}
            value={method}
            onChange={setMethod}
            options={Object.entries(METHODS).map(([value, label]) => ({ value, label }))}
          />
          <Select
            allowClear
            placeholder="Quién cobró"
            style={{ width: 200 }}
            value={collector}
            onChange={setCollector}
            options={(data?.collectors ?? []).map((c) => ({ value: c, label: c }))}
          />
          <Button icon={<ReloadOutlined />} onClick={() => refetch()} loading={isFetching}>Actualizar</Button>
        </Space>
      </Card>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} md={8}>
          <Card>
            <Statistic title="Total cobrado" value={money(data?.total ?? 0)} />
            <Text type="secondary">
              {data?.count ?? 0} cobro{data?.count === 1 ? "" : "s"}
              {data?.voided_count ? ` · ${data.voided_count} anulado${data.voided_count === 1 ? "" : "s"} (no suman)` : ""}
            </Text>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card title="Por medio de pago" size="small">
            {Object.keys(data?.by_method ?? {}).length === 0 && <Text type="secondary">—</Text>}
            {Object.entries(data?.by_method ?? {}).map(([m, v]) => (
              <div key={m} style={{ display: "flex", justifyContent: "space-between" }}>
                <span>{METHODS[m] ?? m}</span><Text strong>{money(v)}</Text>
              </div>
            ))}
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card title="Por quién cobró" size="small">
            {Object.keys(data?.by_collector ?? {}).length === 0 && <Text type="secondary">—</Text>}
            {Object.entries(data?.by_collector ?? {}).map(([who, v]) => (
              <div key={who} style={{ display: "flex", justifyContent: "space-between" }}>
                <span>{who}</span><Text strong>{money(v)}</Text>
              </div>
            ))}
          </Card>
        </Col>
      </Row>

      <Card>
        <Table<Cobro>
          dataSource={data?.items ?? []}
          loading={isFetching && !data}
          rowKey="group_id"
          size="small"
          scroll={{ x: 900 }}
          pagination={{ pageSize: 25, showSizeChanger: false }}
          rowClassName={(r) => (r.voided ? "row-voided" : "")}
          locale={{ emptyText: <Empty description="No hay cobros en estas fechas" /> }}
          columns={[
            { title: "Fecha", dataIndex: "date", width: 100, render: (d: string) => dayjs(d).format("DD/MM/YYYY") },
            {
              title: "Cliente", dataIndex: "client_name",
              render: (n: string, r) => <Link to={`/clients/${r.client_id}`}>{n || `#${r.client_id}`}</Link>,
            },
            {
              title: "Monto", dataIndex: "total", align: "right", width: 130,
              render: (v: number, r) => <Text strong delete={r.voided}>{money(v)}</Text>,
            },
            { title: "Medio", dataIndex: "method", width: 120, render: (m: string) => METHODS[m] ?? m },
            {
              title: "Aplicado a", key: "applied",
              render: (_: unknown, r) => (
                <>
                  {[...new Set(r.invoices)].map((p) => <Tag key={p}>{p}</Tag>)}
                  {r.to_credit > 0 && <Tag color="green">A favor {money(r.to_credit)}</Tag>}
                </>
              ),
            },
            { title: "Cobró", dataIndex: "received_by", width: 150, render: (v?: string | null) => v ?? "—" },
            { title: "Referencia", dataIndex: "reference", render: (v?: string | null) => v ?? "" },
            {
              title: "", key: "act", width: 170, align: "right",
              render: (_: unknown, r) =>
                r.voided ? (
                  <Text type="secondary" style={{ fontSize: 12 }}>Anulado por {r.voided_by}: {r.void_reason}</Text>
                ) : canVoid ? (
                  <Button size="small" danger onClick={() => setVoiding({ id: r.payment_id, total: r.total })}>Anular</Button>
                ) : null,
            },
          ]}
        />
      </Card>

      <CollectModal open={collecting} onClose={() => setCollecting(false)} />
      <VoidCobroModal paymentId={voiding?.id ?? null} total={voiding?.total} onClose={() => setVoiding(null)} />
    </div>
  );
}

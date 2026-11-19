import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Card,
  Col,
  Input,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import dayjs from "dayjs";
import { adminApi } from "@/services/api";
import type { AuditLogEntry } from "@/types";

const actionColor: Record<string, string> = {
  suspend_client: "red",
  activate_client: "green",
  change_plan: "blue",
  create_client: "cyan",
  delete_client: "volcano",
  test_router: "geekblue",
  set_wireless: "purple",
};

const entityLabels: Record<string, string> = {
  client: "Cliente",
  router: "Router",
  ubiquiti: "Ubiquiti",
  plan: "Plan",
  invoice: "Factura",
};

export default function AuditLog() {
  const [entityType, setEntityType] = useState<string | undefined>();
  const [search, setSearch] = useState("");

  const { data = [], isLoading } = useQuery({
    queryKey: ["audit-logs", entityType],
    queryFn: () => adminApi.auditLogs({ entity_type: entityType, limit: 200 }),
    refetchInterval: 30_000,
  });

  const filtered = data.filter((row) => {
    if (!search) return true;
    const s = search.toLowerCase();
    return (
      row.username.toLowerCase().includes(s) ||
      row.entity_name.toLowerCase().includes(s) ||
      row.action.toLowerCase().includes(s)
    );
  });

  const columns = [
    {
      title: "Fecha",
      dataIndex: "created_at",
      width: 170,
      render: (v: string) => dayjs(v).format("DD/MM/YY HH:mm:ss"),
    },
    {
      title: "Usuario",
      dataIndex: "username",
      width: 120,
    },
    {
      title: "Acción",
      dataIndex: "action",
      width: 160,
      render: (v: string) => (
        <Tag color={actionColor[v] ?? "default"}>{v.replace(/_/g, " ")}</Tag>
      ),
    },
    {
      title: "Tipo",
      dataIndex: "entity_type",
      width: 100,
      render: (v: string) => entityLabels[v] ?? v,
    },
    {
      title: "Entidad",
      dataIndex: "entity_name",
      render: (v: string, r: AuditLogEntry) =>
        r.entity_id ? `#${r.entity_id} — ${v}` : v,
    },
    {
      title: "Detalle",
      dataIndex: "details",
      render: (v?: string) => v ?? "—",
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Typography.Title level={3} style={{ marginBottom: 16 }}>
        Log de Auditoría
      </Typography.Title>

      <Card style={{ marginBottom: 16 }}>
        <Row gutter={16}>
          <Col flex="200px">
            <Select
              allowClear
              placeholder="Filtrar por tipo"
              style={{ width: "100%" }}
              onChange={setEntityType}
              options={Object.entries(entityLabels).map(([k, v]) => ({
                value: k,
                label: v,
              }))}
            />
          </Col>
          <Col flex="auto">
            <Input.Search
              placeholder="Buscar por usuario, entidad o acción…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              allowClear
            />
          </Col>
        </Row>
      </Card>

      <Table
        rowKey="id"
        size="small"
        loading={isLoading}
        dataSource={filtered}
        columns={columns}
        pagination={{ pageSize: 50, showTotal: (t) => `${t} registros` }}
      />
    </div>
  );
}

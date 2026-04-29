import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Badge,
  Button,
  Input,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import {
  PlusOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  DeleteOutlined,
  EditOutlined,
  SyncOutlined,
} from "@ant-design/icons";
import { clientsApi } from "@/services/api";
import type { Client, ClientStatus } from "@/types";

const { Title } = Typography;

const statusConfig: Record<ClientStatus, { color: string; label: string }> = {
  active: { color: "green", label: "Activo" },
  suspended: { color: "orange", label: "Suspendido" },
  cancelled: { color: "red", label: "Cancelado" },
};

export default function ClientList() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<ClientStatus | undefined>();

  const { data = [], isLoading, error } = useQuery({
    queryKey: ["clients", { search, status: statusFilter }],
    queryFn: () => clientsApi.list({ search: search || undefined, status: statusFilter }),
  });

  const suspendMutation = useMutation({
    mutationFn: (id: number) => clientsApi.suspend(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["clients"] }); message.success("Cliente suspendido"); },
    onError: () => message.error("Error al suspender"),
  });

  const activateMutation = useMutation({
    mutationFn: (id: number) => clientsApi.activate(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["clients"] }); message.success("Cliente activado"); },
    onError: () => message.error("Error al activar"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => clientsApi.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["clients"] }); message.success("Cliente eliminado"); },
    onError: () => message.error("Error al eliminar"),
  });

  const syncMutation = useMutation({
    mutationFn: (id: number) => clientsApi.syncMikrotik(id),
    onSuccess: () => message.success("Queue sincronizada"),
    onError: () => message.warning("No se pudo sincronizar con Mikrotik"),
  });

  const columns = [
    {
      title: "Cliente",
      key: "name",
      render: (_: unknown, r: Client) => (
        <a onClick={() => navigate(`/clients/${r.id}`)}>{r.full_name}</a>
      ),
    },
    { title: "IP", dataIndex: "ip_address", key: "ip" },
    { title: "Teléfono", dataIndex: "phone", key: "phone", render: (v: string) => v ?? "—" },
    {
      title: "Plan",
      key: "plan",
      render: (_: unknown, r: Client) =>
        r.plan ? `${r.plan.name} (${r.plan.download_mbps}/${r.plan.upload_mbps} Mbps)` : "—",
    },
    { title: "Router", key: "router", render: (_: unknown, r: Client) => r.router?.name ?? "—" },
    {
      title: "Estado",
      dataIndex: "status",
      key: "status",
      render: (s: ClientStatus) => <Tag color={statusConfig[s].color}>{statusConfig[s].label}</Tag>,
    },
    {
      title: "Acciones",
      key: "actions",
      align: "right" as const,
      render: (_: unknown, r: Client) => (
        <Space size={4}>
          <Tooltip title="Editar">
            <Button size="small" icon={<EditOutlined />} onClick={() => navigate(`/clients/${r.id}`)} />
          </Tooltip>
          <Tooltip title="Sync Mikrotik">
            <Button size="small" icon={<SyncOutlined />} onClick={() => syncMutation.mutate(r.id)} />
          </Tooltip>
          {r.status === "active" ? (
            <Tooltip title="Suspender">
              <Popconfirm title="¿Suspender cliente?" onConfirm={() => suspendMutation.mutate(r.id)}>
                <Button size="small" icon={<PauseCircleOutlined />} />
              </Popconfirm>
            </Tooltip>
          ) : r.status === "suspended" ? (
            <Tooltip title="Activar">
              <Popconfirm title="¿Activar cliente?" onConfirm={() => activateMutation.mutate(r.id)}>
                <Button size="small" icon={<PlayCircleOutlined />} type="primary" ghost />
              </Popconfirm>
            </Tooltip>
          ) : null}
          <Tooltip title="Eliminar">
            <Popconfirm title="¿Eliminar cliente?" onConfirm={() => deleteMutation.mutate(r.id)}>
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          Clientes
          <Badge count={data.length} style={{ marginLeft: 8, backgroundColor: "#1677ff" }} />
        </Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate("/clients/new")}>
          Nuevo cliente
        </Button>
      </div>

      <Space style={{ marginBottom: 16 }}>
        <Input.Search
          placeholder="Buscar por nombre, IP o teléfono…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ width: 280 }}
          allowClear
        />
        <Select
          placeholder="Estado"
          style={{ width: 140 }}
          allowClear
          value={statusFilter}
          onChange={(v) => setStatusFilter(v)}
          options={[
            { value: "active", label: "Activos" },
            { value: "suspended", label: "Suspendidos" },
            { value: "cancelled", label: "Cancelados" },
          ]}
        />
      </Space>

      {error && <Alert type="error" message="Error cargando clientes" style={{ marginBottom: 16 }} />}

      <Table
        loading={isLoading}
        dataSource={data}
        rowKey="id"
        columns={columns}
        size="small"
        pagination={{ pageSize: 50, showTotal: (t) => `${t} clientes` }}
      />
    </div>
  );
}

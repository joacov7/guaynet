import { useEffect, useState } from "react";
import { usePermissions } from "@/contexts/PermissionsContext";
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
  StopOutlined,
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
  const { canEdit } = usePermissions();
  const [typed, setTyped] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<ClientStatus | undefined>();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);

  // One query when the user stops typing, not one per key
  useEffect(() => {
    const t = setTimeout(() => {
      setSearch(typed.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(t);
  }, [typed]);

  const { data: pageData, isFetching, error } = useQuery({
    queryKey: ["clients", { search, status: statusFilter, page, pageSize }],
    queryFn: () =>
      clientsApi.listPage({
        search: search || undefined,
        status: statusFilter,
        skip: (page - 1) * pageSize,
        limit: pageSize,
      }),
    placeholderData: (prev) => prev,
  });
  const data = pageData?.items ?? [];
  const total = pageData?.total ?? 0;

  const { data: connectivity = {} } = useQuery({
    queryKey: ["clients-connection-status"],
    queryFn: clientsApi.connectionStatus,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  const suspendMutation = useMutation({
    mutationFn: (id: number) => clientsApi.suspend(id),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["clients"] });
      if (data.mikrotik_error) message.warning(`Suspendido. Error MikroTik: ${data.mikrotik_error}`, 8);
      else message.success("Cliente suspendido");
    },
    onError: () => message.error("Error al suspender"),
  });

  const activateMutation = useMutation({
    mutationFn: (id: number) => clientsApi.activate(id),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["clients"] });
      if (data.mikrotik_error) message.warning(`Activado. Error MikroTik: ${data.mikrotik_error}`, 8);
      else message.success("Cliente activado");
    },
    onError: () => message.error("Error al activar"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => clientsApi.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["clients"] }); message.success("Cliente eliminado"); },
    onError: () => message.error("Error al eliminar"),
  });

  const cancelMutation = useMutation({
    mutationFn: (id: number) => clientsApi.cancel(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["clients"] }); message.success("Cliente dado de baja"); },
    onError: () => message.error("Error al dar de baja"),
  });

  const syncMutation = useMutation({
    mutationFn: (id: number) => clientsApi.syncMikrotik(id),
    onSuccess: () => message.success("Queue sincronizada"),
    onError: (err: any) => message.error(
      err.response?.data?.detail || `HTTP ${err.response?.status ?? "?"}: no se pudo sincronizar con Mikrotik`, 10
    ),
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
    {
      title: "Router",
      key: "router",
      render: (_: unknown, r: Client) => r.router?.name ?? "—",
    },
    {
      title: "Conectividad",
      key: "connectivity",
      render: (_: unknown, r: Client) => {
        const status = connectivity[String(r.id)]?.status ?? "unknown";
        if (status === "online") return <Tag color="green">Detectado</Tag>;
        if (status === "not_detected") return <Tag color="red">No detectado</Tag>;
        return <Tag color="default">Sin datos</Tag>;
      },
    },
    {
      title: "Estado",
      dataIndex: "status",
      key: "status",
      render: (s: ClientStatus) => (
        <Tag color={statusConfig[s].color}>{statusConfig[s].label}</Tag>
      ),
    },
    {
      title: "Acciones",
      key: "actions",
      align: "right" as const,
      render: (_: unknown, r: Client) => (
        <Space size={4}>
          <Tooltip title="Editar">
            <Button size="small" icon={<EditOutlined />} onClick={() => navigate(`/clients/${r.id}/edit`)} />
          </Tooltip>
          {canEdit("clients") && (
            <Tooltip title="Volver a aplicar en el MikroTik">
              <Button size="small" icon={<SyncOutlined />} onClick={() => syncMutation.mutate(r.id)} />
            </Tooltip>
          )}
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
          {r.status !== "cancelled" && (
            <Tooltip title="Dar de baja">
              <Popconfirm
                title="¿Dar de baja al cliente?"
                description="Se eliminará la queue de Mikrotik y se liberará la antena."
                onConfirm={() => cancelMutation.mutate(r.id)}
                okText="Dar de baja"
                okButtonProps={{ danger: true }}
              >
                <Button size="small" icon={<StopOutlined />} danger />
              </Popconfirm>
            </Tooltip>
          )}
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
          <Badge count={total} overflowCount={99999} style={{ marginLeft: 8, backgroundColor: "#1677ff" }} />
        </Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate("/clients/new")}>
          Nuevo cliente
        </Button>
      </div>

      <Space style={{ marginBottom: 16 }}>
        <Input.Search
          placeholder="Buscar por nombre, IP, DNI, teléfono o MAC…"
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
          style={{ width: 280 }}
          allowClear
        />
        <Select
          placeholder="Estado"
          style={{ width: 140 }}
          allowClear
          value={statusFilter}
          onChange={(v) => {
            setStatusFilter(v);
            setPage(1);
          }}
          options={[
            { value: "active", label: "Activos" },
            { value: "suspended", label: "Suspendidos" },
            { value: "cancelled", label: "Cancelados" },
          ]}
        />
      </Space>

      {error && <Alert type="error" message="Error cargando clientes" style={{ marginBottom: 16 }} />}

      <Table
        loading={isFetching}
        dataSource={data}
        rowKey="id"
        columns={columns}
        size="small"
        scroll={{ x: 900 }}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          pageSizeOptions: [25, 50, 100, 200],
          showTotal: (t) => `${t} clientes`,
          onChange: (p, size) => {
            setPage(size !== pageSize ? 1 : p);
            setPageSize(size);
          },
        }}
      />
    </div>
  );
}

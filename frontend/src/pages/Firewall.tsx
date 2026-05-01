import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Badge,
  Button,
  Empty,
  Popconfirm,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import {
  DeleteOutlined,
  PlusOutlined,
  ReloadOutlined,
  SafetyOutlined,
  ScanOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { firewallApi, routersApi } from "@/services/api";
import type { DHCPLease, FirewallRule, MangleRule } from "@/types";

const { Title, Text } = Typography;

const FILTER_TEMPLATES = [
  { key: "basic_security", label: "Seguridad básica", description: "Drop inválidos, proteger WAN, permitir gestión desde LAN" },
  { key: "icmp_limit", label: "Limitar ICMP", description: "Rate-limit para prevenir flood ICMP" },
  { key: "drop_invalid", label: "Drop inválidos", description: "Descartar paquetes de conexiones inválidas" },
];

export default function Firewall() {
  const navigate = useNavigate();
  const [routerId, setRouterId] = useState<number | undefined>();

  const { data: routers = [] } = useQuery({ queryKey: ["routers"], queryFn: routersApi.list });

  const {
    data: dhcpData,
    isLoading: dhcpLoading,
    refetch: refetchDhcp,
  } = useQuery({
    queryKey: ["dhcp-scan", routerId],
    queryFn: () => firewallApi.dhcpScan(routerId!),
    enabled: routerId != null,
  });

  const {
    data: filterRules = [],
    isLoading: filterLoading,
    refetch: refetchFilter,
  } = useQuery({
    queryKey: ["firewall-filter", routerId],
    queryFn: () => firewallApi.getFilterRules(routerId!),
    enabled: routerId != null,
  });

  const {
    data: mangleRules = [],
    isLoading: mangleLoading,
    refetch: refetchMangle,
  } = useQuery({
    queryKey: ["firewall-mangle", routerId],
    queryFn: () => firewallApi.getMangleRules(routerId!),
    enabled: routerId != null,
  });

  const {
    data: pcqQueues = [],
    isLoading: pcqLoading,
    refetch: refetchPcq,
  } = useQuery({
    queryKey: ["pcq-queues", routerId],
    queryFn: () => firewallApi.getPCQQueues(routerId!),
    enabled: routerId != null,
  });

  const deleteFilterMutation = useMutation({
    mutationFn: (ruleId: string) => firewallApi.deleteFilterRule(routerId!, ruleId),
    onSuccess: () => { refetchFilter(); message.success("Regla eliminada"); },
    onError: () => message.error("Error al eliminar regla"),
  });

  const deleteMangeMutation = useMutation({
    mutationFn: (ruleId: string) => firewallApi.deleteMangleRule(routerId!, ruleId),
    onSuccess: () => { refetchMangle(); message.success("Regla eliminada"); },
    onError: () => message.error("Error al eliminar regla"),
  });

  const templateMutation = useMutation({
    mutationFn: (template: string) => firewallApi.applyTemplate(routerId!, template),
    onSuccess: (res) => {
      refetchFilter();
      refetchMangle();
      message.success(res.message);
    },
    onError: (err: any) => message.error(err.response?.data?.detail ?? "Error al aplicar template"),
  });

  const setupPcqMutation = useMutation({
    mutationFn: () => firewallApi.setupPCQ(routerId!),
    onSuccess: (res) => {
      refetchPcq();
      message.success(res.added > 0 ? `PCQ configurado (${res.added} tipos creados)` : "Los tipos PCQ ya existen");
    },
    onError: (err: any) => message.error(err.response?.data?.detail ?? "Error al configurar PCQ"),
  });

  const filterColumns = [
    {
      title: "#",
      key: "idx",
      width: 40,
      render: (_: unknown, __: unknown, i: number) => i + 1,
    },
    {
      title: "Chain",
      dataIndex: "chain",
      key: "chain",
      render: (v: string) => <Tag>{v}</Tag>,
    },
    {
      title: "Action",
      dataIndex: "action",
      key: "action",
      render: (v: string) => (
        <Tag color={v === "drop" ? "red" : v === "accept" ? "green" : "blue"}>{v}</Tag>
      ),
    },
    {
      title: "Src",
      dataIndex: "src_address",
      key: "src",
      render: (v: string) => v || <Text type="secondary">any</Text>,
    },
    {
      title: "Dst",
      dataIndex: "dst_address",
      key: "dst",
      render: (v: string) => v || <Text type="secondary">any</Text>,
    },
    {
      title: "Proto",
      dataIndex: "protocol",
      key: "proto",
      render: (v: string) => v || <Text type="secondary">any</Text>,
    },
    {
      title: "Dst Port",
      dataIndex: "dst_port",
      key: "dst_port",
      render: (v: string) => v || "—",
    },
    {
      title: "Comentario",
      dataIndex: "comment",
      key: "comment",
      render: (v: string) => v || "—",
    },
    {
      title: "Estado",
      dataIndex: "disabled",
      key: "disabled",
      render: (v: boolean) => (
        <Tag color={v ? "orange" : "green"}>{v ? "Deshabilitada" : "Activa"}</Tag>
      ),
    },
    {
      title: "",
      key: "actions",
      align: "right" as const,
      render: (_: unknown, r: FirewallRule) => (
        <Popconfirm title="¿Eliminar esta regla del router?" onConfirm={() => deleteFilterMutation.mutate(r.id)}>
          <Button size="small" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ];

  const mangleColumns = [
    {
      title: "#",
      key: "idx",
      width: 40,
      render: (_: unknown, __: unknown, i: number) => i + 1,
    },
    {
      title: "Chain",
      dataIndex: "chain",
      key: "chain",
      render: (v: string) => <Tag>{v}</Tag>,
    },
    {
      title: "Action",
      dataIndex: "action",
      key: "action",
      render: (v: string) => <Tag color="blue">{v}</Tag>,
    },
    {
      title: "Marca",
      dataIndex: "new_packet_mark",
      key: "mark",
      render: (v: string) => v ? <Tag color="purple">{v}</Tag> : "—",
    },
    {
      title: "Proto",
      dataIndex: "protocol",
      key: "proto",
      render: (v: string) => v || <Text type="secondary">any</Text>,
    },
    {
      title: "Dst Port",
      dataIndex: "dst_port",
      key: "dst_port",
      render: (v: string) => v || "—",
    },
    {
      title: "Comentario",
      dataIndex: "comment",
      key: "comment",
      render: (v: string) => v || "—",
    },
    {
      title: "Estado",
      dataIndex: "disabled",
      key: "disabled",
      render: (v: boolean) => (
        <Tag color={v ? "orange" : "green"}>{v ? "Deshabilitada" : "Activa"}</Tag>
      ),
    },
    {
      title: "",
      key: "actions",
      align: "right" as const,
      render: (_: unknown, r: MangleRule) => (
        <Popconfirm title="¿Eliminar esta regla del router?" onConfirm={() => deleteMangeMutation.mutate(r.id)}>
          <Button size="small" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ];

  const dhcpColumns = [
    {
      title: "IP",
      dataIndex: "address",
      key: "address",
      render: (v: string, r: DHCPLease) => (
        <Space>
          <span>{v}</span>
          {r.is_registered && (
            <Tag color="green" style={{ fontSize: 11 }}>
              Registrado
            </Tag>
          )}
        </Space>
      ),
    },
    { title: "MAC", dataIndex: "mac_address", key: "mac" },
    {
      title: "Hostname",
      dataIndex: "hostname",
      key: "hostname",
      render: (v: string) => v || "—",
    },
    { title: "Estado DHCP", dataIndex: "status", key: "status" },
    {
      title: "Cliente",
      key: "client",
      render: (_: unknown, r: DHCPLease) =>
        r.is_registered ? (
          <a onClick={() => navigate(`/clients/${r.client_id}`)}>{r.client_name}</a>
        ) : (
          <Button
            size="small"
            type="primary"
            ghost
            icon={<PlusOutlined />}
            onClick={() =>
              navigate("/clients/new", {
                state: { ip: r.address, mac: r.mac_address },
              })
            }
          >
            Crear cliente
          </Button>
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
          Firewall & QoS
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
              key: "dhcp",
              label: (
                <span>
                  <ScanOutlined /> DHCP Scan
                  {dhcpData && dhcpData.unregistered > 0 && (
                    <Badge
                      count={dhcpData.unregistered}
                      style={{ marginLeft: 6, backgroundColor: "#faad14" }}
                    />
                  )}
                </span>
              ),
              children: (
                <div>
                  <Space style={{ marginBottom: 12 }}>
                    {dhcpData && (
                      <>
                        <Tag color="green">Registrados: {dhcpData.registered}</Tag>
                        <Tag color="orange">Sin registrar: {dhcpData.unregistered}</Tag>
                        <Tag>Total: {dhcpData.total}</Tag>
                      </>
                    )}
                    <Button
                      size="small"
                      icon={<ReloadOutlined />}
                      onClick={() => refetchDhcp()}
                      loading={dhcpLoading}
                    >
                      Escanear
                    </Button>
                  </Space>
                  <Table
                    loading={dhcpLoading}
                    dataSource={dhcpData?.leases ?? []}
                    rowKey="address"
                    columns={dhcpColumns}
                    size="small"
                    pagination={{ pageSize: 25 }}
                  />
                </div>
              ),
            },
            {
              key: "filter",
              label: (
                <span>
                  <SafetyOutlined /> Firewall Filter
                  <Badge
                    count={filterRules.length}
                    style={{ marginLeft: 6, backgroundColor: "#1677ff" }}
                  />
                </span>
              ),
              children: (
                <div>
                  <div style={{ marginBottom: 12 }}>
                    <Text strong style={{ marginRight: 12 }}>
                      Aplicar template:
                    </Text>
                    <Space wrap>
                      {FILTER_TEMPLATES.map((t) => (
                        <Tooltip key={t.key} title={t.description}>
                          <Popconfirm
                            title={`¿Aplicar "${t.label}"? Se agregarán reglas al final de la lista de filtros.`}
                            onConfirm={() => templateMutation.mutate(t.key)}
                          >
                            <Button
                              size="small"
                              icon={<SafetyOutlined />}
                              loading={templateMutation.isPending}
                            >
                              {t.label}
                            </Button>
                          </Popconfirm>
                        </Tooltip>
                      ))}
                    </Space>
                  </div>
                  <Table
                    loading={filterLoading}
                    dataSource={filterRules}
                    rowKey="id"
                    columns={filterColumns}
                    size="small"
                    pagination={{ pageSize: 50, showTotal: (t) => `${t} reglas` }}
                  />
                </div>
              ),
            },
            {
              key: "mangle",
              label: (
                <span>
                  <ThunderboltOutlined /> Mangle / QoS
                  <Badge
                    count={mangleRules.length}
                    style={{ marginLeft: 6, backgroundColor: "#722ed1" }}
                  />
                </span>
              ),
              children: (
                <div>
                  <div style={{ marginBottom: 12 }}>
                    <Tooltip title="Agrega mangle rules para marcar VoIP (SIP/RTP), DNS, HTTPS y HTTP. También crea queue types PCQ.">
                      <Popconfirm
                        title="¿Aplicar priorización QoS? Se agregarán reglas mangle para VoIP, DNS, HTTPS y HTTP, y se configurarán los queue types PCQ."
                        onConfirm={() => templateMutation.mutate("qos_prioritization")}
                      >
                        <Button
                          type="primary"
                          icon={<ThunderboltOutlined />}
                          loading={templateMutation.isPending}
                        >
                          Aplicar priorización QoS (VoIP / DNS / HTTPS)
                        </Button>
                      </Popconfirm>
                    </Tooltip>
                  </div>
                  <Table
                    loading={mangleLoading}
                    dataSource={mangleRules}
                    rowKey="id"
                    columns={mangleColumns}
                    size="small"
                    pagination={{ pageSize: 50, showTotal: (t) => `${t} reglas` }}
                  />
                </div>
              ),
            },
            {
              key: "pcq",
              label: "PCQ Queues",
              children: (
                <div>
                  <div style={{ marginBottom: 16 }}>
                    <Space>
                      <Text type="secondary">
                        PCQ distribuye el ancho de banda equitativamente entre conexiones de cada cliente.
                      </Text>
                      <Popconfirm
                        title="¿Crear pcq-download y pcq-upload si no existen?"
                        onConfirm={() => setupPcqMutation.mutate()}
                      >
                        <Button
                          type="primary"
                          loading={setupPcqMutation.isPending}
                          icon={<ThunderboltOutlined />}
                        >
                          Configurar PCQ
                        </Button>
                      </Popconfirm>
                      <Button
                        size="small"
                        icon={<ReloadOutlined />}
                        onClick={() => refetchPcq()}
                      />
                    </Space>
                  </div>
                  <Table
                    loading={pcqLoading}
                    dataSource={pcqQueues}
                    rowKey="id"
                    columns={[
                      { title: "Nombre", dataIndex: "name", key: "name" },
                      { title: "Tipo", dataIndex: "kind", key: "kind" },
                      {
                        title: "Rate",
                        dataIndex: "pcq_rate",
                        key: "pcq_rate",
                        render: (v: string) => v || "auto",
                      },
                      { title: "Limit", dataIndex: "pcq_limit", key: "pcq_limit" },
                      {
                        title: "Clasificador",
                        dataIndex: "pcq_classifier",
                        key: "classifier",
                      },
                    ]}
                    size="small"
                    pagination={false}
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

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Badge,
  Button,
  Empty,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Spin,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import {
  DeleteOutlined,
  DownloadOutlined,
  PlusOutlined,
  ReloadOutlined,
  SafetyOutlined,
  ScanOutlined,
  ThunderboltOutlined,
  BranchesOutlined,
} from "@ant-design/icons";
import { firewallApi, plansApi, routersApi } from "@/services/api";
import type { DHCPLease, FirewallRule, MangleRule, Plan, QueueTreeEntry } from "@/types";

const { Title, Text } = Typography;

// ── Queue Tree helpers ────────────────────────────────────────────────────────

function fmtBps(bps: number): string {
  if (bps === 0) return "0";
  if (bps >= 1_000_000) return `${(bps / 1_000_000).toFixed(1)} Mbps`;
  if (bps >= 1_000) return `${(bps / 1_000).toFixed(0)} kbps`;
  return `${bps} bps`;
}

function utilizationColor(pct: number): string {
  if (pct >= 90) return "#ff4d4f";
  if (pct >= 70) return "#faad14";
  if (pct >= 40) return "#52c41a";
  return "#1677ff";
}

const PRIORITY_COLOR: Record<string, string> = {
  "1": "red", "2": "orange", "3": "gold",
  "4": "lime", "5": "green", "6": "cyan",
  "7": "blue", "8": "default",
};

interface TreeNode extends QueueTreeEntry {
  children: TreeNode[];
  depth: number;
}

function buildTree(entries: QueueTreeEntry[]): TreeNode[] {
  const byName = new Map<string, TreeNode>();
  const roots: TreeNode[] = [];

  entries.forEach((e) => byName.set(e.name, { ...e, children: [], depth: 0 }));

  byName.forEach((node) => {
    const parent = byName.get(node.parent);
    if (parent) {
      node.depth = parent.depth + 1;
      parent.children.push(node);
    } else {
      roots.push(node);
    }
  });

  return roots;
}

function QueueTreeNode({ node, isLast, prefix }: { node: TreeNode; isLast: boolean; prefix: string }) {
  const [expanded, setExpanded] = useState(true);
  const hasChildren = node.children.length > 0;
  const pct = node.max_limit_bps > 0 ? Math.min(100, (node.rate_bps / node.max_limit_bps) * 100) : 0;
  const color = utilizationColor(pct);

  const connector = prefix + (isLast ? "└─ " : "├─ ");
  const childPrefix = prefix + (isLast ? "    " : "│   ");

  return (
    <div style={{ fontFamily: "monospace", fontSize: 13 }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          padding: "5px 0",
          gap: 8,
          opacity: node.disabled ? 0.45 : 1,
          cursor: hasChildren ? "pointer" : "default",
        }}
        onClick={() => hasChildren && setExpanded((v) => !v)}
      >
        <span style={{ color: "#8c8c8c", whiteSpace: "pre", userSelect: "none" }}>{connector}</span>

        <span style={{ fontWeight: node.depth <= 1 ? 600 : 400, minWidth: 160 }}>
          {hasChildren && (
            <span style={{ marginRight: 4, color: "#1677ff" }}>{expanded ? "▾" : "▸"}</span>
          )}
          {node.name}
          {node.disabled && <Tag color="orange" style={{ marginLeft: 6, fontSize: 10 }}>off</Tag>}
        </span>

        {node.packet_mark && (
          <Tag color="purple" style={{ fontSize: 11, margin: 0 }}>{node.packet_mark}</Tag>
        )}

        <Tag color={PRIORITY_COLOR[node.priority] ?? "default"} style={{ fontSize: 11, margin: 0 }}>
          p{node.priority}
        </Tag>

        {node.max_limit && (
          <span style={{ color: "#8c8c8c", fontSize: 12 }}>/ {node.max_limit}</span>
        )}

        <span style={{ flex: 1 }} />

        <span style={{ minWidth: 90, textAlign: "right", fontWeight: 500, color }}>
          {fmtBps(node.rate_bps)}
        </span>

        {node.max_limit_bps > 0 && (
          <div style={{ width: 120, background: "#f0f0f0", borderRadius: 4, overflow: "hidden" }}>
            <div
              style={{
                height: 8,
                width: `${pct}%`,
                background: color,
                borderRadius: 4,
                transition: "width 0.4s ease",
              }}
            />
          </div>
        )}

        {node.max_limit_bps > 0 && (
          <span style={{ minWidth: 38, fontSize: 11, color, textAlign: "right" }}>
            {pct.toFixed(0)}%
          </span>
        )}
      </div>

      {hasChildren && expanded &&
        node.children.map((child, i) => (
          <QueueTreeNode
            key={child.id}
            node={child}
            isLast={i === node.children.length - 1}
            prefix={childPrefix}
          />
        ))
      }
    </div>
  );
}

function QueueTreeView({ entries, loading, routerId, onApplyPro }: {
  entries: QueueTreeEntry[];
  loading: boolean;
  routerId: number;
  onApplyPro: () => void;
}) {
  const roots = buildTree(entries);
  const totalRateBps = roots.reduce((s, n) => s + n.rate_bps, 0);

  if (loading && entries.length === 0) return <Spin />;
  if (!loading && entries.length === 0) {
    return (
      <Empty description="No hay entradas en el Queue Tree de este router">
        <Button type="primary" icon={<ThunderboltOutlined />} onClick={onApplyPro}>
          Aplicar árbol QoS profesional
        </Button>
      </Empty>
    );
  }

  return (
    <div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
        <Text type="secondary" style={{ fontSize: 13 }}>
          Tráfico total activo: <strong style={{ color: "#1677ff" }}>{fmtBps(totalRateBps)}</strong>
        </Text>
        <span style={{ flex: 1 }} />
        <Tag color="blue">Auto-refresh 5s</Tag>
        <Button
          type="primary"
          icon={<ThunderboltOutlined />}
          size="small"
          onClick={onApplyPro}
        >
          Aplicar árbol profesional
        </Button>
      </div>

      <div style={{
        background: "#fafafa",
        border: "1px solid #f0f0f0",
        borderRadius: 8,
        padding: "12px 16px",
        overflowX: "auto",
      }}>
        {roots.length === 0 ? (
          <Text type="secondary">Sin entradas en el árbol</Text>
        ) : (
          roots.map((root, i) => (
            <QueueTreeNode key={root.id} node={root} isLast={i === roots.length - 1} prefix="" />
          ))
        )}
      </div>
    </div>
  );
}

const FILTER_TEMPLATES = [
  { key: "basic_security", label: "Seguridad básica", description: "Drop inválidos, proteger WAN, permitir gestión desde LAN" },
  { key: "icmp_limit", label: "Limitar ICMP", description: "Rate-limit para prevenir flood ICMP" },
  { key: "drop_invalid", label: "Drop inválidos", description: "Descartar paquetes de conexiones inválidas" },
];

export default function Firewall() {
  const navigate = useNavigate();
  const [routerId, setRouterId] = useState<number | undefined>();
  const [selectedLeases, setSelectedLeases] = useState<DHCPLease[]>([]);
  const [importPlanId, setImportPlanId] = useState<number | undefined>();
  const [importModalOpen, setImportModalOpen] = useState(false);

  const { data: routers = [] } = useQuery({ queryKey: ["routers"], queryFn: routersApi.list });
  const { data: plans = [] } = useQuery<Plan[]>({ queryKey: ["plans"], queryFn: () => plansApi.list() });

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

  const [proModalOpen, setProModalOpen] = useState(false);
  const [proDownMbps, setProDownMbps] = useState<number>(100);
  const [proUpMbps, setProUpMbps] = useState<number>(30);
  const [queueTreeActive, setQueueTreeActive] = useState(false);

  const {
    data: queueTreeData = [],
    isLoading: queueTreeLoading,
    refetch: refetchQueueTree,
  } = useQuery({
    queryKey: ["queue-tree", routerId],
    queryFn: () => firewallApi.getQueueTreeStats(routerId!),
    enabled: routerId != null && queueTreeActive,
    refetchInterval: queueTreeActive ? 5000 : false,
  });

  const proTreeMutation = useMutation({
    mutationFn: () => firewallApi.applyProfessionalTree(routerId!, proDownMbps, proUpMbps),
    onSuccess: (res) => {
      message.success(res.message);
      setProModalOpen(false);
      refetchQueueTree();
    },
    onError: (err: any) => message.error(err.response?.data?.detail ?? "Error al aplicar árbol"),
  });

  const importMutation = useMutation({
    mutationFn: () => firewallApi.dhcpImport(
      routerId!,
      selectedLeases.map((l) => ({ address: l.address, mac_address: l.mac_address, hostname: l.hostname ?? undefined })),
      importPlanId!,
    ),
    onSuccess: (res) => {
      message.success(`Importados: ${res.created} clientes, omitidos: ${res.skipped}`);
      setImportModalOpen(false);
      setSelectedLeases([]);
      refetchDhcp();
    },
    onError: (err: any) => message.error(err.response?.data?.detail ?? "Error al importar"),
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
                  <Space style={{ marginBottom: 12 }} wrap>
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
                    {selectedLeases.length > 0 && (
                      <Button
                        size="small"
                        type="primary"
                        icon={<DownloadOutlined />}
                        onClick={() => setImportModalOpen(true)}
                      >
                        Importar {selectedLeases.length} seleccionados
                      </Button>
                    )}
                  </Space>
                  <Table
                    loading={dhcpLoading}
                    dataSource={dhcpData?.leases ?? []}
                    rowKey="address"
                    columns={dhcpColumns}
                    size="small"
                    pagination={{ pageSize: 25 }}
                    rowSelection={{
                      selectedRowKeys: selectedLeases.map((l) => l.address),
                      onChange: (_, rows) => setSelectedLeases(rows.filter((r) => !r.is_registered)),
                      getCheckboxProps: (r: DHCPLease) => ({ disabled: r.is_registered }),
                    }}
                  />
                  <Modal
                    title={`Importar ${selectedLeases.length} clientes desde DHCP`}
                    open={importModalOpen}
                    onCancel={() => setImportModalOpen(false)}
                    onOk={() => importMutation.mutate()}
                    okText="Importar"
                    confirmLoading={importMutation.isPending}
                    okButtonProps={{ disabled: !importPlanId }}
                  >
                    <p>Seleccioná el plan que se asignará a todos los clientes importados:</p>
                    <Select
                      style={{ width: "100%" }}
                      placeholder="Seleccionar plan"
                      value={importPlanId}
                      onChange={setImportPlanId}
                      options={plans.map((p: Plan) => ({
                        value: p.id,
                        label: `${p.name} — ${p.download_mbps}/${p.upload_mbps} Mbps ($${p.price})`,
                      }))}
                    />
                    <p style={{ marginTop: 12, color: "#888", fontSize: 12 }}>
                      El nombre del cliente se deriva del hostname DHCP. Podés editarlo después desde la ficha del cliente.
                    </p>
                  </Modal>
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
              key: "queue-tree",
              label: (
                <span>
                  <BranchesOutlined /> Queue Tree
                  {queueTreeData.length > 0 && (
                    <Badge count={queueTreeData.length} style={{ marginLeft: 6, backgroundColor: "#1677ff" }} />
                  )}
                </span>
              ),
              children: (
                <div>
                  {!queueTreeActive ? (
                    <div style={{ textAlign: "center", padding: 40 }}>
                      <Button
                        type="primary"
                        size="large"
                        icon={<BranchesOutlined />}
                        onClick={() => setQueueTreeActive(true)}
                      >
                        Cargar Queue Tree
                      </Button>
                      <div style={{ marginTop: 8 }}>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          Obtiene el árbol QoS del router con métricas en tiempo real
                        </Text>
                      </div>
                    </div>
                  ) : (
                    <QueueTreeView
                      entries={queueTreeData}
                      loading={queueTreeLoading}
                      routerId={routerId!}
                      onApplyPro={() => setProModalOpen(true)}
                    />
                  )}

                  <Modal
                    title="Aplicar árbol QoS profesional"
                    open={proModalOpen}
                    onCancel={() => setProModalOpen(false)}
                    onOk={() => proTreeMutation.mutate()}
                    okText="Aplicar"
                    confirmLoading={proTreeMutation.isPending}
                    okButtonProps={{ disabled: !proDownMbps || !proUpMbps }}
                  >
                    <Space direction="vertical" style={{ width: "100%" }}>
                      <Text>
                        Crea un árbol DOWNLOAD + UPLOAD con 7 clases de tráfico cada uno
                        (VoIP, DNS, HTTPS, Juegos, WhatsApp, HTTP, Resto) y las reglas mangle necesarias.
                        Las entradas existentes con el mismo nombre se actualizan.
                      </Text>
                      <div style={{ display: "flex", gap: 16, marginTop: 8 }}>
                        <div>
                          <Text strong>Capacidad bajada (Mbps)</Text>
                          <InputNumber
                            min={1}
                            max={10000}
                            value={proDownMbps}
                            onChange={(v) => setProDownMbps(v ?? 100)}
                            style={{ display: "block", marginTop: 4, width: 160 }}
                          />
                        </div>
                        <div>
                          <Text strong>Capacidad subida (Mbps)</Text>
                          <InputNumber
                            min={1}
                            max={10000}
                            value={proUpMbps}
                            onChange={(v) => setProUpMbps(v ?? 30)}
                            style={{ display: "block", marginTop: 4, width: 160 }}
                          />
                        </div>
                      </div>
                    </Space>
                  </Modal>
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

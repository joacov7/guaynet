import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Col, message, Row, Select, Space, Table, Tag, Typography } from "antd";
import { ReloadOutlined, ImportOutlined } from "@ant-design/icons";
import { firewallApi, plansApi, routersApi } from "@/services/api";
import type { DHCPLease } from "@/types";

const { Title, Text } = Typography;

export default function DHCPDevices() {
  const qc = useQueryClient();
  const [routerId, setRouterId] = useState<number>();
  const [planId, setPlanId] = useState<number>();
  const [selected, setSelected] = useState<DHCPLease[]>([]);

  const { data: routers = [] } = useQuery({ queryKey: ["routers"], queryFn: routersApi.list });
  const { data: plans = [] } = useQuery({ queryKey: ["plans"], queryFn: plansApi.list });
  const activePlans = useMemo(() => plans.filter((p) => p.is_active), [plans]);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["dhcp-scan", routerId],
    queryFn: () => firewallApi.dhcpScan(routerId!),
    enabled: !!routerId,
    refetchOnWindowFocus: false,
  });

  const importMutation = useMutation({
    mutationFn: () => firewallApi.dhcpImport(
      routerId!,
      selected.map((item) => ({
        address: item.address,
        mac_address: item.mac_address,
        hostname: item.hostname,
      })),
      planId!,
    ),
    onSuccess: (res) => {
      message.success(`Altas: ${res.created}. Omitidos: ${res.skipped}. Pendientes de provisión MikroTik: ${res.provisioning_pending ?? res.created}.`);
      setSelected([]);
      qc.invalidateQueries({ queryKey: ["clients"] });
      refetch();
    },
    onError: (err: any) => message.error(err.response?.data?.detail ?? "Error al importar"),
  });

  const columns = [
    { title: "IP", dataIndex: "address", key: "address" },
    { title: "MAC", dataIndex: "mac_address", key: "mac" },
    { title: "Nombre detectado", dataIndex: "hostname", key: "hostname", render: (v?: string) => v || "—" },
    { title: "Estado DHCP", dataIndex: "status", key: "status" },
    {
      title: "Identificación",
      key: "identity",
      render: (_: unknown, row: DHCPLease) => {
        if (row.is_registered) return <Tag color="green">Cliente registrado</Tag>;
        if (row.match_reason === "ip_conflict") return <Tag color="orange">Conflicto de IP</Tag>;
        if (row.replacement_client_id) return <Tag color="blue">Posible reemplazo</Tag>;
        return <Tag color="default">Sin registrar</Tag>;
      },
    },
  ];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>Dispositivos DHCP</Title>
        <Button icon={<ReloadOutlined />} disabled={!routerId} loading={isLoading} onClick={() => refetch()}>
          Escanear nuevamente
        </Button>
      </div>
      <Card>
        <Row gutter={[16, 16]} align="middle">
          <Col xs={24} md={12}>
            <Text strong>Router MikroTik</Text>
            <Select
              style={{ width: "100%", marginTop: 6 }}
              placeholder="Seleccionar router"
              value={routerId}
              onChange={(value) => { setRouterId(value); setSelected([]); }}
              options={routers.map((r) => ({ value: r.id, label: r.name }))}
            />
          </Col>
          <Col xs={24} md={12}>
            <Text type="secondary">
              El escaneo consulta las concesiones DHCP del router. Solo se importan los equipos que no estén asociados a un cliente.
            </Text>
          </Col>
        </Row>
      </Card>

      {error && <Alert style={{ marginTop: 16 }} type="error" message="No se pudo consultar el router" />}
      {data?.error && <Alert style={{ marginTop: 16 }} type="warning" message="Error del router" description={data.error} />}

      {data && !data.error && (
        <Card style={{ marginTop: 16 }}>
          <Space wrap style={{ marginBottom: 16 }}>
            <Tag color="green">Registrados: {data.registered}</Tag>
            <Tag color="orange">Sin registrar: {data.unregistered}</Tag>
            <Tag>Total: {data.total}</Tag>
          </Space>
          <Row gutter={[12, 12]} style={{ marginBottom: 16 }} align="middle">
            <Col xs={24} md={9}>
              <Select
                style={{ width: "100%" }}
                placeholder="Plan para los nuevos clientes"
                value={planId}
                onChange={setPlanId}
                options={activePlans.map((p) => ({ value: p.id, label: `${p.name} (${p.download_mbps}/${p.upload_mbps} Mbps)` }))}
              />
            </Col>
            <Col>
              <Button
                type="primary"
                icon={<ImportOutlined />}
                disabled={!selected.length || !planId}
                loading={importMutation.isPending}
                onClick={() => importMutation.mutate()}
              >
                Importar {selected.length} seleccionados
              </Button>
            </Col>
          </Row>
          <Table
            rowKey={(row) => `${row.address}-${row.mac_address}`}
            size="small"
            loading={isLoading}
            dataSource={data.leases}
            columns={columns}
            rowSelection={{
              selectedRowKeys: selected.map((r) => `${r.address}-${r.mac_address}`),
              onChange: (_keys, rows) => setSelected(rows as DHCPLease[]),
              getCheckboxProps: (row: DHCPLease) => ({
                disabled: row.is_registered || row.match_reason === "ip_conflict" || !!row.replacement_client_id,
              }),
            }}
            pagination={{ pageSize: 25, showTotal: (total) => `${total} dispositivos` }}
          />
        </Card>
      )}
    </div>
  );
}

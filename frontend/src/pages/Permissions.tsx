import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, Switch, Table, Tabs, Typography, message, Tag, Spin } from "antd";
import { permissionsApi, RolePermission } from "@/services/api";

const { Title, Text } = Typography;

const SECTION_LABELS: Record<string, string> = {
  clients:    "Clientes",
  plans:      "Planes",
  routers:    "Routers",
  billing:    "Facturación",
  firewall:   "Firewall & QoS",
  monitoring: "Monitoreo",
  ubiquiti:   "Ubiquiti",
  users:      "Usuarios",
  map:        "Mapa de Red",
  ip_pool:    "Pool de IPs",
  audit:      "Auditoría",
  bandwidth:  "Ancho de Banda",
};

const ROLE_LABELS: Record<string, string> = {
  operator:   "Operador",
  technician: "Técnico",
};

function PermissionsTable({ role }: { role: string }) {
  const qc = useQueryClient();
  const { data = [], isLoading } = useQuery({
    queryKey: ["permissions"],
    queryFn: permissionsApi.list,
  });

  const mutation = useMutation({
    mutationFn: ({ section, can_view, can_edit }: { section: string; can_view: boolean; can_edit: boolean }) =>
      permissionsApi.update(role, section, can_view, can_edit),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["permissions"] });
      message.success("Permiso actualizado");
    },
    onError: () => message.error("Error al actualizar"),
  });

  const rolePerms = data.filter((p: RolePermission) => p.role === role);
  const bySection = Object.fromEntries(rolePerms.map((p: RolePermission) => [p.section, p]));

  const rows = Object.entries(SECTION_LABELS).map(([section, label]) => ({
    key: section,
    section,
    label,
    can_view: bySection[section]?.can_view ?? false,
    can_edit: bySection[section]?.can_edit ?? false,
  }));

  if (isLoading) return <Spin />;

  return (
    <Table dataSource={rows} rowKey="section" pagination={false} size="small">
      <Table.Column title="Sección" dataIndex="label" />
      <Table.Column
        title="Ver"
        dataIndex="can_view"
        width={100}
        render={(val: boolean, row: typeof rows[0]) => (
          <Switch
            checked={val}
            onChange={(checked) =>
              mutation.mutate({ section: row.section, can_view: checked, can_edit: checked ? row.can_edit : false })
            }
            loading={mutation.isPending}
          />
        )}
      />
      <Table.Column
        title="Editar"
        dataIndex="can_edit"
        width={100}
        render={(val: boolean, row: typeof rows[0]) => (
          <Switch
            checked={val}
            disabled={!row.can_view}
            onChange={(checked) =>
              mutation.mutate({ section: row.section, can_view: row.can_view, can_edit: checked })
            }
            loading={mutation.isPending}
          />
        )}
      />
    </Table>
  );
}

export default function Permissions() {
  const [activeRole, setActiveRole] = useState("operator");

  return (
    <div style={{ padding: 24 }}>
      <Title level={4}>Gestión de Permisos</Title>
      <Text type="secondary" style={{ display: "block", marginBottom: 16 }}>
        El rol <Tag color="gold">Admin</Tag> siempre tiene acceso completo y no puede ser restringido.
      </Text>
      <Card>
        <Tabs
          activeKey={activeRole}
          onChange={setActiveRole}
          items={Object.entries(ROLE_LABELS).map(([role, label]) => ({
            key: role,
            label,
            children: <PermissionsTable role={role} />,
          }))}
        />
      </Card>
    </div>
  );
}

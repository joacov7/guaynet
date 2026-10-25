import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Avatar,
  Button,
  Card,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import { UndoOutlined, UserOutlined } from "@ant-design/icons";
import { permissionsApi, RolePermission, UserPermissionEntry, usersApi } from "@/services/api";
import type { User } from "@/types";

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

// ── Permisos por rol ────────────────────────────────────────────────────────

function RolePermissionsTable({ role }: { role: string }) {
  const qc = useQueryClient();
  const { data = [], isLoading } = useQuery({ queryKey: ["permissions"], queryFn: permissionsApi.list });

  const mutation = useMutation({
    mutationFn: ({ section, can_view, can_edit }: { section: string; can_view: boolean; can_edit: boolean }) =>
      permissionsApi.update(role, section, can_view, can_edit),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["permissions"] }); message.success("Permiso actualizado"); },
    onError: () => message.error("Error al actualizar"),
  });

  const rolePerms = data.filter((p: RolePermission) => p.role === role);
  const bySection = Object.fromEntries(rolePerms.map((p: RolePermission) => [p.section, p]));
  const rows = Object.entries(SECTION_LABELS).map(([section, label]) => ({
    key: section, section, label,
    can_view: bySection[section]?.can_view ?? false,
    can_edit: bySection[section]?.can_edit ?? false,
  }));

  return (
    <Table dataSource={rows} rowKey="section" pagination={false} size="small" loading={isLoading}>
      <Table.Column title="Sección" dataIndex="label" />
      <Table.Column title="Ver" dataIndex="can_view" width={90}
        render={(val: boolean, row: typeof rows[0]) => (
          <Switch checked={val} size="small"
            onChange={(checked) => mutation.mutate({ section: row.section, can_view: checked, can_edit: checked ? row.can_edit : false })}
            loading={mutation.isPending} />
        )}
      />
      <Table.Column title="Editar" dataIndex="can_edit" width={90}
        render={(val: boolean, row: typeof rows[0]) => (
          <Switch checked={val} size="small" disabled={!row.can_view}
            onChange={(checked) => mutation.mutate({ section: row.section, can_view: row.can_view, can_edit: checked })}
            loading={mutation.isPending} />
        )}
      />
    </Table>
  );
}

// ── Permisos por usuario ────────────────────────────────────────────────────

function UserPermissionsPanel() {
  const qc = useQueryClient();
  const [userId, setUserId] = useState<number | null>(null);

  const { data: users = [] } = useQuery({ queryKey: ["users"], queryFn: usersApi.list });
  const nonAdmins = (users as User[]).filter((u) => u.role !== "admin" && !u.is_superuser);

  const { data: perms = [], isLoading } = useQuery({
    queryKey: ["user-perms", userId],
    queryFn: () => permissionsApi.getUserPerms(userId!),
    enabled: userId != null,
  });

  const selectedUser = (users as User[]).find((u) => u.id === userId);

  const setMut = useMutation({
    mutationFn: ({ section, can_view, can_edit }: { section: string; can_view: boolean; can_edit: boolean }) =>
      permissionsApi.setUserPerm(userId!, section, can_view, can_edit),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["user-perms", userId] }); message.success("Override aplicado"); },
    onError: () => message.error("Error al actualizar"),
  });

  const delMut = useMutation({
    mutationFn: (section: string) => permissionsApi.deleteUserPerm(userId!, section),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["user-perms", userId] }); message.success("Override eliminado — vuelve al permiso del rol"); },
    onError: () => message.error("Error al eliminar"),
  });

  const rows = (perms as UserPermissionEntry[]).map((p) => ({
    key: p.section,
    label: SECTION_LABELS[p.section] ?? p.section,
    ...p,
  }));

  const overrideCount = rows.filter((r) => r.is_override).length;

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
        <Select
          placeholder="Seleccionar usuario"
          style={{ width: 260 }}
          value={userId}
          onChange={setUserId}
          options={nonAdmins.map((u) => ({
            value: u.id,
            label: (
              <Space>
                <Avatar size="small" icon={<UserOutlined />} />
                <span>{u.username}</span>
                <Tag>{ROLE_LABELS[u.role] ?? u.role}</Tag>
              </Space>
            ),
          }))}
          optionLabelProp="label"
        />
        {selectedUser && (
          <Text type="secondary" style={{ fontSize: 13 }}>
            Rol base: <Tag>{ROLE_LABELS[selectedUser.role] ?? selectedUser.role}</Tag>
            {overrideCount > 0 && (
              <Tag color="blue" style={{ marginLeft: 4 }}>{overrideCount} override{overrideCount > 1 ? "s" : ""}</Tag>
            )}
          </Text>
        )}
      </div>

      {userId == null ? (
        <Alert message="Seleccioná un usuario para ver y editar sus permisos individuales." type="info" showIcon />
      ) : (
        <>
          <Alert
            style={{ marginBottom: 12 }}
            type="info"
            showIcon
            message={
              <span>
                Los permisos sin override heredan los del rol.{" "}
                <Tag color="blue">Override</Tag> indica que el usuario tiene un permiso personalizado que reemplaza al rol.
              </span>
            }
          />
          <Table dataSource={rows} rowKey="section" pagination={false} size="small" loading={isLoading}
            rowClassName={(r) => r.is_override ? "ant-table-row-selected" : ""}
          >
            <Table.Column title="Sección" dataIndex="label"
              render={(label: string, r: typeof rows[0]) => (
                <Space>
                  {label}
                  {r.is_override && <Tag color="blue" style={{ fontSize: 11 }}>Override</Tag>}
                </Space>
              )}
            />
            <Table.Column title="Ver" dataIndex="can_view" width={90}
              render={(val: boolean, r: typeof rows[0]) => (
                <Switch checked={val} size="small"
                  onChange={(checked) => setMut.mutate({ section: r.section, can_view: checked, can_edit: checked ? r.can_edit : false })}
                  loading={setMut.isPending} />
              )}
            />
            <Table.Column title="Editar" dataIndex="can_edit" width={90}
              render={(val: boolean, r: typeof rows[0]) => (
                <Switch checked={val} size="small" disabled={!r.can_view}
                  onChange={(checked) => setMut.mutate({ section: r.section, can_view: r.can_view, can_edit: checked })}
                  loading={setMut.isPending} />
              )}
            />
            <Table.Column title="" width={60}
              render={(_: unknown, r: typeof rows[0]) =>
                r.is_override ? (
                  <Tooltip title="Eliminar override y volver al permiso del rol">
                    <Popconfirm
                      title="¿Eliminar override?"
                      description="El usuario volverá a usar los permisos de su rol."
                      onConfirm={() => delMut.mutate(r.section)}
                      okText="Eliminar"
                      cancelText="Cancelar"
                    >
                      <Button size="small" icon={<UndoOutlined />} type="text" danger />
                    </Popconfirm>
                  </Tooltip>
                ) : null
              }
            />
          </Table>
        </>
      )}
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────

export default function Permissions() {
  const [activeRole, setActiveRole] = useState("operator");

  return (
    <div style={{ maxWidth: 800 }}>
      <div style={{ marginBottom: 20 }}>
        <Title level={4} style={{ margin: 0 }}>Gestión de Permisos</Title>
        <Text type="secondary">
          El rol <Tag color="gold">Admin</Tag> siempre tiene acceso completo. Los overrides por usuario tienen prioridad sobre los permisos del rol.
        </Text>
      </div>

      <Tabs
        defaultActiveKey="roles"
        items={[
          {
            key: "roles",
            label: "Por rol",
            children: (
              <Card>
                <Text type="secondary" style={{ display: "block", marginBottom: 16, fontSize: 13 }}>
                  Permisos base para todos los usuarios de cada rol, salvo que tengan un override individual.
                </Text>
                <Tabs
                  activeKey={activeRole}
                  onChange={setActiveRole}
                  items={Object.entries(ROLE_LABELS).map(([role, label]) => ({
                    key: role,
                    label,
                    children: <RolePermissionsTable role={role} />,
                  }))}
                />
              </Card>
            ),
          },
          {
            key: "users",
            label: "Por usuario",
            children: (
              <Card>
                <Text type="secondary" style={{ display: "block", marginBottom: 16, fontSize: 13 }}>
                  Configurá permisos individuales para un usuario específico. Sobreescriben los permisos de su rol.
                </Text>
                <UserPermissionsPanel />
              </Card>
            ),
          },
        ]}
      />
    </div>
  );
}

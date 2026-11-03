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

// Order and grouping of the sections shown in the tables. "users" is left out:
// user management is always admin-only.
const SECTION_GROUPS: { group: string; sections: [string, string][] }[] = [
  { group: "Clientes y servicio", sections: [
    ["clients", "Clientes"],
    ["plans", "Planes de internet"],
    ["zones", "Zonas"],
  ] },
  { group: "Facturación y finanzas", sections: [
    ["billing", "Facturación, pagos y avisos de cobro"],
    ["expenses", "Gastos"],
    ["reports", "Reportes"],
  ] },
  { group: "Red", sections: [
    ["routers", "Routers y Gestión WAN"],
    ["firewall", "Firewall & QoS"],
    ["ubiquiti", "Ubiquiti"],
    ["monitoring", "Monitoreo"],
    ["alarms", "Alarmas de red"],
    ["map", "Mapa de Red"],
    ["ip_pool", "Pool de IPs"],
    ["bandwidth", "Ancho de Banda"],
  ] },
  { group: "Soporte y campo", sections: [
    ["tickets", "Soporte (tickets)"],
    ["work_orders", "Órdenes de trabajo"],
    ["inventory", "Inventario"],
  ] },
  { group: "Seguridad", sections: [
    ["security_alerts", "Central de monitoreo y alertas"],
    ["security_subscriptions", "Abonados (PINs, vacaciones, reportes, horario)"],
    ["security_properties", "Propiedades"],
    ["security_members", "Miembros"],
    ["security_plans", "Planes de seguridad"],
    ["security_contracts", "Contratos"],
    ["security_devices", "Dispositivos y zonas"],
    ["security_entry_sessions", "Entrada segura"],
    ["security_events", "Historial de eventos"],
    ["security_neighborhood", "Grupos vecinales"],
    ["security_settings", "Configuración de seguridad"],
  ] },
  { group: "Administración", sections: [
    ["audit", "Auditoría"],
  ] },
];

// Sensitive actions: one "allowed" switch each, checked on top of "Editar" of
// their section (stored as can_view = can_edit = allowed).
const ACTIONS: [string, string, string][] = [
  ["act_client_service", "Cortar, reactivar o dar de baja el servicio", "Clientes"],
  ["act_client_delete", "Borrar clientes", "Clientes"],
  ["act_payments", "Registrar pagos o marcar facturas como pagadas", "Facturación"],
  ["act_invoice_afip", "Emitir factura electrónica (AFIP)", "Facturación"],
  ["act_billing_bulk", "Acciones masivas: generar facturas del mes, marcar vencidas, corte masivo, recordatorios", "Facturación"],
  ["act_export", "Exportar datos (CSV)", "Facturación"],
  ["act_device_ssh", "SSH y actualización de firmware en Ubiquiti", "Ubiquiti"],
  ["act_alert_close", "Resolver alertas o marcarlas como falsa alarma", "Seguridad · Central"],
  ["act_security_pins", "Cambiar PINs y palabra segura de abonados", "Seguridad · Abonados"],
  ["act_access_links", "Generar enlaces del portal y de Telegram", "Seguridad · Abonados y Miembros"],
];

function ActionsHelp() {
  return (
    <Text type="secondary" style={{ display: "block", margin: "24px 0 8px", fontSize: 13 }}>
      <b>Acciones sensibles.</b> Además de «Editar» en la sección indicada, el usuario necesita tener habilitada la acción.
    </Text>
  );
}

const SECTION_LABELS: Record<string, string> = Object.fromEntries(SECTION_GROUPS.flatMap((g) => g.sections));
const SECTION_GROUP: Record<string, string> = Object.fromEntries(
  SECTION_GROUPS.flatMap((g) => g.sections.map(([key]) => [key, g.group])),
);
const SECTION_ORDER: string[] = SECTION_GROUPS.flatMap((g) => g.sections.map(([key]) => key));

/** "Módulo" column: the group name spans its rows (rows must be in SECTION_ORDER). */
function groupColumn<T extends { section: string }>(rows: T[]) {
  return (
    <Table.Column<T>
      title="Módulo"
      key="group"
      width={170}
      render={(_: unknown, r: T) => <Text strong>{SECTION_GROUP[r.section]}</Text>}
      onCell={(r: T, index?: number) => {
        const i = index ?? 0;
        if (i > 0 && SECTION_GROUP[rows[i - 1].section] === SECTION_GROUP[r.section]) return { rowSpan: 0 };
        let span = 1;
        while (i + span < rows.length && SECTION_GROUP[rows[i + span].section] === SECTION_GROUP[r.section]) span++;
        return { rowSpan: span, style: { verticalAlign: "top" } };
      }}
    />
  );
}

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
  const rows = SECTION_ORDER.map((section) => ({
    key: section, section, label: SECTION_LABELS[section],
    can_view: bySection[section]?.can_view ?? false,
    can_edit: bySection[section]?.can_edit ?? false,
  }));

  const actionRows = ACTIONS.map(([section, label, where]) => ({
    key: section, section, label, where, allowed: bySection[section]?.can_view ?? false,
  }));

  return (
    <>
    <Table dataSource={rows} rowKey="section" pagination={false} size="small" loading={isLoading} bordered>
      {groupColumn(rows)}
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
    <ActionsHelp />
    <Table dataSource={actionRows} rowKey="section" pagination={false} size="small" loading={isLoading} bordered>
      <Table.Column title="Acción" dataIndex="label" />
      <Table.Column title="Requiere editar" dataIndex="where" width={210} render={(v: string) => <Text type="secondary">{v}</Text>} />
      <Table.Column title="Permitida" dataIndex="allowed" width={100}
        render={(val: boolean, row: typeof actionRows[0]) => (
          <Switch checked={val} size="small"
            onChange={(checked) => mutation.mutate({ section: row.section, can_view: checked, can_edit: checked })}
            loading={mutation.isPending} />
        )}
      />
    </Table>
    </>
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

  const rows = (perms as UserPermissionEntry[])
    .filter((p) => p.section in SECTION_LABELS)
    .sort((a, b) => SECTION_ORDER.indexOf(a.section) - SECTION_ORDER.indexOf(b.section))
    .map((p) => ({ key: p.section, label: SECTION_LABELS[p.section], ...p }));

  const byKey = Object.fromEntries((perms as UserPermissionEntry[]).map((p) => [p.section, p]));
  const actionRows = ACTIONS.filter(([k]) => byKey[k]).map(([section, label, where]) => ({
    key: section, section, label, where, allowed: byKey[section].can_view, is_override: byKey[section].is_override,
  }));
  const overrideCount = rows.filter((r) => r.is_override).length + actionRows.filter((r) => r.is_override).length;

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
            rowClassName={(r) => r.is_override ? "ant-table-row-selected" : ""} bordered
          >
            {groupColumn(rows)}
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
          <ActionsHelp />
          <Table dataSource={actionRows} rowKey="section" pagination={false} size="small" loading={isLoading} bordered
            rowClassName={(r) => r.is_override ? "ant-table-row-selected" : ""}
          >
            <Table.Column title="Acción" dataIndex="label"
              render={(label: string, r: typeof actionRows[0]) => (
                <Space>
                  {label}
                  {r.is_override && <Tag color="blue" style={{ fontSize: 11 }}>Override</Tag>}
                </Space>
              )}
            />
            <Table.Column title="Requiere editar" dataIndex="where" width={200} render={(v: string) => <Text type="secondary">{v}</Text>} />
            <Table.Column title="Permitida" dataIndex="allowed" width={90}
              render={(val: boolean, r: typeof actionRows[0]) => (
                <Switch checked={val} size="small"
                  onChange={(checked) => setMut.mutate({ section: r.section, can_view: checked, can_edit: checked })}
                  loading={setMut.isPending} />
              )}
            />
            <Table.Column title="" width={60}
              render={(_: unknown, r: typeof actionRows[0]) =>
                r.is_override ? (
                  <Popconfirm
                    title="¿Eliminar override?"
                    description="Vuelve a usar lo que tenga su rol."
                    onConfirm={() => delMut.mutate(r.section)}
                    okText="Eliminar"
                    cancelText="Cancelar"
                  >
                    <Button size="small" icon={<UndoOutlined />} type="text" danger />
                  </Popconfirm>
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
    <div style={{ maxWidth: 960 }}>
      <div style={{ marginBottom: 20 }}>
        <Title level={4} style={{ margin: 0 }}>Gestión de Permisos</Title>
        <Text type="secondary">
          El rol <Tag color="gold">Admin</Tag> siempre tiene acceso completo. Los overrides por usuario tienen prioridad sobre los permisos del rol.
          {" "}«Ver» permite consultar; «Editar» permite crear, modificar, borrar y ejecutar acciones (cortar, sincronizar, etc.).
          Usuarios, VPN, Automatizaciones y Configuración general son solo para administradores.
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

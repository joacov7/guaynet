import React, { useState } from "react";
import {
  Button,
  Checkbox,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import {
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  RollbackOutlined,
  SendOutlined,
} from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { membersApi, propertiesApi } from "../../services/security/api";
import type { PropertyMember, PropertyMemberRole, TelegramLink } from "../../types/security";
import TelegramLinkModal from "./TelegramLinkModal";

const { Title, Text } = Typography;

const ROLE_LABELS: Record<PropertyMemberRole, string> = {
  owner:    "Propietario",
  family:   "Familia",
  employee: "Empleado",
  trusted:  "Confianza",
};

const ROLE_COLORS: Record<PropertyMemberRole, string> = {
  owner:    "gold",
  family:   "blue",
  employee: "purple",
  trusted:  "cyan",
};

interface MemberFormValues {
  name: string;
  phone?: string;
  email?: string;
  role: PropertyMemberRole;
  can_arm: boolean;
  can_disarm: boolean;
  can_invite: boolean;
  can_view_cameras: boolean;
  notify_on_alarm: boolean;
  notify_on_entry: boolean;
}

const DEFAULT_PERMISSIONS_BY_ROLE: Record<PropertyMemberRole, Partial<MemberFormValues>> = {
  owner:    { can_arm: true,  can_disarm: true,  can_invite: true,  can_view_cameras: true,  notify_on_alarm: true,  notify_on_entry: true },
  family:   { can_arm: true,  can_disarm: true,  can_invite: false, can_view_cameras: false, notify_on_alarm: true,  notify_on_entry: false },
  employee: { can_arm: true,  can_disarm: true,  can_invite: false, can_view_cameras: false, notify_on_alarm: false, notify_on_entry: true },
  trusted:  { can_arm: false, can_disarm: false, can_invite: false, can_view_cameras: false, notify_on_alarm: true,  notify_on_entry: false },
};

export default function SecurityMembers() {
  const [searchParams] = useSearchParams();
  const propertyId = Number(searchParams.get("property_id") ?? 0);
  const navigate = useNavigate();
  const qc = useQueryClient();

  const [showRevoked, setShowRevoked] = useState(false);
  const [modal, setModal] = useState<{ open: boolean; editing?: PropertyMember }>({ open: false });
  const [form] = Form.useForm<MemberFormValues>();
  const [tgLink, setTgLink] = useState<{ link: TelegramLink; who: string } | null>(null);

  const { data: property } = useQuery({
    queryKey: ["security", "properties", propertyId],
    queryFn: () => propertiesApi.get(propertyId),
    enabled: !!propertyId,
  });

  const { data: members = [], isLoading } = useQuery({
    queryKey: ["security", "members", propertyId, showRevoked],
    queryFn: () => membersApi.list(propertyId, showRevoked),
    enabled: !!propertyId,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["security", "members", propertyId] });
  };

  const createMutation = useMutation({
    mutationFn: (values: MemberFormValues) => membersApi.create({ property_id: propertyId, ...values }),
    onSuccess: () => { invalidate(); setModal({ open: false }); message.success("Miembro agregado"); },
    onError: () => message.error("Error al agregar miembro"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, values }: { id: number; values: MemberFormValues }) => membersApi.update(id, values),
    onSuccess: () => { invalidate(); setModal({ open: false }); message.success("Miembro actualizado"); },
    onError: () => message.error("Error al actualizar miembro"),
  });

  const revokeMutation = useMutation({
    mutationFn: (id: number) => membersApi.revoke(id),
    onSuccess: () => { invalidate(); message.success("Miembro revocado"); },
    onError: () => message.error("Error al revocar"),
  });

  const restoreMutation = useMutation({
    mutationFn: (id: number) => membersApi.update(id, { status: "active" } as any),
    onSuccess: () => { invalidate(); message.success("Miembro reactivado"); },
    onError: () => message.error("Error al reactivar"),
  });

  const tgLinkMutation = useMutation({
    mutationFn: (m: PropertyMember) => membersApi.telegramLink(m.id).then((link) => ({ link, who: m.name })),
    onSuccess: setTgLink,
    onError: (e: any) => {
      message.error(e?.response?.data?.detail ?? "No se pudo generar el enlace");
    },
  });

  const tgUnlinkMutation = useMutation({
    mutationFn: (id: number) => membersApi.telegramUnlink(id),
    onSuccess: () => {
      invalidate();
      message.success("Telegram desvinculado");
    },
    onError: () => {
      message.error("No se pudo desvincular");
    },
  });

  const openCreate = () => {
    form.resetFields();
    form.setFieldsValue({ role: "family", ...DEFAULT_PERMISSIONS_BY_ROLE.family });
    setModal({ open: true });
  };

  const openEdit = (m: PropertyMember) => {
    form.setFieldsValue(m as any);
    setModal({ open: true, editing: m });
  };

  const onRoleChange = (role: PropertyMemberRole) => {
    form.setFieldsValue(DEFAULT_PERMISSIONS_BY_ROLE[role]);
  };

  const onSubmit = (values: MemberFormValues) => {
    if (modal.editing) {
      updateMutation.mutate({ id: modal.editing.id, values });
    } else {
      createMutation.mutate(values);
    }
  };

  const boolCol = (title: string, field: keyof PropertyMember) => ({
    title,
    dataIndex: field,
    key: field,
    align: "center" as const,
    width: 80,
    render: (v: boolean) => (
      <Tooltip title={v ? "Sí" : "No"}>
        <span style={{ fontSize: 16 }}>{v ? "✓" : "—"}</span>
      </Tooltip>
    ),
  });

  const columns = [
    {
      title: "Nombre",
      dataIndex: "name",
      key: "name",
      render: (name: string, m: PropertyMember) => (
        <Space direction="vertical" size={0}>
          <Text strong>{name}</Text>
          {m.phone && <Text type="secondary" style={{ fontSize: 12 }}>{m.phone}</Text>}
          {m.email && <Text type="secondary" style={{ fontSize: 12 }}>{m.email}</Text>}
        </Space>
      ),
    },
    {
      title: "Rol",
      dataIndex: "role",
      key: "role",
      render: (role: PropertyMemberRole) => (
        <Tag color={ROLE_COLORS[role]}>{ROLE_LABELS[role]}</Tag>
      ),
    },
    {
      title: "Estado",
      dataIndex: "status",
      key: "status",
      render: (s: string) => (
        <Tag color={s === "active" ? "green" : "default"}>{s === "active" ? "Activo" : "Revocado"}</Tag>
      ),
    },
    boolCol("Armar", "can_arm"),
    boolCol("Desarmar", "can_disarm"),
    boolCol("Invitar", "can_invite"),
    boolCol("Cámaras", "can_view_cameras"),
    boolCol("Alarma", "notify_on_alarm"),
    boolCol("Entrada", "notify_on_entry"),
    {
      title: "Telegram",
      key: "telegram",
      render: (_: any, m: PropertyMember) =>
        m.status !== "active" ? null : m.telegram_linked_at ? (
          <Space size={4}>
            <Tooltip title={`Vinculado el ${new Date(m.telegram_linked_at).toLocaleDateString("es-AR")}`}>
              <Tag color="blue">Vinculado</Tag>
            </Tooltip>
            <Popconfirm
              title="¿Desvincular Telegram?"
              description="Deja de recibir avisos y de usar el bot."
              onConfirm={() => tgUnlinkMutation.mutate(m.id)}
              okText="Desvincular"
              cancelText="Cancelar"
            >
              <Button size="small" type="link">Quitar</Button>
            </Popconfirm>
          </Space>
        ) : (
          <Button
            size="small"
            icon={<SendOutlined />}
            loading={tgLinkMutation.isPending && tgLinkMutation.variables?.id === m.id}
            onClick={() => tgLinkMutation.mutate(m)}
          >
            Enlace
          </Button>
        ),
    },
    {
      title: "",
      key: "actions",
      width: 100,
      render: (_: any, m: PropertyMember) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(m)} />
          {m.status === "active" ? (
            <Popconfirm
              title="¿Revocar acceso?"
              onConfirm={() => revokeMutation.mutate(m.id)}
              okText="Revocar"
              cancelText="Cancelar"
            >
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          ) : (
            <Tooltip title="Reactivar">
              <Button size="small" icon={<RollbackOutlined />} onClick={() => restoreMutation.mutate(m.id)} />
            </Tooltip>
          )}
        </Space>
      ),
    },
  ];

  if (!propertyId) {
    return (
      <div style={{ padding: 24 }}>
        <Text type="warning">No se especificó una propiedad. Accedé desde el panel de suscripciones.</Text>
      </div>
    );
  }

  return (
    <div style={{ padding: 24 }}>
      <Space style={{ marginBottom: 16 }}>
        <Button onClick={() => navigate(-1)}>← Volver</Button>
      </Space>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          Miembros — {property?.name ?? `Propiedad #${propertyId}`}
        </Title>
        <Space>
          <Switch
            size="small"
            checked={showRevoked}
            onChange={setShowRevoked}
            checkedChildren="Con revocados"
            unCheckedChildren="Solo activos"
          />
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            Agregar miembro
          </Button>
        </Space>
      </div>

      <TelegramLinkModal link={tgLink?.link ?? null} who={tgLink?.who ?? ""} onClose={() => setTgLink(null)} />

      <Table
        rowKey="id"
        dataSource={members}
        columns={columns}
        loading={isLoading}
        pagination={{ pageSize: 50 }}
        size="middle"
        scroll={{ x: 900 }}
        rowClassName={(m) => (m.status === "revoked" ? "ant-table-row-disabled" : "")}
      />

      <Modal
        title={modal.editing ? "Editar miembro" : "Nuevo miembro"}
        open={modal.open}
        onCancel={() => setModal({ open: false })}
        onOk={() => form.submit()}
        confirmLoading={createMutation.isPending || updateMutation.isPending}
        okText="Guardar"
        cancelText="Cancelar"
        width={520}
      >
        <Form form={form} layout="vertical" onFinish={onSubmit}>
          <Form.Item name="name" label="Nombre" rules={[{ required: true, message: "Requerido" }]}>
            <Input />
          </Form.Item>
          <Space style={{ width: "100%" }}>
            <Form.Item name="phone" label="Teléfono" style={{ marginBottom: 8, flex: 1 }}>
              <Input placeholder="+54 343..." />
            </Form.Item>
            <Form.Item name="email" label="Email" style={{ marginBottom: 8, flex: 1 }}>
              <Input placeholder="correo@ejemplo.com" />
            </Form.Item>
          </Space>
          <Form.Item name="role" label="Rol" rules={[{ required: true }]}>
            <Select onChange={onRoleChange}>
              {(Object.keys(ROLE_LABELS) as PropertyMemberRole[]).map((r) => (
                <Select.Option key={r} value={r}>{ROLE_LABELS[r]}</Select.Option>
              ))}
            </Select>
          </Form.Item>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 24px" }}>
            <Form.Item name="can_arm" valuePropName="checked" style={{ marginBottom: 8 }}>
              <Checkbox>Puede armar</Checkbox>
            </Form.Item>
            <Form.Item name="can_disarm" valuePropName="checked" style={{ marginBottom: 8 }}>
              <Checkbox>Puede desarmar</Checkbox>
            </Form.Item>
            <Form.Item name="can_invite" valuePropName="checked" style={{ marginBottom: 8 }}>
              <Checkbox>Puede invitar</Checkbox>
            </Form.Item>
            <Form.Item name="can_view_cameras" valuePropName="checked" style={{ marginBottom: 8 }}>
              <Checkbox>Ver cámaras</Checkbox>
            </Form.Item>
            <Form.Item name="notify_on_alarm" valuePropName="checked" style={{ marginBottom: 8 }}>
              <Checkbox>Notificar en alarma</Checkbox>
            </Form.Item>
            <Form.Item name="notify_on_entry" valuePropName="checked" style={{ marginBottom: 8 }}>
              <Checkbox>Notificar en entrada</Checkbox>
            </Form.Item>
          </div>
        </Form>
      </Modal>
    </div>
  );
}

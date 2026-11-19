import React, { useState } from "react";
import {
  Button,
  Form,
  Input,
  Modal,
  Popconfirm,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import {
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  TeamOutlined,
  UserAddOutlined,
} from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { neighborhoodApi, subscriptionsApi } from "../../services/security/api";
import type { NeighborhoodGroup, NeighborhoodMembership, SecuritySubscription } from "../../types/security";

const { Title } = Typography;

interface GroupFormValues {
  name: string;
  telegram_group_id: string;
  description?: string;
}

export default function SecurityNeighborhood() {
  const qc = useQueryClient();
  const [groupModal, setGroupModal] = useState<{ open: boolean; editing?: NeighborhoodGroup }>({ open: false });
  const [membersModal, setMembersModal] = useState<NeighborhoodGroup | null>(null);
  const [groupForm] = Form.useForm<GroupFormValues>();
  const [addSubId, setAddSubId] = useState<string>("");

  const { data: groups = [], isLoading } = useQuery({
    queryKey: ["security", "neighborhood-groups"],
    queryFn: neighborhoodApi.list,
  });

  const { data: subscriptions = [] } = useQuery<SecuritySubscription[]>({
    queryKey: ["security", "subscriptions"],
    queryFn: subscriptionsApi.list,
  });

  const { data: members = [] } = useQuery<NeighborhoodMembership[]>({
    queryKey: ["security", "neighborhood-members", membersModal?.id],
    queryFn: () => neighborhoodApi.listMembers(membersModal!.id),
    enabled: !!membersModal,
  });

  const createMutation = useMutation({
    mutationFn: (values: GroupFormValues) => neighborhoodApi.create(values),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["security", "neighborhood-groups"] }); setGroupModal({ open: false }); message.success("Grupo creado"); },
    onError: () => message.error("Error al crear grupo"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, values }: { id: number; values: GroupFormValues }) => neighborhoodApi.update(id, values),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["security", "neighborhood-groups"] }); setGroupModal({ open: false }); message.success("Grupo actualizado"); },
    onError: () => message.error("Error al actualizar grupo"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => neighborhoodApi.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["security", "neighborhood-groups"] }); message.success("Grupo eliminado"); },
    onError: () => message.error("Error al eliminar grupo"),
  });

  const addMemberMutation = useMutation({
    mutationFn: ({ groupId, subId }: { groupId: number; subId: number }) =>
      neighborhoodApi.addMember(groupId, subId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["security", "neighborhood-members", membersModal?.id] });
      qc.invalidateQueries({ queryKey: ["security", "neighborhood-groups"] });
      setAddSubId("");
      message.success("Suscripción agregada");
    },
    onError: (e: any) => message.error(e?.response?.data?.detail ?? "Error al agregar miembro"),
  });

  const removeMemberMutation = useMutation({
    mutationFn: ({ groupId, subId }: { groupId: number; subId: number }) =>
      neighborhoodApi.removeMember(groupId, subId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["security", "neighborhood-members", membersModal?.id] });
      qc.invalidateQueries({ queryKey: ["security", "neighborhood-groups"] });
      message.success("Miembro removido");
    },
    onError: () => message.error("Error al remover miembro"),
  });

  const openCreate = () => {
    groupForm.resetFields();
    setGroupModal({ open: true });
  };

  const openEdit = (g: NeighborhoodGroup) => {
    groupForm.setFieldsValue({ name: g.name, telegram_group_id: g.telegram_group_id, description: g.description });
    setGroupModal({ open: true, editing: g });
  };

  const onGroupSubmit = async (values: GroupFormValues) => {
    if (groupModal.editing) {
      updateMutation.mutate({ id: groupModal.editing.id, values });
    } else {
      createMutation.mutate(values);
    }
  };

  const subMap = new Map(subscriptions.map((s) => [s.id, s]));

  const columns = [
    { title: "Nombre", dataIndex: "name", key: "name" },
    {
      title: "Chat ID Telegram",
      dataIndex: "telegram_group_id",
      key: "telegram_group_id",
      render: (v: string) => <code>{v}</code>,
    },
    { title: "Descripción", dataIndex: "description", key: "description", render: (v?: string) => v ?? "-" },
    {
      title: "Miembros",
      dataIndex: "member_count",
      key: "member_count",
      render: (v: number) => <Tag icon={<TeamOutlined />}>{v}</Tag>,
    },
    {
      title: "Acciones",
      key: "actions",
      render: (_: any, record: NeighborhoodGroup) => (
        <Space>
          <Button size="small" icon={<TeamOutlined />} onClick={() => setMembersModal(record)}>
            Miembros
          </Button>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
            Editar
          </Button>
          <Popconfirm
            title="¿Eliminar este grupo?"
            description="Se eliminarán todas las membresías."
            onConfirm={() => deleteMutation.mutate(record.id)}
            okText="Eliminar"
            cancelText="Cancelar"
          >
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const memberColumns = [
    {
      title: "Suscripción",
      dataIndex: "subscription_id",
      key: "subscription_id",
      render: (id: number) => {
        const sub = subMap.get(id);
        return sub ? `#${id} — ${sub.beat_account_id ?? "sin cuenta BEAT"}` : `#${id}`;
      },
    },
    {
      title: "",
      key: "remove",
      render: (_: any, m: NeighborhoodMembership) => (
        <Popconfirm
          title="¿Remover de este grupo?"
          onConfirm={() => removeMemberMutation.mutate({ groupId: m.group_id, subId: m.subscription_id })}
          okText="Remover"
          cancelText="Cancelar"
        >
          <Button size="small" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>Grupos Vecinales</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          Nuevo grupo
        </Button>
      </div>

      <Table
        rowKey="id"
        dataSource={groups}
        columns={columns}
        loading={isLoading}
        pagination={{ pageSize: 25 }}
        size="middle"
      />

      {/* Create/Edit modal */}
      <Modal
        title={groupModal.editing ? "Editar grupo" : "Nuevo grupo vecinal"}
        open={groupModal.open}
        onCancel={() => setGroupModal({ open: false })}
        onOk={() => groupForm.submit()}
        confirmLoading={createMutation.isPending || updateMutation.isPending}
        okText="Guardar"
        cancelText="Cancelar"
      >
        <Form form={groupForm} layout="vertical" onFinish={onGroupSubmit}>
          <Form.Item name="name" label="Nombre del barrio" rules={[{ required: true, message: "Requerido" }]}>
            <Input placeholder="Barrio Los Naranjos" />
          </Form.Item>
          <Form.Item
            name="telegram_group_id"
            label="Chat ID de Telegram"
            rules={[{ required: true, message: "Requerido" }]}
            extra="ID numérico del grupo (ej: -1001234567890). El bot debe ser miembro del grupo."
          >
            <Input placeholder="-1001234567890" />
          </Form.Item>
          <Form.Item name="description" label="Descripción">
            <Input.TextArea rows={2} placeholder="Descripción opcional" />
          </Form.Item>
        </Form>
      </Modal>

      {/* Members modal */}
      <Modal
        title={`Miembros — ${membersModal?.name}`}
        open={!!membersModal}
        onCancel={() => setMembersModal(null)}
        footer={null}
        width={600}
      >
        <div style={{ marginBottom: 12, display: "flex", gap: 8 }}>
          <Input
            placeholder="ID de suscripción"
            value={addSubId}
            onChange={(e) => setAddSubId(e.target.value)}
            style={{ width: 180 }}
          />
          <Button
            type="primary"
            icon={<UserAddOutlined />}
            loading={addMemberMutation.isPending}
            disabled={!addSubId.trim()}
            onClick={() => {
              const id = parseInt(addSubId, 10);
              if (!isNaN(id) && membersModal) {
                addMemberMutation.mutate({ groupId: membersModal.id, subId: id });
              }
            }}
          >
            Agregar
          </Button>
        </div>
        <Table
          rowKey="id"
          dataSource={members}
          columns={memberColumns}
          size="small"
          pagination={false}
        />
      </Modal>
    </div>
  );
}

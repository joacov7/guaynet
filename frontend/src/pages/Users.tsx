import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Button, Form, Input, Modal, Select, Space, Switch, Table, Tag, Typography, message,
} from "antd";
import { PlusOutlined, EditOutlined } from "@ant-design/icons";
import { usersApi } from "@/services/api";
import type { User } from "@/types";

const { Title } = Typography;

const ROLE_COLOR: Record<string, string> = {
  admin: "red",
  operator: "blue",
  technician: "green",
};

const ROLE_LABEL: Record<string, string> = {
  admin: "Admin",
  operator: "Operador",
  technician: "Técnico",
};

interface FormValues {
  username: string;
  email: string;
  full_name: string;
  role: string;
  password?: string;
  is_active?: boolean;
}

export default function Users() {
  const qc = useQueryClient();
  const [form] = Form.useForm<FormValues>();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<User | null>(null);

  const { data = [], isLoading } = useQuery({
    queryKey: ["users"],
    queryFn: usersApi.list,
  });

  const createMutation = useMutation({
    mutationFn: (v: FormValues) =>
      usersApi.create({
        username: v.username,
        email: v.email,
        full_name: v.full_name || "",
        password: v.password!,
        role: v.role,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      message.success("Usuario creado");
      setOpen(false);
      form.resetFields();
    },
    onError: (e: any) => message.error(e.response?.data?.detail ?? "Error al crear usuario"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, values }: { id: number; values: FormValues }) =>
      usersApi.update(id, {
        email: values.email,
        full_name: values.full_name,
        role: values.role,
        is_active: values.is_active,
        ...(values.password ? { password: values.password } : {}),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      message.success("Usuario actualizado");
      setOpen(false);
      setEditing(null);
      form.resetFields();
    },
    onError: () => message.error("Error al actualizar"),
  });

  function openCreate() {
    setEditing(null);
    form.resetFields();
    setOpen(true);
  }

  function openEdit(user: User) {
    setEditing(user);
    form.setFieldsValue({
      username: user.username,
      email: user.email,
      full_name: user.full_name,
      role: user.role,
      is_active: user.is_active,
      password: "",
    });
    setOpen(true);
  }

  function handleOk() {
    form.validateFields().then((values) => {
      if (editing) {
        updateMutation.mutate({ id: editing.id, values });
      } else {
        createMutation.mutate(values);
      }
    });
  }

  const isPending = createMutation.isPending || updateMutation.isPending;

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>Usuarios del sistema</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          Nuevo usuario
        </Button>
      </div>

      <Table dataSource={data} rowKey="id" loading={isLoading} size="small">
        <Table.Column title="Usuario" dataIndex="username" />
        <Table.Column title="Nombre completo" dataIndex="full_name" />
        <Table.Column title="Email" dataIndex="email" />
        <Table.Column
          title="Rol"
          dataIndex="role"
          render={(role: string) => (
            <Tag color={ROLE_COLOR[role] ?? "default"}>{ROLE_LABEL[role] ?? role}</Tag>
          )}
        />
        <Table.Column
          title="Estado"
          dataIndex="is_active"
          render={(active: boolean) =>
            active ? <Tag color="green">Activo</Tag> : <Tag color="red">Inactivo</Tag>
          }
        />
        <Table.Column
          title="Acciones"
          render={(_: unknown, user: User) => (
            <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(user)}>
              Editar
            </Button>
          )}
        />
      </Table>

      <Modal
        title={editing ? "Editar usuario" : "Nuevo usuario"}
        open={open}
        onOk={handleOk}
        onCancel={() => { setOpen(false); setEditing(null); form.resetFields(); }}
        okText={editing ? "Guardar" : "Crear"}
        confirmLoading={isPending}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="username" label="Usuario" rules={[{ required: !editing }]}>
            <Input disabled={!!editing} />
          </Form.Item>
          <Form.Item name="full_name" label="Nombre completo">
            <Input />
          </Form.Item>
          <Form.Item name="email" label="Email" rules={[{ required: true, type: "email" }]}>
            <Input />
          </Form.Item>
          <Form.Item name="role" label="Rol" rules={[{ required: true }]}>
            <Select
              options={[
                { value: "admin", label: "Admin" },
                { value: "operator", label: "Operador" },
                { value: "technician", label: "Técnico" },
              ]}
            />
          </Form.Item>
          <Form.Item
            name="password"
            label={editing ? "Nueva contraseña (dejar vacío para no cambiar)" : "Contraseña"}
            rules={editing ? [] : [{ required: true, min: 6 }]}
          >
            <Input.Password />
          </Form.Item>
          {editing && (
            <Form.Item name="is_active" label="Activo" valuePropName="checked">
              <Switch />
            </Form.Item>
          )}
        </Form>
      </Modal>
    </div>
  );
}

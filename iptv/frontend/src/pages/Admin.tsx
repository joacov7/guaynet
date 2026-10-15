import { useState } from "react";
import {
  Tabs, Table, Button, Modal, Form, Input, InputNumber, Switch,
  Space, Popconfirm, message, Upload, Tag, Typography, Select,
  Card, Statistic, Row, Col,
} from "antd";
import {
  PlusOutlined, EditOutlined, DeleteOutlined, ImportOutlined,
  UploadOutlined, ReloadOutlined, CopyOutlined,
} from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { UploadFile } from "antd/es/upload";
import { adminApi, Channel, Category, User } from "../services/api";

const { Text } = Typography;

function CategoriesTab() {
  const qc = useQueryClient();
  const [form] = Form.useForm();
  const [editing, setEditing] = useState<Category | null>(null);
  const [open, setOpen] = useState(false);

  const { data = [] } = useQuery({ queryKey: ["admin-categories"], queryFn: () => adminApi.listCategories().then(r => r.data) });

  const save = useMutation({
    mutationFn: (v: Partial<Category>) => editing ? adminApi.updateCategory(editing.id, v) : adminApi.createCategory(v),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["admin-categories"] }); setOpen(false); form.resetFields(); },
    onError: () => message.error("Error al guardar"),
  });

  const del = useMutation({
    mutationFn: adminApi.deleteCategory,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-categories"] }),
    onError: () => message.error("Error al eliminar"),
  });

  function openEdit(cat?: Category) {
    setEditing(cat ?? null);
    form.setFieldsValue(cat ?? { name: "", icon: "", order: 0 });
    setOpen(true);
  }

  return (
    <>
      <Button type="primary" icon={<PlusOutlined />} onClick={() => openEdit()} style={{ marginBottom: 12 }}>
        Nueva categoría
      </Button>
      <Table dataSource={data} rowKey="id" size="small" pagination={false}>
        <Table.Column title="Orden" dataIndex="order" width={80} />
        <Table.Column title="Nombre" dataIndex="name" />
        <Table.Column title="Ícono" dataIndex="icon" width={80} />
        <Table.Column title="Acciones" width={120} render={(_: unknown, row: Category) => (
          <Space>
            <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(row)} />
            <Popconfirm title="¿Eliminar?" onConfirm={() => del.mutate(row.id)}>
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          </Space>
        )} />
      </Table>
      <Modal title={editing ? "Editar categoría" : "Nueva categoría"} open={open} onCancel={() => setOpen(false)}
        onOk={() => form.validateFields().then(save.mutate)} confirmLoading={save.isPending}>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="Nombre" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="icon" label="Ícono"><Input /></Form.Item>
          <Form.Item name="order" label="Orden"><InputNumber style={{ width: "100%" }} /></Form.Item>
        </Form>
      </Modal>
    </>
  );
}

function ChannelsTab() {
  const qc = useQueryClient();
  const [form] = Form.useForm();
  const [editing, setEditing] = useState<Channel | null>(null);
  const [open, setOpen] = useState(false);

  const { data: channels = [] } = useQuery({ queryKey: ["admin-channels"], queryFn: () => adminApi.listChannels().then(r => r.data) });
  const { data: cats = [] } = useQuery({ queryKey: ["admin-categories"], queryFn: () => adminApi.listCategories().then(r => r.data) });

  const catOptions = cats.map((c: Category) => ({ value: c.id, label: c.name }));

  const save = useMutation({
    mutationFn: (v: Partial<Channel>) => editing ? adminApi.updateChannel(editing.id, v) : adminApi.createChannel(v),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["admin-channels"] }); setOpen(false); form.resetFields(); },
    onError: () => message.error("Error al guardar"),
  });

  const del = useMutation({
    mutationFn: adminApi.deleteChannel,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-channels"] }),
  });

  function openEdit(ch?: Channel) {
    setEditing(ch ?? null);
    form.setFieldsValue(ch ?? { name: "", stream_url: "", logo_url: "", is_active: true, order: 0 });
    setOpen(true);
  }

  return (
    <>
      <Button type="primary" icon={<PlusOutlined />} onClick={() => openEdit()} style={{ marginBottom: 12 }}>
        Nuevo canal
      </Button>
      <Table dataSource={channels} rowKey="id" size="small" scroll={{ y: 500 }}>
        <Table.Column title="Orden" dataIndex="order" width={70} />
        <Table.Column title="Nombre" dataIndex="name" />
        <Table.Column title="Categoría" dataIndex="category_id" width={140}
          render={(id: number) => cats.find((c: Category) => c.id === id)?.name ?? "-"} />
        <Table.Column title="Activo" dataIndex="is_active" width={80} render={(v: boolean) => <Tag color={v ? "green" : "red"}>{v ? "Sí" : "No"}</Tag>} />
        <Table.Column title="Acciones" width={120} render={(_: unknown, row: Channel) => (
          <Space>
            <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(row)} />
            <Popconfirm title="¿Eliminar?" onConfirm={() => del.mutate(row.id)}>
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          </Space>
        )} />
      </Table>
      <Modal title={editing ? "Editar canal" : "Nuevo canal"} open={open} onCancel={() => setOpen(false)}
        onOk={() => form.validateFields().then(save.mutate)} confirmLoading={save.isPending}>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="Nombre" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="stream_url" label="URL del stream" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="logo_url" label="Logo URL"><Input /></Form.Item>
          <Form.Item name="category_id" label="Categoría"><Select options={catOptions} allowClear /></Form.Item>
          <Form.Item name="order" label="Orden"><InputNumber style={{ width: "100%" }} /></Form.Item>
          <Form.Item name="is_active" label="Activo" valuePropName="checked"><Switch /></Form.Item>
        </Form>
      </Modal>
    </>
  );
}

function ImportTab() {
  const qc = useQueryClient();
  const [urlValue, setUrlValue] = useState("");
  const [fileList, setFileList] = useState<UploadFile[]>([]);

  const importUrl = useMutation({
    mutationFn: () => adminApi.importFromUrl(urlValue),
    onSuccess: (r) => {
      message.success(`Importados ${r.data.imported} canales`);
      qc.invalidateQueries({ queryKey: ["admin-channels"] });
      setUrlValue("");
    },
    onError: () => message.error("Error al importar"),
  });

  const importFile = useMutation({
    mutationFn: (file: File) => adminApi.importFromFile(file),
    onSuccess: (r) => {
      message.success(`Importados ${r.data.imported} canales`);
      qc.invalidateQueries({ queryKey: ["admin-channels"] });
      setFileList([]);
    },
    onError: () => message.error("Error al importar"),
  });

  return (
    <Row gutter={24}>
      <Col xs={24} md={12}>
        <Card title="Importar desde URL" size="small">
          <Space.Compact style={{ width: "100%", marginBottom: 8 }}>
            <Input value={urlValue} onChange={e => setUrlValue(e.target.value)} placeholder="https://..." />
            <Button type="primary" icon={<ImportOutlined />} loading={importUrl.isPending} onClick={() => importUrl.mutate()}>
              Importar
            </Button>
          </Space.Compact>
          <Text type="secondary" style={{ fontSize: 12 }}>Archivo M3U o M3U8 accesible públicamente</Text>
        </Card>
      </Col>
      <Col xs={24} md={12}>
        <Card title="Importar desde archivo" size="small">
          <Upload
            fileList={fileList}
            beforeUpload={(file) => { setFileList([file]); return false; }}
            onRemove={() => setFileList([])}
            accept=".m3u,.m3u8"
          >
            <Button icon={<UploadOutlined />}>Seleccionar archivo</Button>
          </Upload>
          <Button
            type="primary" icon={<ImportOutlined />} style={{ marginTop: 8 }}
            loading={importFile.isPending}
            disabled={fileList.length === 0}
            onClick={() => fileList[0] && importFile.mutate(fileList[0] as unknown as File)}
          >
            Importar
          </Button>
        </Card>
      </Col>
    </Row>
  );
}

function UsersTab() {
  const qc = useQueryClient();
  const [form] = Form.useForm();
  const [editing, setEditing] = useState<User | null>(null);
  const [open, setOpen] = useState(false);

  const { data = [] } = useQuery({ queryKey: ["admin-users"], queryFn: () => adminApi.listUsers().then(r => r.data) });

  const save = useMutation({
    mutationFn: (v: Partial<User> & { password?: string }) =>
      editing ? adminApi.updateUser(editing.id, v) : adminApi.createUser(v),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["admin-users"] }); setOpen(false); form.resetFields(); },
    onError: () => message.error("Error al guardar"),
  });

  const del = useMutation({
    mutationFn: adminApi.deleteUser,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  const regen = useMutation({
    mutationFn: adminApi.regenCode,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["admin-users"] }); message.success("Código regenerado"); },
  });

  function openCreate() {
    setEditing(null);
    form.resetFields();
    setOpen(true);
  }

  return (
    <>
      <Button type="primary" icon={<PlusOutlined />} onClick={openCreate} style={{ marginBottom: 12 }}>
        Nuevo usuario
      </Button>
      <Table dataSource={data} rowKey="id" size="small">
        <Table.Column title="Usuario" dataIndex="username" />
        <Table.Column title="Rol" dataIndex="role" render={(v: string) => <Tag color={v === "admin" ? "gold" : "blue"}>{v}</Tag>} />
        <Table.Column title="Activo" dataIndex="is_active" render={(v: boolean) => <Tag color={v ? "green" : "red"}>{v ? "Sí" : "No"}</Tag>} />
        <Table.Column title="Código de acceso" dataIndex="access_code" render={(v: string | null) => v ? (
          <Space>
            <Text code>{v}</Text>
            <Button size="small" icon={<CopyOutlined />} onClick={() => { navigator.clipboard.writeText(v); message.success("Copiado"); }} />
          </Space>
        ) : "-"} />
        <Table.Column title="Acciones" width={150} render={(_: unknown, row: User) => (
          <Space>
            <Button size="small" icon={<ReloadOutlined />} onClick={() => regen.mutate(row.id)} title="Regenerar código" />
            <Popconfirm title="¿Eliminar?" onConfirm={() => del.mutate(row.id)}>
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          </Space>
        )} />
      </Table>
      <Modal title="Nuevo usuario" open={open} onCancel={() => setOpen(false)}
        onOk={() => form.validateFields().then(save.mutate)} confirmLoading={save.isPending}>
        <Form form={form} layout="vertical">
          <Form.Item name="username" label="Usuario" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="password" label="Contraseña"><Input.Password /></Form.Item>
          <Form.Item name="role" label="Rol" initialValue="viewer">
            <Select options={[{ value: "admin", label: "Admin" }, { value: "viewer", label: "Viewer" }]} />
          </Form.Item>
          <Form.Item name="is_active" label="Activo" valuePropName="checked" initialValue={true}><Switch /></Form.Item>
        </Form>
      </Modal>
    </>
  );
}

export default function Admin() {
  const { data: channels = [] } = useQuery({ queryKey: ["admin-channels"], queryFn: () => adminApi.listChannels().then(r => r.data) });
  const { data: cats = [] } = useQuery({ queryKey: ["admin-categories"], queryFn: () => adminApi.listCategories().then(r => r.data) });
  const { data: users = [] } = useQuery({ queryKey: ["admin-users"], queryFn: () => adminApi.listUsers().then(r => r.data) });

  const activeChannels = channels.filter((c: Channel) => c.is_active).length;

  return (
    <div style={{ padding: 24 }}>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col xs={12} sm={6}><Card size="small"><Statistic title="Canales" value={channels.length} /></Card></Col>
        <Col xs={12} sm={6}><Card size="small"><Statistic title="Activos" value={activeChannels} valueStyle={{ color: "#52c41a" }} /></Card></Col>
        <Col xs={12} sm={6}><Card size="small"><Statistic title="Categorías" value={cats.length} /></Card></Col>
        <Col xs={12} sm={6}><Card size="small"><Statistic title="Usuarios" value={users.length} /></Card></Col>
      </Row>
      <Tabs
        items={[
          { key: "channels", label: "Canales", children: <ChannelsTab /> },
          { key: "categories", label: "Categorías", children: <CategoriesTab /> },
          { key: "import", label: "Importar M3U", children: <ImportTab /> },
          { key: "users", label: "Usuarios", children: <UsersTab /> },
        ]}
      />
    </div>
  );
}

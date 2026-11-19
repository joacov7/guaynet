import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Badge,
  Button,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import { DeleteOutlined, EditOutlined, PlusOutlined } from "@ant-design/icons";
import { routersApi, zonesApi } from "@/services/api";
import type { Zone } from "@/types";

const { Title } = Typography;

export default function Zones() {
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editZone, setEditZone] = useState<Zone | null>(null);
  const [form] = Form.useForm();

  const { data = [], isLoading } = useQuery({ queryKey: ["zones"], queryFn: zonesApi.list });
  const { data: routers = [] } = useQuery({ queryKey: ["routers"], queryFn: routersApi.list });

  const saveMutation = useMutation({
    mutationFn: (values: Partial<Zone>) =>
      editZone ? zonesApi.update(editZone.id, values) : zonesApi.create(values),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["zones"] });
      message.success(editZone ? "Zona actualizada" : "Zona creada");
      closeModal();
    },
    onError: (err: any) => message.error(err.response?.data?.detail ?? "Error al guardar"),
  });

  const deleteMutation = useMutation({
    mutationFn: zonesApi.delete,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["zones"] });
      message.success("Zona eliminada");
    },
    onError: (err: any) => message.error(err.response?.data?.detail ?? "Error al eliminar"),
  });

  const openCreate = () => {
    setEditZone(null);
    form.resetFields();
    form.setFieldsValue({ color: "#1677ff" });
    setModalOpen(true);
  };

  const openEdit = (zone: Zone) => {
    setEditZone(zone);
    form.setFieldsValue(zone);
    setModalOpen(true);
  };

  const closeModal = () => {
    setModalOpen(false);
    setEditZone(null);
    form.resetFields();
  };

  const columns = [
    {
      title: "Nombre",
      dataIndex: "name",
      key: "name",
      render: (name: string, r: Zone) => (
        <Space>
          <span
            style={{
              display: "inline-block",
              width: 12,
              height: 12,
              borderRadius: "50%",
              background: r.color,
            }}
          />
          {name}
        </Space>
      ),
    },
    { title: "Descripción", dataIndex: "description", key: "description", render: (v: string) => v ?? "—" },
    {
      title: "Router",
      key: "router",
      render: (_: unknown, r: Zone) => {
        const router = routers.find((rt) => rt.id === r.router_id);
        return router ? <Tag>{router.name}</Tag> : "—";
      },
    },
    {
      title: "Clientes",
      dataIndex: "client_count",
      key: "client_count",
      align: "right" as const,
      render: (v: number) => <Badge count={v} showZero color="#1677ff" />,
    },
    {
      title: "",
      key: "actions",
      align: "right" as const,
      render: (_: unknown, r: Zone) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)} />
          <Popconfirm title="¿Eliminar zona?" onConfirm={() => deleteMutation.mutate(r.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>Zonas / NAPs</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          Nueva zona
        </Button>
      </div>

      <Table
        loading={isLoading}
        dataSource={data}
        rowKey="id"
        columns={columns}
        size="small"
        pagination={false}
      />

      <Modal
        title={editZone ? "Editar zona" : "Nueva zona"}
        open={modalOpen}
        onCancel={closeModal}
        onOk={() => form.submit()}
        confirmLoading={saveMutation.isPending}
        width={480}
      >
        <Form form={form} layout="vertical" onFinish={(v) => saveMutation.mutate(v)}>
          <Form.Item name="name" label="Nombre" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="Descripción">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="color" label="Color (hex)" rules={[{ required: true }]}>
            <Input placeholder="#1677ff" maxLength={20} style={{ width: 160 }} />
          </Form.Item>
          <Form.Item name="router_id" label="Router asociado">
            <Select
              allowClear
              placeholder="Sin router"
              options={routers.map((r) => ({
                value: r.id,
                label: r.location ? `${r.name} (${r.location})` : r.name,
              }))}
            />
          </Form.Item>
          <Space style={{ width: "100%" }} size={16}>
            <Form.Item name="latitude" label="Latitud">
              <InputNumber placeholder="-34.6037" step={0.0001} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="longitude" label="Longitud">
              <InputNumber placeholder="-58.3816" step={0.0001} style={{ width: "100%" }} />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
    </div>
  );
}

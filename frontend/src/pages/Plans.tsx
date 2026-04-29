import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import { PlusOutlined, EditOutlined, DeleteOutlined } from "@ant-design/icons";
import { plansApi } from "@/services/api";
import type { Plan } from "@/types";

const { Title } = Typography;

export default function Plans() {
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editPlan, setEditPlan] = useState<Plan | null>(null);
  const [form] = Form.useForm();

  const { data = [], isLoading } = useQuery({ queryKey: ["plans"], queryFn: () => plansApi.list() });

  const saveMutation = useMutation({
    mutationFn: (values: Partial<Plan>) =>
      editPlan ? plansApi.update(editPlan.id, values) : plansApi.create(values),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["plans"] });
      message.success(editPlan ? "Plan actualizado" : "Plan creado");
      closeModal();
    },
    onError: () => message.error("Error al guardar"),
  });

  const deleteMutation = useMutation({
    mutationFn: plansApi.delete,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["plans"] }); message.success("Plan eliminado"); },
    onError: (err: any) => message.error(err.response?.data?.detail ?? "Error al eliminar"),
  });

  const openCreate = () => {
    setEditPlan(null);
    form.resetFields();
    form.setFieldsValue({ is_active: true, burst_time_seconds: 10 });
    setModalOpen(true);
  };

  const openEdit = (plan: Plan) => {
    setEditPlan(plan);
    form.setFieldsValue(plan);
    setModalOpen(true);
  };

  const closeModal = () => {
    setModalOpen(false);
    setEditPlan(null);
    form.resetFields();
  };

  const columns = [
    { title: "Nombre", dataIndex: "name", key: "name" },
    {
      title: "Velocidad (Down/Up)",
      key: "speed",
      render: (_: unknown, r: Plan) => <Tag color="blue">{r.download_mbps}/{r.upload_mbps} Mbps</Tag>,
    },
    {
      title: "Burst",
      key: "burst",
      render: (_: unknown, r: Plan) =>
        r.mikrotik_burst_limit ? <Tag color="geekblue">{r.mikrotik_burst_limit}</Tag> : <Tag>Sin burst</Tag>,
    },
    {
      title: "Precio",
      dataIndex: "price",
      key: "price",
      render: (v: number) =>
        new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS" }).format(v),
    },
    { title: "Clientes", dataIndex: "client_count", key: "client_count", align: "right" as const },
    {
      title: "Activo",
      dataIndex: "is_active",
      key: "is_active",
      render: (v: boolean) => <Tag color={v ? "green" : "default"}>{v ? "Sí" : "No"}</Tag>,
    },
    {
      title: "",
      key: "actions",
      align: "right" as const,
      render: (_: unknown, r: Plan) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)} />
          <Popconfirm title="¿Eliminar plan?" onConfirm={() => deleteMutation.mutate(r.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>Planes</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>Nuevo plan</Button>
      </div>

      <Table loading={isLoading} dataSource={data} rowKey="id" columns={columns} size="small" pagination={false} />

      <Modal
        title={editPlan ? "Editar plan" : "Nuevo plan"}
        open={modalOpen}
        onCancel={closeModal}
        onOk={() => form.submit()}
        confirmLoading={saveMutation.isPending}
        width={560}
      >
        <Form form={form} layout="vertical" onFinish={(v) => saveMutation.mutate(v)}>
          <Form.Item name="name" label="Nombre" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="description" label="Descripción"><Input.TextArea rows={2} /></Form.Item>
          <Space style={{ width: "100%" }} size={16}>
            <Form.Item name="download_mbps" label="Descarga (Mbps)" rules={[{ required: true }]}>
              <InputNumber min={1} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="upload_mbps" label="Subida (Mbps)" rules={[{ required: true }]}>
              <InputNumber min={1} style={{ width: "100%" }} />
            </Form.Item>
          </Space>
          <Title level={5} style={{ marginBottom: 8 }}>Burst (opcional)</Title>
          <Space style={{ width: "100%" }} size={16}>
            <Form.Item name="burst_download_mbps" label="Burst descarga (Mbps)">
              <InputNumber min={1} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="burst_upload_mbps" label="Burst subida (Mbps)">
              <InputNumber min={1} style={{ width: "100%" }} />
            </Form.Item>
          </Space>
          <Space style={{ width: "100%" }} size={16}>
            <Form.Item name="burst_threshold_mbps" label="Umbral burst (Mbps)">
              <InputNumber min={1} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="burst_time_seconds" label="Tiempo burst (seg)">
              <InputNumber min={1} max={120} style={{ width: "100%" }} />
            </Form.Item>
          </Space>
          <Form.Item name="price" label="Precio (ARS)" rules={[{ required: true }]}>
            <InputNumber min={0} precision={2} style={{ width: "100%" }} prefix="$" />
          </Form.Item>
          <Form.Item name="is_active" label="Activo" valuePropName="checked"><Switch /></Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

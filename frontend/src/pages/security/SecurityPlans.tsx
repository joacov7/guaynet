import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Checkbox, Form, Input, InputNumber, Modal, Switch, Table, Tag, Tooltip, Typography, message } from "antd";
import { EditOutlined, PlusOutlined } from "@ant-design/icons";
import { plansApi } from "@/services/security/api";
import type { SecurityFeatureName, SecurityPlan } from "@/types/security";
import { usePermissions } from "@/contexts/PermissionsContext";
import { featureLabels } from "./labels";

const { Title, Text } = Typography;

const money = (v: number) =>
  new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 }).format(v);

export default function SecurityPlans() {
  const qc = useQueryClient();
  const { isAdmin } = usePermissions();
  const [editing, setEditing] = useState<SecurityPlan | "new" | null>(null);
  const [form] = Form.useForm();

  const { data: plans = [], isLoading } = useQuery({
    queryKey: ["security-plans-all"],
    queryFn: () => plansApi.list(false),
  });

  const saveMutation = useMutation({
    mutationFn: (values: any) =>
      editing === "new" ? plansApi.create(values) : plansApi.update((editing as SecurityPlan).id, values),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["security-plans-all"] });
      qc.invalidateQueries({ queryKey: ["security-plans"] });
      message.success("Plan guardado");
      setEditing(null);
      form.resetFields();
    },
    onError: (e: any) => {
      const d = e.response?.data?.detail;
      message.error(Array.isArray(d) ? d[0]?.msg : d ?? "Error al guardar");
    },
  });

  const openEdit = (p: SecurityPlan | "new") => {
    setEditing(p);
    form.resetFields();
    if (p !== "new") form.setFieldsValue({ ...p, default_features: p.default_features ?? [] });
  };

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>Planes de seguridad</Title>
        {isAdmin && (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => openEdit("new")}>
            Nuevo plan
          </Button>
        )}
      </div>

      <Table<SecurityPlan>
        dataSource={plans}
        rowKey="id"
        size="small"
        loading={isLoading}
        pagination={false}
        locale={{ emptyText: "Todavía no hay planes. Creá al menos uno para dar de alta abonados." }}
        columns={[
          { title: "Nombre", dataIndex: "name", key: "name" },
          { title: "Precio mensual", dataIndex: "price", key: "price", render: (v: number) => money(v) },
          {
            title: "Central de monitoreo",
            dataIndex: "includes_monitoring",
            key: "monitoring",
            render: (v: boolean) => (v ? <Tag color="blue">Incluida</Tag> : <Tag>Solo avisos al cliente</Tag>),
          },
          {
            title: "Funcionalidades incluidas",
            dataIndex: "default_features",
            key: "features",
            render: (v?: SecurityFeatureName[]) =>
              v?.length ? <Text>{v.length} de {Object.keys(featureLabels).length}</Text> : <Text type="secondary">Ninguna</Text>,
          },
          {
            title: "Estado",
            dataIndex: "is_active",
            key: "active",
            render: (v: boolean) => (v ? <Tag color="green">Activo</Tag> : <Tag>Inactivo</Tag>),
          },
          {
            title: "",
            key: "actions",
            width: 50,
            render: (_, p) =>
              isAdmin && (
                <Tooltip title="Editar">
                  <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(p)} />
                </Tooltip>
              ),
          },
        ]}
      />

      <Modal
        open={!!editing}
        title={editing === "new" ? "Nuevo plan" : "Editar plan"}
        onCancel={() => setEditing(null)}
        onOk={() => form.submit()}
        okText="Guardar"
        confirmLoading={saveMutation.isPending}
        width={640}
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{ includes_monitoring: false, is_active: true, default_features: [] }}
          onFinish={(v) => saveMutation.mutate(v)}
        >
          <Form.Item name="name" label="Nombre" rules={[{ required: true, message: "Ingresá un nombre" }]}>
            <Input maxLength={100} />
          </Form.Item>
          <Form.Item name="description" label="Descripción">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="price" label="Precio mensual (ARS)" rules={[{ required: true, message: "Ingresá el precio" }]}>
            <InputNumber min={0} step={100} style={{ width: 200 }} />
          </Form.Item>
          <Form.Item
            name="includes_monitoring"
            label="Incluye central de monitoreo"
            valuePropName="checked"
            extra="Si está activo, las alertas van a los operadores. Si no, solo se avisa al cliente."
          >
            <Switch />
          </Form.Item>
          <Form.Item
            name="default_features"
            label="Funcionalidades incluidas"
            extra="Se activan al dar de alta un abonado con este plan. Después se pueden ajustar por abonado. Cambiar el plan no modifica a los abonados existentes."
          >
            <Checkbox.Group
              style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", rowGap: 6 }}
              options={Object.entries(featureLabels).map(([value, label]) => ({ value, label }))}
            />
          </Form.Item>
          <Form.Item name="is_active" label="Activo" valuePropName="checked" extra="Un plan inactivo no se ofrece en altas nuevas.">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

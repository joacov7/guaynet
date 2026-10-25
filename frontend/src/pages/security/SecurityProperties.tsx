import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Form, Input, Modal, Select, Space, Table, Tag, Tooltip, Typography, message } from "antd";
import { EditOutlined, PlusOutlined, SafetyCertificateOutlined } from "@ant-design/icons";
import { clientsApi } from "@/services/api";
import { propertiesApi, subscriptionsApi } from "@/services/security/api";
import type { Property, PropertyType } from "@/types/security";

const { Title, Text } = Typography;

export const PROPERTY_TYPE_LABELS: Record<PropertyType, string> = {
  home: "Vivienda",
  commercial: "Comercio",
  industrial: "Industria",
  other: "Otro",
};

const STATUS_LABEL: Record<string, { label: string; color: string }> = {
  active: { label: "Activo", color: "green" },
  suspended: { label: "Suspendido", color: "orange" },
  pending_install: { label: "Pendiente instalación", color: "blue" },
  cancelled: { label: "Cancelado", color: "default" },
};

export default function SecurityProperties() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [editing, setEditing] = useState<Property | "new" | null>(null);
  const [clientSearch, setClientSearch] = useState("");
  const [form] = Form.useForm();

  const { data: properties = [], isLoading } = useQuery({
    queryKey: ["security-properties"],
    queryFn: () => propertiesApi.list(),
  });
  const { data: subscriptions = [] } = useQuery({
    queryKey: ["security-subscriptions"],
    queryFn: () => subscriptionsApi.list(),
  });
  const { data: clients = [], isFetching: searchingClients } = useQuery({
    queryKey: ["clients-search", clientSearch],
    queryFn: () => clientsApi.list({ search: clientSearch || undefined, limit: 20 }),
    enabled: !!editing,
  });

  // Latest subscription per property (active one first)
  const subByProperty = useMemo(() => {
    const m = new Map<number, (typeof subscriptions)[number]>();
    for (const s of subscriptions) {
      const cur = m.get(s.property_id);
      if (!cur || (s.status === "active" && cur.status !== "active") || (cur.status !== "active" && s.id > cur.id)) {
        m.set(s.property_id, s);
      }
    }
    return m;
  }, [subscriptions]);

  const saveMutation = useMutation({
    mutationFn: (values: any) => {
      const payload = { ...values, internet_client_id: values.internet_client_id ?? null };
      return editing === "new"
        ? propertiesApi.create(payload)
        : propertiesApi.update((editing as Property).id, payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["security-properties"] });
      message.success("Propiedad guardada");
      setEditing(null);
      form.resetFields();
    },
    onError: (e: any) => {
      const d = e.response?.data?.detail;
      message.error(Array.isArray(d) ? d[0]?.msg : d ?? "Error al guardar");
    },
  });

  const openEdit = (p: Property | "new") => {
    setEditing(p);
    setClientSearch("");
    form.resetFields();
    if (p !== "new") form.setFieldsValue(p);
  };

  // Keep the currently linked client visible in the select even if it is not in the search results
  const editingClientId = editing && editing !== "new" ? editing.internet_client_id : undefined;
  const clientOptions = clients.map((c: any) => ({
    value: c.id,
    label: `${c.full_name}${c.ip_address ? ` — ${c.ip_address}` : ""}`,
  }));
  if (editingClientId && !clientOptions.some((o) => o.value === editingClientId)) {
    clientOptions.unshift({ value: editingClientId, label: `Cliente #${editingClientId}` });
  }

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>Propiedades</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => openEdit("new")}>
          Nueva propiedad
        </Button>
      </div>

      <Table<Property>
        dataSource={properties}
        rowKey="id"
        size="small"
        loading={isLoading}
        pagination={{ pageSize: 20 }}
        locale={{ emptyText: "Todavía no hay propiedades. Creá la primera para poder dar de alta un abonado." }}
        columns={[
          { title: "ID", dataIndex: "id", key: "id", width: 60 },
          { title: "Nombre", dataIndex: "name", key: "name" },
          {
            title: "Dirección",
            key: "address",
            render: (_, p) => [p.address, p.city].filter(Boolean).join(", "),
          },
          {
            title: "Tipo",
            dataIndex: "property_type",
            key: "type",
            render: (v: PropertyType) => PROPERTY_TYPE_LABELS[v] ?? v,
          },
          {
            title: "Cliente de internet",
            dataIndex: "internet_client_id",
            key: "client",
            render: (v?: number | null) => (v ? <Tag color="blue">Vinculado (#{v})</Tag> : <Text type="secondary">—</Text>),
          },
          {
            title: "Abonado",
            key: "sub",
            render: (_, p) => {
              const s = subByProperty.get(p.id);
              if (!s) {
                return (
                  <Button size="small" icon={<SafetyCertificateOutlined />} onClick={() => navigate(`/security/subscriptions?new=${p.id}`)}>
                    Dar de alta
                  </Button>
                );
              }
              const st = STATUS_LABEL[s.status] ?? { label: s.status, color: "default" };
              return <Tag color={st.color}>#{s.id} · {st.label}</Tag>;
            },
          },
          {
            title: "",
            key: "actions",
            width: 50,
            render: (_, p) => (
              <Tooltip title="Editar">
                <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(p)} />
              </Tooltip>
            ),
          },
        ]}
      />

      <Modal
        open={!!editing}
        title={editing === "new" ? "Nueva propiedad" : "Editar propiedad"}
        onCancel={() => setEditing(null)}
        onOk={() => form.submit()}
        okText="Guardar"
        confirmLoading={saveMutation.isPending}
      >
        <Form form={form} layout="vertical" initialValues={{ property_type: "home" }} onFinish={(v) => saveMutation.mutate(v)}>
          <Form.Item name="name" label="Nombre" rules={[{ required: true, message: "Ingresá un nombre" }]}>
            <Input placeholder="Ej: Casa Pérez, Ferretería Centro" maxLength={200} />
          </Form.Item>
          <Form.Item name="address" label="Dirección" rules={[{ required: true, message: "Ingresá la dirección" }]}>
            <Input maxLength={500} />
          </Form.Item>
          <Space style={{ display: "flex" }} align="start">
            <Form.Item name="city" label="Localidad" style={{ width: 220 }}>
              <Input maxLength={100} />
            </Form.Item>
            <Form.Item name="property_type" label="Tipo" style={{ width: 200 }}>
              <Select options={Object.entries(PROPERTY_TYPE_LABELS).map(([value, label]) => ({ value, label }))} />
            </Form.Item>
          </Space>
          <Form.Item
            name="internet_client_id"
            label="Cliente de internet (opcional)"
            extra="Si también tiene internet con Guaynet, podrá ver su alarma en el portal sin usar el enlace."
          >
            <Select
              showSearch
              allowClear
              filterOption={false}
              onSearch={setClientSearch}
              loading={searchingClients}
              placeholder="Buscar por nombre, IP o teléfono"
              options={clientOptions}
              notFoundContent={searchingClients ? "Buscando…" : "Sin resultados"}
            />
          </Form.Item>
          <Form.Item name="notes" label="Notas">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

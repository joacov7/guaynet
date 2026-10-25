import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Drawer, Form, Input, Select, Spin, Tag, Typography, message } from "antd";
import dayjs from "dayjs";
import { portalApi } from "@/services/api";

const STATUS_COLOR: Record<string, string> = { open: "blue", in_progress: "orange", resolved: "green", closed: "default" };
const STATUS_LABEL: Record<string, string> = { open: "Abierto", in_progress: "En curso", resolved: "Resuelto", closed: "Cerrado" };
const CATEGORY_OPTIONS = [
  { value: "connectivity", label: "Conectividad" },
  { value: "speed", label: "Velocidad" },
  { value: "billing", label: "Facturación" },
  { value: "equipment", label: "Equipo" },
  { value: "installation", label: "Instalación" },
  { value: "other", label: "Otro" },
];

export default function PortalTickets() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();

  const { data: tickets = [], isLoading, isError, refetch } = useQuery({
    queryKey: ["portal-tickets"],
    queryFn: portalApi.getTickets,
    retry: 2,
  });

  const createMutation = useMutation({
    mutationFn: portalApi.createTicket,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["portal-tickets"] });
      message.success("Ticket enviado");
      setOpen(false);
      form.resetFields();
    },
    onError: () => message.error("No se pudo crear el ticket"),
  });

  if (isLoading) return (
    <div style={{ display: "flex", justifyContent: "center", padding: 60 }}>
      <Spin size="large" />
    </div>
  );

  if (isError) return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: 60, gap: 12 }}>
      <Typography.Text type="secondary">No se pudieron cargar los tickets.</Typography.Text>
      <Button onClick={() => refetch()}>Reintentar</Button>
    </div>
  );

  return (
    <div style={{ padding: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <Typography.Text strong style={{ fontSize: 15 }}>Mis tickets ({tickets.length})</Typography.Text>
        <Button type="primary" size="small" onClick={() => setOpen(true)}>+ Nuevo</Button>
      </div>

      {tickets.length === 0 && (
        <div style={{ textAlign: "center", padding: 40 }}>
          <div style={{ fontSize: 36, marginBottom: 8 }}>🎫</div>
          <Typography.Text type="secondary">No tenés tickets. ¿Necesitás ayuda?</Typography.Text>
        </div>
      )}

      {tickets.map((t: any) => (
        <div
          key={t.id}
          style={{
            background: "#fff", borderRadius: 12, padding: 14,
            marginBottom: 10, boxShadow: "0 1px 4px rgba(0,0,0,.06)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
            <Tag color={STATUS_COLOR[t.status]}>{STATUS_LABEL[t.status]}</Tag>
            <Typography.Text type="secondary" style={{ fontSize: 11 }}>
              #{t.id} · {dayjs(t.created_at).format("DD/MM/YY")}
            </Typography.Text>
          </div>
          <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 2 }}>{t.title}</div>
          {t.description && (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>{t.description}</Typography.Text>
          )}
          {t.comment_count > 0 && (
            <Typography.Text type="secondary" style={{ fontSize: 11, display: "block", marginTop: 4 }}>
              💬 {t.comment_count} comentario{t.comment_count !== 1 ? "s" : ""}
            </Typography.Text>
          )}
        </div>
      ))}

      <Drawer
        title="Nuevo ticket de soporte"
        placement="bottom"
        height={420}
        open={open}
        onClose={() => setOpen(false)}
        styles={{ body: { paddingBottom: 80 } }}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={(values) => createMutation.mutate(values)}
        >
          <Form.Item name="title" label="Título" rules={[{ required: true }]}>
            <Input placeholder="Describe brevemente el problema" />
          </Form.Item>
          <Form.Item name="category" label="Categoría" initialValue="other" rules={[{ required: true }]}>
            <Select options={CATEGORY_OPTIONS} />
          </Form.Item>
          <Form.Item name="description" label="Descripción detallada">
            <Input.TextArea rows={3} placeholder="Más detalles sobre el problema..." />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={createMutation.isPending} block>
            Enviar ticket
          </Button>
        </Form>
      </Drawer>
      <div style={{ height: 16 }} />
    </div>
  );
}

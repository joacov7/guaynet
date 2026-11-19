import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Form,
  Input,
  Modal,
  Popconfirm,
  Space,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import { CheckCircleOutlined, EyeOutlined, FilePdfOutlined, PlusOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { contractsApi } from "@/services/security/api";
import type { ContractAcceptance, ContractTemplate } from "@/types/security";

const { Title, Text, Paragraph } = Typography;

export default function SecurityContracts() {
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [viewing, setViewing] = useState<ContractTemplate | null>(null);
  const [form] = Form.useForm();

  const { data: templates = [], isLoading: loadingTpl } = useQuery({
    queryKey: ["security-contract-templates"],
    queryFn: () => contractsApi.listTemplates(),
  });
  const { data: acceptances = [], isLoading: loadingAcc } = useQuery({
    queryKey: ["security-contract-acceptances"],
    queryFn: () => contractsApi.listAcceptances(),
  });

  const onError = (e: any) => {
    const d = e.response?.data?.detail;
    message.error(Array.isArray(d) ? d[0]?.msg : d ?? "Error");
  };

  const createMutation = useMutation({
    mutationFn: (v: { version: string; title: string; body: string }) => contractsApi.createTemplate(v),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["security-contract-templates"] });
      message.success("Versión creada. Activala para que los clientes puedan firmarla.");
      setCreateOpen(false);
      form.resetFields();
    },
    onError,
  });

  const activateMutation = useMutation({
    mutationFn: (id: number) => contractsApi.activateTemplate(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["security-contract-templates"] });
      message.success("Versión activada");
    },
    onError,
  });

  const download = async (a: ContractAcceptance) => {
    try {
      const blob = await contractsApi.downloadPdf(a.id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `contrato_sub${a.subscription_id}_v${a.version}.pdf`;
      link.click();
      URL.revokeObjectURL(url);
    } catch {
      message.error("No se pudo descargar el PDF");
    }
  };

  const active = templates.find((t) => t.is_active);

  return (
    <div style={{ padding: 24 }}>
      <Title level={3} style={{ marginTop: 0 }}>Contratos</Title>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="Aceptación electrónica"
        description={
          <>
            El cliente lee el contrato en su portal y lo acepta confirmando con el PIN de su alarma.
            Se registra nombre, DNI, fecha, IP y la huella SHA-256 del texto, y se le envía una copia en PDF.
            Es una firma electrónica (Ley 25.506, art. 5), no una «firma digital» con certificador licenciado.
            El texto del contrato es responsabilidad de la empresa: conviene que lo revise un abogado.
          </>
        }
      />

      <Tabs
        items={[
          {
            key: "templates",
            label: "Versiones del contrato",
            children: (
              <>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
                  <Text type="secondary">
                    {active
                      ? <>Vigente: <Text strong>{active.title} — v{active.version}</Text></>
                      : "No hay ninguna versión vigente: los clientes todavía no pueden firmar."}
                  </Text>
                  <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
                    Nueva versión
                  </Button>
                </div>
                <Table
                  dataSource={templates}
                  rowKey="id"
                  size="small"
                  loading={loadingTpl}
                  pagination={false}
                  locale={{ emptyText: "Todavía no se cargó ningún contrato" }}
                  columns={[
                    { title: "Versión", dataIndex: "version", key: "version" },
                    { title: "Título", dataIndex: "title", key: "title" },
                    {
                      title: "Creada",
                      dataIndex: "created_at",
                      key: "created",
                      render: (v: string) => dayjs(v).format("DD/MM/YYYY HH:mm"),
                    },
                    {
                      title: "Estado",
                      dataIndex: "is_active",
                      key: "active",
                      render: (v: boolean) => (v ? <Tag color="green">Vigente</Tag> : <Tag>Inactiva</Tag>),
                    },
                    {
                      title: "",
                      key: "actions",
                      render: (_: unknown, t: ContractTemplate) => (
                        <Space size={4}>
                          <Tooltip title="Ver texto">
                            <Button size="small" icon={<EyeOutlined />} onClick={() => setViewing(t)} />
                          </Tooltip>
                          {!t.is_active && (
                            <Popconfirm
                              title="¿Activar esta versión?"
                              description="Los clientes que no la firmaron la verán como pendiente en su portal."
                              onConfirm={() => activateMutation.mutate(t.id)}
                              okText="Activar"
                              cancelText="Cancelar"
                            >
                              <Button size="small" icon={<CheckCircleOutlined />}>Activar</Button>
                            </Popconfirm>
                          )}
                        </Space>
                      ),
                    },
                  ]}
                />
              </>
            ),
          },
          {
            key: "acceptances",
            label: `Firmas (${acceptances.length})`,
            children: (
              <Table
                dataSource={acceptances}
                rowKey="id"
                size="small"
                loading={loadingAcc}
                pagination={{ pageSize: 20 }}
                locale={{ emptyText: "Ningún cliente firmó todavía" }}
                columns={[
                  { title: "Suscripción", dataIndex: "subscription_id", key: "sub", render: (v: number) => `#${v}` },
                  { title: "Versión", dataIndex: "version", key: "version" },
                  { title: "Firmante", dataIndex: "signer_name", key: "name", render: (v?: string) => v ?? "—" },
                  { title: "DNI", dataIndex: "signer_dni", key: "dni", render: (v?: string) => v ?? "—" },
                  {
                    title: "Fecha",
                    dataIndex: "accepted_at",
                    key: "at",
                    render: (v: string) => dayjs(v).format("DD/MM/YYYY HH:mm"),
                  },
                  { title: "IP", dataIndex: "acceptance_ip", key: "ip", render: (v?: string) => v ?? "—" },
                  {
                    title: "",
                    key: "pdf",
                    render: (_: unknown, a: ContractAcceptance) =>
                      a.has_pdf ? (
                        <Button size="small" icon={<FilePdfOutlined />} onClick={() => download(a)}>PDF</Button>
                      ) : null,
                  },
                ]}
              />
            ),
          },
        ]}
      />

      <Modal
        open={createOpen}
        title="Nueva versión del contrato"
        onCancel={() => setCreateOpen(false)}
        onOk={() => form.submit()}
        okText="Crear"
        confirmLoading={createMutation.isPending}
        width={760}
      >
        <Paragraph type="secondary" style={{ fontSize: 12 }}>
          Una versión no se puede editar después de creada: para cambiar el texto, creá una versión nueva.
          Separá las cláusulas con una línea en blanco.
        </Paragraph>
        <Form form={form} layout="vertical" onFinish={(v) => createMutation.mutate(v)}>
          <Space style={{ display: "flex" }} align="start">
            <Form.Item name="version" label="Versión" rules={[{ required: true }]} style={{ width: 120 }}>
              <Input placeholder="1.0" maxLength={20} />
            </Form.Item>
            <Form.Item name="title" label="Título" rules={[{ required: true }]} style={{ width: 560 }}>
              <Input placeholder="Contrato de servicio de monitoreo de alarmas" maxLength={200} />
            </Form.Item>
          </Space>
          <Form.Item
            name="body"
            label="Texto completo"
            rules={[{ required: true }, { min: 20, message: "El texto es demasiado corto" }]}
          >
            <Input.TextArea rows={16} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        open={!!viewing}
        title={viewing ? `${viewing.title} — v${viewing.version}` : ""}
        onCancel={() => setViewing(null)}
        footer={<Button onClick={() => setViewing(null)}>Cerrar</Button>}
        width={760}
      >
        {viewing && (
          <>
            <div style={{ whiteSpace: "pre-wrap", maxHeight: 480, overflow: "auto", fontSize: 13 }}>
              {viewing.body}
            </div>
            <Text type="secondary" style={{ fontSize: 11, display: "block", marginTop: 12 }}>
              SHA-256: <Text code style={{ fontSize: 11 }}>{viewing.body_hash}</Text>
            </Text>
          </>
        )}
      </Modal>
    </div>
  );
}

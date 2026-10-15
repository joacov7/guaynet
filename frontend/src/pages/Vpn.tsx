import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Col,
  Divider,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Tabs,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import {
  CopyOutlined,
  DeleteOutlined,
  EditOutlined,
  KeyOutlined,
  PlusOutlined,
  CodeOutlined,
} from "@ant-design/icons";
import { vpnApi, routersApi } from "@/services/api";
import type { VpnConnection } from "@/types";

const { Title, Text } = Typography;
const { TextArea } = Input;

function CopyBlock({ text, label }: { text: string; label: string }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
        <Text strong>{label}</Text>
        <Button
          size="small"
          icon={<CopyOutlined />}
          onClick={() => { navigator.clipboard.writeText(text); message.success("Copiado"); }}
        >
          Copiar
        </Button>
      </div>
      <pre
        style={{
          background: "#1e1e1e", color: "#d4d4d4", padding: 12, borderRadius: 6,
          fontSize: 12, overflowX: "auto", margin: 0, whiteSpace: "pre-wrap",
        }}
      >
        {text}
      </pre>
    </div>
  );
}

function CommandsModal({ vpn, onClose }: { vpn: VpnConnection; onClose: () => void }) {
  const { data, isLoading } = useQuery({
    queryKey: ["vpn-commands", vpn.id],
    queryFn: () => vpnApi.commands(vpn.id),
  });

  return (
    <Modal
      title={<><CodeOutlined /> Comandos — {vpn.name}</>}
      open
      onCancel={onClose}
      footer={<Button onClick={onClose}>Cerrar</Button>}
      width={720}
    >
      {isLoading ? (
        <Text>Cargando...</Text>
      ) : data ? (
        <>
          <Alert
            type="info"
            showIcon
            message="Pegá los comandos de MikroTik en la terminal del router. Los del servidor en el host donde corre el VPN."
            style={{ marginBottom: 16 }}
          />
          <CopyBlock text={data.mikrotik} label="Comandos MikroTik (RouterOS)" />
          <Divider />
          <CopyBlock text={data.server} label="Configuración del servidor" />
        </>
      ) : null}
    </Modal>
  );
}

type FormValues = Partial<VpnConnection> & { vpn_type: "wireguard" | "l2tp" };

function VpnForm({
  initial,
  onSave,
  onCancel,
  isPending,
}: {
  initial?: VpnConnection;
  onSave: (v: FormValues) => void;
  onCancel: () => void;
  isPending: boolean;
}) {
  const [form] = Form.useForm<FormValues>();
  const [vpnType, setVpnType] = useState<"wireguard" | "l2tp">(initial?.vpn_type ?? "wireguard");
  const qc = useQueryClient();

  const { data: routers = [] } = useQuery({
    queryKey: ["routers"],
    queryFn: routersApi.list,
  });

  async function fillWgKeys() {
    try {
      const keys = await vpnApi.generateWgKeys();
      form.setFieldsValue({
        wg_client_private_key: keys.private_key,
        wg_client_public_key: keys.public_key,
      });
      message.success("Claves generadas");
    } catch {
      message.error("Error al generar claves");
    }
  }

  async function fillL2tpCreds() {
    try {
      const creds = await vpnApi.generateL2tpCreds();
      form.setFieldsValue({
        l2tp_password: creds.password,
        l2tp_ipsec_secret: creds.ipsec_secret,
      });
      message.success("Credenciales generadas");
    } catch {
      message.error("Error al generar credenciales");
    }
  }

  return (
    <Form
      form={form}
      layout="vertical"
      initialValues={initial ?? { vpn_type: "wireguard", wg_server_port: 51820, wg_keepalive: 25 }}
      onFinish={onSave}
    >
      <Row gutter={16}>
        <Col span={14}>
          <Form.Item name="name" label="Nombre" rules={[{ required: true }]}>
            <Input placeholder="ej: Router Palermo" />
          </Form.Item>
        </Col>
        <Col span={10}>
          <Form.Item name="vpn_type" label="Tipo" rules={[{ required: true }]}>
            <Select
              onChange={(v) => setVpnType(v)}
              options={[
                { value: "wireguard", label: "WireGuard (RouterOS v7)" },
                { value: "l2tp", label: "L2TP/IPsec (RouterOS v6)" },
              ]}
            />
          </Form.Item>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={14}>
          <Form.Item name="router_id" label="Router asociado">
            <Select
              allowClear
              placeholder="Opcional"
              options={routers.map((r) => ({ value: r.id, label: r.name }))}
              onChange={(_, opt: any) => form.setFieldValue("router_name", opt?.label)}
            />
          </Form.Item>
        </Col>
      </Row>

      {vpnType === "wireguard" && (
        <>
          <Divider orientation="left" orientationMargin={0}>WireGuard</Divider>
          <div style={{ marginBottom: 8 }}>
            <Button icon={<KeyOutlined />} size="small" onClick={fillWgKeys}>
              Generar par de claves del cliente
            </Button>
          </div>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="wg_client_private_key" label="Clave privada (cliente)" rules={[{ required: true }]}>
                <Input.Password />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="wg_client_public_key" label="Clave pública (cliente)" rules={[{ required: true }]}>
                <Input />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={16}>
              <Form.Item name="wg_server_endpoint" label="Endpoint del servidor (host/IP)" rules={[{ required: true }]}>
                <Input placeholder="ej: guaynet.duckdns.org" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="wg_server_port" label="Puerto">
                <InputNumber style={{ width: "100%" }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="wg_server_public_key" label="Clave pública del servidor" rules={[{ required: true }]}>
            <Input placeholder="Clave pública del wg0 del servidor" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="wg_client_ip" label="IP del cliente en el túnel" rules={[{ required: true }]}>
                <Input placeholder="ej: 10.99.0.2/32" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="wg_server_wg_ip" label="IP del servidor en el túnel" rules={[{ required: true }]}>
                <Input placeholder="ej: 10.99.0.1/24" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="wg_keepalive" label="Persistent keepalive (seg)">
            <InputNumber style={{ width: 120 }} />
          </Form.Item>
        </>
      )}

      {vpnType === "l2tp" && (
        <>
          <Divider orientation="left" orientationMargin={0}>L2TP/IPsec</Divider>
          <div style={{ marginBottom: 8 }}>
            <Button icon={<KeyOutlined />} size="small" onClick={fillL2tpCreds}>
              Generar usuario y secreto IPsec
            </Button>
          </div>
          <Form.Item name="l2tp_server_host" label="Host del servidor" rules={[{ required: true }]}>
            <Input placeholder="ej: guaynet.duckdns.org" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="l2tp_username" label="Usuario PPP" rules={[{ required: true }]}>
                <Input />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="l2tp_password" label="Contraseña PPP" rules={[{ required: true }]}>
                <Input.Password />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="l2tp_ipsec_secret" label="Secreto IPsec (PSK)" rules={[{ required: true }]}>
            <Input.Password />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="l2tp_local_ip" label="IP local del servidor (túnel)" rules={[{ required: true }]}>
                <Input placeholder="ej: 192.168.99.1" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="l2tp_remote_ip" label="IP asignada al router (túnel)" rules={[{ required: true }]}>
                <Input placeholder="ej: 192.168.99.2" />
              </Form.Item>
            </Col>
          </Row>
        </>
      )}

      <Form.Item name="notes" label="Notas">
        <TextArea rows={2} />
      </Form.Item>

      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
        <Button onClick={onCancel}>Cancelar</Button>
        <Button type="primary" htmlType="submit" loading={isPending}>
          {initial ? "Guardar" : "Crear"}
        </Button>
      </div>
    </Form>
  );
}

function VpnCard({ vpn, onEdit, onDelete, onCommands }: {
  vpn: VpnConnection;
  onEdit: () => void;
  onDelete: () => void;
  onCommands: () => void;
}) {
  const isWg = vpn.vpn_type === "wireguard";
  return (
    <Card
      size="small"
      title={
        <Space>
          <Tag color={isWg ? "blue" : "purple"}>{isWg ? "WireGuard" : "L2TP/IPsec"}</Tag>
          <Text strong>{vpn.name}</Text>
          {vpn.router_name && <Text type="secondary">— {vpn.router_name}</Text>}
        </Space>
      }
      extra={
        <Space>
          <Tooltip title="Ver comandos">
            <Button size="small" icon={<CodeOutlined />} onClick={onCommands} />
          </Tooltip>
          <Tooltip title="Editar">
            <Button size="small" icon={<EditOutlined />} onClick={onEdit} />
          </Tooltip>
          <Popconfirm title="¿Eliminar esta conexión VPN?" onConfirm={onDelete} okText="Sí" cancelText="No">
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      }
      style={{ marginBottom: 12 }}
    >
      {isWg ? (
        <Row gutter={16}>
          <Col><Text type="secondary">Endpoint:</Text> {vpn.wg_server_endpoint}:{vpn.wg_server_port}</Col>
          <Col><Text type="secondary">IP cliente:</Text> {vpn.wg_client_ip}</Col>
          <Col><Text type="secondary">Keepalive:</Text> {vpn.wg_keepalive}s</Col>
        </Row>
      ) : (
        <Row gutter={16}>
          <Col><Text type="secondary">Servidor:</Text> {vpn.l2tp_server_host}</Col>
          <Col><Text type="secondary">Usuario:</Text> {vpn.l2tp_username}</Col>
          <Col><Text type="secondary">IP túnel:</Text> {vpn.l2tp_remote_ip}</Col>
        </Row>
      )}
      {vpn.notes && <div style={{ marginTop: 6 }}><Text type="secondary">{vpn.notes}</Text></div>}
    </Card>
  );
}

export default function Vpn() {
  const qc = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<VpnConnection | null>(null);
  const [commandsFor, setCommandsFor] = useState<VpnConnection | null>(null);
  const [tab, setTab] = useState("wireguard");

  const { data = [], isLoading } = useQuery({ queryKey: ["vpn"], queryFn: vpnApi.list });

  const createMutation = useMutation({
    mutationFn: vpnApi.create,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["vpn"] }); message.success("Conexión creada"); setFormOpen(false); },
    onError: (e: any) => message.error(e.response?.data?.detail ?? "Error"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<VpnConnection> }) => vpnApi.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["vpn"] }); message.success("Actualizado"); setEditing(null); setFormOpen(false); },
    onError: () => message.error("Error al actualizar"),
  });

  const deleteMutation = useMutation({
    mutationFn: vpnApi.delete,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["vpn"] }); message.success("Eliminado"); },
  });

  function handleSave(values: FormValues) {
    if (editing) {
      updateMutation.mutate({ id: editing.id, data: values });
    } else {
      createMutation.mutate(values);
    }
  }

  const wgList = data.filter((v) => v.vpn_type === "wireguard");
  const l2tpList = data.filter((v) => v.vpn_type === "l2tp");

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>Conexiones VPN</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditing(null); setFormOpen(true); }}>
          Nueva conexión
        </Button>
      </div>

      <Tabs
        activeKey={tab}
        onChange={setTab}
        items={[
          {
            key: "wireguard",
            label: `WireGuard (${wgList.length})`,
            children: isLoading ? <Text>Cargando...</Text> : wgList.length === 0
              ? <Alert type="info" message="No hay conexiones WireGuard. Usá WireGuard para RouterOS v7." />
              : wgList.map((v) => (
                <VpnCard
                  key={v.id}
                  vpn={v}
                  onEdit={() => { setEditing(v); setFormOpen(true); }}
                  onDelete={() => deleteMutation.mutate(v.id)}
                  onCommands={() => setCommandsFor(v)}
                />
              )),
          },
          {
            key: "l2tp",
            label: `L2TP/IPsec (${l2tpList.length})`,
            children: isLoading ? <Text>Cargando...</Text> : l2tpList.length === 0
              ? <Alert type="info" message="No hay conexiones L2TP. Usá L2TP/IPsec para RouterOS v6." />
              : l2tpList.map((v) => (
                <VpnCard
                  key={v.id}
                  vpn={v}
                  onEdit={() => { setEditing(v); setFormOpen(true); }}
                  onDelete={() => deleteMutation.mutate(v.id)}
                  onCommands={() => setCommandsFor(v)}
                />
              )),
          },
        ]}
      />

      <Modal
        title={editing ? "Editar conexión VPN" : "Nueva conexión VPN"}
        open={formOpen}
        onCancel={() => { setFormOpen(false); setEditing(null); }}
        footer={null}
        width={680}
        destroyOnClose
      >
        <VpnForm
          initial={editing ?? undefined}
          onSave={handleSave}
          onCancel={() => { setFormOpen(false); setEditing(null); }}
          isPending={createMutation.isPending || updateMutation.isPending}
        />
      </Modal>

      {commandsFor && (
        <CommandsModal vpn={commandsFor} onClose={() => setCommandsFor(null)} />
      )}
    </div>
  );
}

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Descriptions, Form, Input, Popconfirm, Space, Table, Tag, Typography, message } from "antd";
import { ApiOutlined, CopyOutlined, ReloadOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { beatApi, securitySettingsApi } from "@/services/security/api";
import type { BeatWebhookCapture, SecuritySettings } from "@/types/security";

const { Text, Paragraph } = Typography;

const FETCH_TAG: Record<BeatWebhookCapture["fetch_status"], React.ReactNode> = {
  ok: <Tag color="green">Detalle obtenido</Tag>,
  pending: <Tag color="blue">Consultando…</Tag>,
  error: <Tag color="red">Error</Tag>,
  no_event_id: <Tag>Sin eventId</Tag>,
};

function errorText(e: any): string {
  const d = e?.response?.data?.detail;
  return Array.isArray(d) ? d[0]?.msg?.replace("Value error, ", "") : d ?? "Ocurrió un error";
}

export default function BeatCard({ settings, isAdmin }: { settings: SecuritySettings; isAdmin: boolean }) {
  const qc = useQueryClient();
  const [form] = Form.useForm();
  const b = settings.beat;

  useEffect(() => {
    form.setFieldsValue({ beat_api_url: b.api_url, beat_api_key: "" });
  }, [b.api_url, form]);

  const { data: webhook } = useQuery({
    queryKey: ["beat-webhook-url"],
    queryFn: beatApi.getWebhookUrl,
    enabled: isAdmin,
  });
  const { data: captures = [], isFetching } = useQuery({
    queryKey: ["beat-webhooks"],
    queryFn: () => beatApi.listWebhooks(30),
    enabled: isAdmin,
    refetchInterval: 10_000,
  });

  const save = useMutation({
    mutationFn: securitySettingsApi.update,
    onSuccess: (d) => {
      qc.setQueryData(["security-settings"], d);
      form.setFieldValue("beat_api_key", "");
      message.success("Datos de BEAT guardados");
    },
    onError: (e) => {
      message.error(errorText(e), 8);
    },
  });
  const test = useMutation({
    mutationFn: beatApi.testConnection,
    onSuccess: () => {
      message.success("Conexión con BEAT correcta: la API key funciona");
    },
    onError: (e) => {
      message.error(errorText(e), 10);
    },
  });
  const regen = useMutation({
    mutationFn: beatApi.regenerateWebhookUrl,
    onSuccess: (d) => {
      qc.setQueryData(["beat-webhook-url"], d);
      qc.invalidateQueries({ queryKey: ["security-settings"] });
      message.success("Dirección generada. Cargala en BEAT → Avanzado → Webhooks.");
    },
    onError: (e) => {
      message.error(errorText(e));
    },
  });

  const copy = (text: string) => {
    navigator.clipboard?.writeText(text).then(() => message.success("Copiado"), () => message.info(text));
  };

  const publicUrlIsDefault = settings.integrations.public_url.includes("guaynet.local");

  return (
    <Card title="BEAT (central de alarmas)" style={{ marginBottom: 16 }}>
      <Paragraph type="secondary" style={{ fontSize: 13 }}>
        BEAT avisa a Guaynet cada evento por webhook y Guaynet consulta el detalle con la API key.
        <b> Por ahora en modo captura:</b> los eventos se guardan y se muestran abajo, pero todavía no generan alertas.
      </Paragraph>

      <Form
        form={form}
        layout="vertical"
        disabled={!isAdmin}
        onFinish={(v: { beat_api_url: string; beat_api_key?: string }) =>
          save.mutate({
            beat_api_url: v.beat_api_url,
            ...(v.beat_api_key?.trim() ? { beat_api_key: v.beat_api_key.trim() } : {}),
          })
        }
      >
        <Form.Item name="beat_api_url" label="Dirección de la API" rules={[{ required: true }]}>
          <Input placeholder="https://beat.netio.com.ar/api/v1" />
        </Form.Item>
        <Form.Item
          name="beat_api_key"
          label={
            <Space>
              {b.api_key_configured ? "Reemplazar API key" : "API key"}
              {b.api_key_configured && <Tag color="blue">Cargada {b.api_key_hint}</Tag>}
            </Space>
          }
          extra="Se genera en BEAT → Avanzado → Apikeys. Se guarda cifrada y no se vuelve a mostrar. Dejalo vacío para no cambiarla."
        >
          <Input.Password autoComplete="off" />
        </Form.Item>
        <Space wrap>
          <Button type="primary" htmlType="submit" loading={save.isPending}>Guardar</Button>
          <Button icon={<ApiOutlined />} onClick={() => test.mutate()} loading={test.isPending} disabled={!isAdmin || !b.api_key_configured}>
            Probar conexión
          </Button>
        </Space>
      </Form>

      {isAdmin && (
        <>
          <Descriptions size="small" column={1} style={{ marginTop: 24 }} title="Webhook para cargar en BEAT">
            <Descriptions.Item label="Dirección">
              {webhook?.webhook_url ? (
                <Space wrap>
                  <Text code style={{ wordBreak: "break-all" }}>{webhook.webhook_url}</Text>
                  <Button size="small" icon={<CopyOutlined />} onClick={() => copy(webhook.webhook_url!)}>Copiar</Button>
                </Space>
              ) : (
                <Text type="secondary">Todavía no se generó.</Text>
              )}
            </Descriptions.Item>
          </Descriptions>
          <Space wrap>
            {webhook?.webhook_url ? (
              <Popconfirm
                title="¿Generar una dirección nueva?"
                description="La actual deja de funcionar: hay que cargar la nueva en BEAT."
                okText="Generar"
                cancelText="Cancelar"
                onConfirm={() => regen.mutate()}
              >
                <Button icon={<ReloadOutlined />} loading={regen.isPending}>Generar nueva</Button>
              </Popconfirm>
            ) : (
              <Button type="primary" onClick={() => regen.mutate()} loading={regen.isPending}>Generar dirección</Button>
            )}
          </Space>
          {publicUrlIsDefault && (
            <Alert
              type="warning"
              showIcon
              style={{ marginTop: 12 }}
              message="La dirección pública es la de ejemplo"
              description="Configurá PUBLIC_URL en el .env con la dirección por la que se entra al panel desde internet; si no, BEAT no va a poder llegar."
            />
          )}
          <Paragraph type="secondary" style={{ fontSize: 12, marginTop: 8 }}>
            La dirección incluye una clave secreta: no la compartas. Si se filtra, generá una nueva.
          </Paragraph>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 16 }}>
            <Text strong>Eventos recibidos</Text>
            <Text type="secondary" style={{ fontSize: 12 }}>{isFetching ? "Actualizando…" : "Se actualiza cada 10 s"}</Text>
          </div>
          <Table<BeatWebhookCapture>
            dataSource={captures}
            rowKey="id"
            size="small"
            pagination={false}
            style={{ marginTop: 8 }}
            locale={{ emptyText: "Todavía no llegó ningún evento de BEAT" }}
            expandable={{
              expandedRowRender: (w) => (
                <div style={{ display: "grid", gap: 8 }}>
                  <div>
                    <Text type="secondary">Aviso recibido</Text>
                    <pre style={{ margin: 0, fontSize: 12, whiteSpace: "pre-wrap" }}>{JSON.stringify(w.payload, null, 2)}</pre>
                  </div>
                  <div>
                    <Text type="secondary">Detalle del evento (API de BEAT)</Text>
                    <pre style={{ margin: 0, fontSize: 12, whiteSpace: "pre-wrap" }}>
                      {w.event_detail ? JSON.stringify(w.event_detail, null, 2) : w.fetch_error ?? "—"}
                    </pre>
                  </div>
                </div>
              ),
            }}
            columns={[
              {
                title: "Recibido",
                dataIndex: "received_at",
                render: (v: string | null) => (v ? dayjs(v).format("DD/MM HH:mm:ss") : "—"),
              },
              { title: "Tipo", dataIndex: "event_type", render: (v: string | null) => v ?? "—" },
              { title: "eventId", dataIndex: "event_id", render: (v: string | null) => v ?? "—" },
              { title: "Origen", dataIndex: "remote_ip", render: (v: string | null) => v ?? "—" },
              {
                title: "Estado",
                dataIndex: "fetch_status",
                render: (v: BeatWebhookCapture["fetch_status"], w) => (
                  <Space size={4}>
                    {FETCH_TAG[v]}
                    {v === "error" && w.fetch_error && <Text type="danger" style={{ fontSize: 12 }}>{w.fetch_error}</Text>}
                  </Space>
                ),
              },
            ]}
          />
        </>
      )}
    </Card>
  );
}

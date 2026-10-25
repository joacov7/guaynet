import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Popconfirm,
  Select,
  Space,
  Spin,
  Tag,
  Typography,
  message,
} from "antd";
import { SendOutlined } from "@ant-design/icons";
import { securitySettingsApi } from "@/services/security/api";
import { usePermissions } from "@/contexts/PermissionsContext";
import type { SecurityParamKey } from "@/types/security";

const { Title, Text, Paragraph } = Typography;

const SOURCE_LABEL: Record<string, React.ReactNode> = {
  panel: <Tag color="blue">Configurado acá</Tag>,
  env: <Tag>Desde el archivo .env</Tag>,
  none: <Tag color="red">Sin configurar</Tag>,
};

const PARAMS: { key: SecurityParamKey; label: string; unit: string; help: string }[] = [
  {
    key: "sec_confirmation_window_seconds",
    label: "Espera de respuesta del cliente",
    unit: "segundos",
    help: "Con «Confirmación de alerta» activa, tiempo que se espera el «¿Estás bien?» antes de avisar a la central.",
  },
  {
    key: "sec_entry_default_minutes",
    label: "Duración de la entrada segura",
    unit: "minutos",
    help: "Cuenta regresiva que se inicia desde el portal o la app si no se indica otra.",
  },
  {
    key: "sec_schedule_default_tolerance",
    label: "Tolerancia por defecto del horario comercial",
    unit: "minutos",
    help: "Valor inicial al cargar el horario de un abonado nuevo.",
  },
];

function errorText(e: any): string {
  const d = e?.response?.data?.detail;
  return Array.isArray(d) ? d[0]?.msg?.replace("Value error, ", "") : d ?? "No se pudo guardar";
}

export default function SecuritySettings() {
  const qc = useQueryClient();
  const { isAdmin } = usePermissions();
  const [tgForm] = Form.useForm();
  const [paramsForm] = Form.useForm();
  const [testResult, setTestResult] = useState<{ bot_username: string; results: { chat_id: number; ok: boolean; error?: string }[] } | null>(null);

  const { data, isLoading } = useQuery({ queryKey: ["security-settings"], queryFn: securitySettingsApi.get });

  useEffect(() => {
    if (!data) return;
    tgForm.setFieldsValue({ telegram_token: "", operator_chat_ids: data.telegram.operator_chat_ids.map(String) });
    paramsForm.setFieldsValue(data.params);
  }, [data, tgForm, paramsForm]);

  const save = useMutation({
    mutationFn: securitySettingsApi.update,
    onSuccess: (d) => {
      qc.setQueryData(["security-settings"], d);
      message.success("Configuración guardada");
      setTestResult(null);
    },
    onError: (e) => message.error(errorText(e), 8),
  });

  const test = useMutation({
    mutationFn: securitySettingsApi.telegramTest,
    onSuccess: setTestResult,
    onError: (e) => message.error(errorText(e), 8),
  });

  if (isLoading || !data) return <Spin style={{ margin: 40 }} />;

  const t = data.telegram;

  const submitTelegram = (v: { telegram_token?: string; operator_chat_ids?: string[] }) => {
    const ids = (v.operator_chat_ids ?? []).map((x) => x.trim()).filter(Boolean);
    const bad = ids.filter((x) => !/^-?\d+$/.test(x));
    if (bad.length) {
      message.error(`Estos IDs no son números: ${bad.join(", ")}`);
      return;
    }
    save.mutate({
      ...(v.telegram_token?.trim() ? { telegram_token: v.telegram_token.trim() } : {}),
      operator_chat_ids: ids.map(Number),
    });
  };

  return (
    <div style={{ padding: 24, maxWidth: 900 }}>
      <Title level={3} style={{ marginTop: 0 }}>Configuración de Seguridad</Title>
      {!isAdmin && (
        <Alert type="info" showIcon style={{ marginBottom: 16 }} message="Solo un administrador puede cambiar esta configuración." />
      )}

      <Card title="Telegram" style={{ marginBottom: 16 }}>
        <Paragraph type="secondary" style={{ fontSize: 13 }}>
          El bot envía las alertas a la central y a los clientes. Las personas de la lista también pueden usar los comandos
          del bot (buscar clientes, cortar o activar el servicio): agregá solo personas de confianza.
        </Paragraph>
        <Descriptions size="small" column={1} style={{ marginBottom: 16 }}>
          <Descriptions.Item label="Token del bot">
            <Space>
              {SOURCE_LABEL[t.token_source]}
              {t.token_hint && <Text code>{t.token_hint}</Text>}
            </Space>
          </Descriptions.Item>
          <Descriptions.Item label="Reciben las alertas">
            <Space>
              {SOURCE_LABEL[t.operator_chat_ids_source]}
              {t.operator_chat_ids.length > 0 && <Text>{t.operator_chat_ids.join(", ")}</Text>}
            </Space>
          </Descriptions.Item>
        </Descriptions>

        <Form form={tgForm} layout="vertical" disabled={!isAdmin} onFinish={submitTelegram}>
          <Form.Item
            name="telegram_token"
            label={t.configured ? "Reemplazar token" : "Token del bot"}
            extra="Lo da @BotFather al crear el bot. Se guarda cifrado y no se vuelve a mostrar. Dejalo vacío para no cambiarlo."
          >
            <Input.Password placeholder="123456789:AA…" autoComplete="off" />
          </Form.Item>
          <Form.Item
            name="operator_chat_ids"
            label="IDs de Telegram que reciben las alertas"
            extra="Tu ID te lo da @userinfobot. Para un grupo, el ID empieza con «-». Cada persona tiene que mandarle /start al bot."
            rules={[{ required: true, message: "Agregá al menos un ID" }]}
          >
            <Select mode="tags" tokenSeparators={[",", " "]} placeholder="987654321" open={false} />
          </Form.Item>
          <Space wrap>
            <Button type="primary" htmlType="submit" loading={save.isPending}>Guardar</Button>
            <Button icon={<SendOutlined />} onClick={() => test.mutate()} loading={test.isPending} disabled={!isAdmin || !t.configured}>
              Enviar mensaje de prueba
            </Button>
            {t.token_source === "panel" && (
              <Popconfirm
                title="¿Quitar el token cargado acá?"
                description={t.token_source === "panel" ? "Se usará el del archivo .env, si hay uno." : undefined}
                okText="Quitar"
                cancelText="Cancelar"
                onConfirm={() => save.mutate({ telegram_token: "" })}
              >
                <Button danger>Quitar token</Button>
              </Popconfirm>
            )}
          </Space>
        </Form>

        {testResult && (
          <Alert
            style={{ marginTop: 16 }}
            type={testResult.results.every((r) => r.ok) ? "success" : "warning"}
            showIcon
            message={`Bot @${testResult.bot_username}`}
            description={
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {testResult.results.map((r) => (
                  <li key={r.chat_id}>
                    {r.chat_id}: {r.ok ? "mensaje enviado" : <Text type="danger">{r.error}</Text>}
                  </li>
                ))}
              </ul>
            }
          />
        )}
      </Card>

      <Card title="Parámetros de operación" style={{ marginBottom: 16 }}>
        <Form form={paramsForm} layout="vertical" disabled={!isAdmin} onFinish={(v) => save.mutate({ params: v })}>
          {PARAMS.map((p) => {
            const lim = data.param_limits[p.key];
            return (
              <Form.Item
                key={p.key}
                name={p.key}
                label={p.label}
                extra={`${p.help} Entre ${lim.min} y ${lim.max}; por defecto ${lim.default}.`}
                rules={[{ required: true }]}
              >
                <InputNumber min={lim.min} max={lim.max} addonAfter={p.unit} style={{ width: 220 }} />
              </Form.Item>
            );
          })}
          <Button type="primary" htmlType="submit" loading={save.isPending}>Guardar parámetros</Button>
        </Form>
      </Card>

      <Card title="Integraciones">
        <Descriptions size="small" column={1}>
          <Descriptions.Item label="BEAT (central de alarmas)">
            {data.integrations.beat_adapter === "real" ? (
              <Tag color="green">Conectado</Tag>
            ) : (
              <Space wrap>
                <Tag color="orange">Simulado</Tag>
                <Text type="secondary">
                  {data.integrations.beat_mock_polling
                    ? "Generando eventos de prueba (BEAT_MOCK_POLLING=1)."
                    : "No se consultan eventos hasta conectar la API real de BEAT."}
                </Text>
              </Space>
            )}
          </Descriptions.Item>
          <Descriptions.Item label="Notificaciones de la app">
            {data.integrations.push === "fcm" ? <Tag color="green">Firebase configurado</Tag> : <Tag color="orange">Simuladas (falta Firebase)</Tag>}
          </Descriptions.Item>
          <Descriptions.Item label="Dirección pública">
            <Space wrap>
              <Text code>{data.integrations.public_url}</Text>
              {data.integrations.public_url.includes("guaynet.local") && (
                <Text type="warning">Es el valor de ejemplo: los enlaces del portal que se envían a clientes no van a funcionar. Se cambia con PUBLIC_URL en el .env.</Text>
              )}
            </Space>
          </Descriptions.Item>
        </Descriptions>
      </Card>
    </div>
  );
}

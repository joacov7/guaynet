import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Badge,
  Button,
  Card,
  Col,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Statistic,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  EyeOutlined,
  ReloadOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { alertsApi } from "@/services/security/api";
import type { AlertPanelItem } from "@/types/security";

const { Title, Text } = Typography;

// ── Alert metadata ────────────────────────────────────────────────────────────

const ALERT_META: Record<string, { label: string; color: string; bgColor: string }> = {
  PANIC:              { label: "PÁNICO",          color: "#cf1322", bgColor: "#fff1f0" },
  DURESS:             { label: "COACCIÓN",         color: "#cf1322", bgColor: "#fff1f0" },
  INTRUSION:          { label: "INTRUSIÓN",        color: "#d46b08", bgColor: "#fff7e6" },
  ENTRY_TIMEOUT:      { label: "ENTRADA EXPIRADA", color: "#d46b08", bgColor: "#fff7e6" },
  CHECKIN_MISSED:     { label: "SIN CHECK-IN",     color: "#7c3aed", bgColor: "#f5f3ff" },
  INACTIVITY:         { label: "INACTIVIDAD",      color: "#7c3aed", bgColor: "#f5f3ff" },
  SYSTEM_FAULT:       { label: "FALLA SISTEMA",    color: "#595959", bgColor: "#fafafa" },
  CONNECTION_LOST:    { label: "SIN SEÑAL",        color: "#595959", bgColor: "#fafafa" },
  SCHEDULE_VIOLATION: { label: "FUERA DE HORARIO", color: "#595959", bgColor: "#fafafa" },
};

const PRIORITY_TYPES = new Set(["PANIC", "DURESS"]);

// ── Elapsed time helper ───────────────────────────────────────────────────────

function useNow(intervalMs = 1000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}

function formatElapsed(triggeredAt: string, now: number): string {
  const secs = Math.floor((now - new Date(triggeredAt).getTime()) / 1000);
  if (secs < 60) return `${secs}s`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ${secs % 60}s`;
  const hrs = Math.floor(mins / 60);
  return `${hrs}h ${mins % 60}m`;
}

// ── Alert card ────────────────────────────────────────────────────────────────

function AlertCard({
  alert,
  now,
  onAcknowledge,
  onResolve,
  onFalseAlarm,
  onManage,
  loading,
}: {
  alert: AlertPanelItem;
  now: number;
  onAcknowledge: () => void;
  onResolve: () => void;
  onFalseAlarm: () => void;
  onManage: () => void;
  loading: boolean;
}) {
  const meta = ALERT_META[alert.alert_type] ?? { label: alert.alert_type, color: "#595959", bgColor: "#fafafa" };
  const isPriority = PRIORITY_TYPES.has(alert.alert_type);
  const elapsed = formatElapsed(alert.triggered_at, now);
  const isNew = alert.status === "new";

  return (
    <Card
      size="small"
      style={{
        marginBottom: 12,
        borderLeft: `4px solid ${meta.color}`,
        backgroundColor: isPriority && isNew ? meta.bgColor : undefined,
        boxShadow: isPriority && isNew ? `0 0 0 1px ${meta.color}40` : undefined,
      }}
      bodyStyle={{ padding: "10px 12px" }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
        {/* Left: type + property */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ marginBottom: 2 }}>
            <Text strong style={{ color: meta.color, fontSize: 13, letterSpacing: 0.3 }}>
              {meta.label}
            </Text>
            {isNew && (
              <Tag color="red" style={{ marginLeft: 6, fontSize: 10 }}>NUEVA</Tag>
            )}
          </div>
          <div style={{ fontSize: 13, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {alert.property_name}
          </div>
          <div style={{ fontSize: 12, color: "#595959" }}>
            {alert.property_address}
          </div>
          {alert.beat_account_id && (
            <div style={{ fontSize: 11, color: "#8c8c8c", marginTop: 2 }}>
              Cuenta BEAT: {alert.beat_account_id}
            </div>
          )}
          {alert.operator_notes && (
            <div style={{ fontSize: 11, color: "#595959", marginTop: 4, fontStyle: "italic" }}>
              "{alert.operator_notes}"
            </div>
          )}
        </div>

        {/* Right: timer + actions */}
        <div style={{ textAlign: "right", flexShrink: 0 }}>
          <div style={{ fontSize: 20, fontWeight: 700, color: meta.color, fontVariantNumeric: "tabular-nums" }}>
            {elapsed}
          </div>
          <div style={{ fontSize: 10, color: "#8c8c8c", marginBottom: 6 }}>transcurrido</div>
          <Space size={4} wrap style={{ justifyContent: "flex-end" }}>
            {isNew && (
              <Tooltip title="Marcar como atendiendo">
                <Button
                  size="small"
                  icon={<EyeOutlined />}
                  onClick={onAcknowledge}
                  loading={loading}
                >
                  Atender
                </Button>
              </Tooltip>
            )}
            <Tooltip title="Resolver">
              <Button
                size="small"
                type="primary"
                icon={<CheckCircleOutlined />}
                onClick={onResolve}
                loading={loading}
              >
                Resolver
              </Button>
            </Tooltip>
            <Popconfirm
              title="¿Confirmar falsa alarma?"
              onConfirm={onFalseAlarm}
              okText="Sí"
              cancelText="No"
            >
              <Tooltip title="Falsa alarma">
                <Button size="small" icon={<CloseCircleOutlined />} loading={loading} />
              </Tooltip>
            </Popconfirm>
            <Tooltip title="Gestionar con notas">
              <Button size="small" icon={<WarningOutlined />} onClick={onManage} />
            </Tooltip>
          </Space>
        </div>
      </div>

      {/* Confirmation status */}
      {alert.confirmation_sent_at && isNew && (
        <div style={{ marginTop: 6, paddingTop: 6, borderTop: "1px solid #f0f0f0" }}>
          {(() => {
            const expires = alert.confirmation_expires_at ? new Date(alert.confirmation_expires_at) : null;
            const remaining = expires ? Math.max(0, Math.round((expires.getTime() - now) / 1000)) : 0;
            return remaining > 0 ? (
              <Tag color="orange" style={{ fontSize: 11 }}>Esperando confirmación del cliente ({remaining}s)</Tag>
            ) : (
              <Tag color="red" style={{ fontSize: 11 }}>Cliente no respondió la confirmación</Tag>
            );
          })()}
        </div>
      )}
    </Card>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────────

export default function SecurityOperatorPanel() {
  const qc = useQueryClient();
  const [manageAlert, setManageAlert] = useState<AlertPanelItem | null>(null);
  const [form] = Form.useForm();
  const prevNewCount = useRef(0);
  const now = useNow();

  const { data: alerts = [], isLoading, dataUpdatedAt } = useQuery({
    queryKey: ["security-alert-panel"],
    queryFn: () => alertsApi.listPanel(),
    refetchInterval: 15_000,
  });

  const newAlerts = alerts.filter((a) => a.status === "new");
  const ackAlerts = alerts.filter((a) => a.status === "acknowledged");

  // Flash document title when new alerts arrive
  useEffect(() => {
    const count = newAlerts.length;
    if (count > 0) {
      document.title = `(${count}) Alerta${count > 1 ? "s" : ""} — Guaynet`;
    } else {
      document.title = "Central de Monitoreo — Guaynet";
    }
    if (count > prevNewCount.current && prevNewCount.current >= 0) {
      message.warning({ content: `Nueva alerta de seguridad`, duration: 5 });
    }
    prevNewCount.current = count;
    return () => { document.title = "Guaynet"; };
  }, [newAlerts.length]);

  const updateMutation = useMutation({
    mutationFn: ({ id, status, notes }: { id: number; status: string; notes?: string }) =>
      alertsApi.update(id, { status: status as AlertPanelItem["status"], operator_notes: notes }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["security-alert-panel"] });
      qc.invalidateQueries({ queryKey: ["security-alerts"] });
      message.success("Alerta actualizada");
      setManageAlert(null);
    },
    onError: () => message.error("Error al actualizar la alerta"),
  });

  const quickAction = (id: number, status: string) =>
    updateMutation.mutate({ id, status });

  const handleManageSubmit = (values: { status: string; operator_notes?: string }) => {
    if (!manageAlert) return;
    updateMutation.mutate({ id: manageAlert.id, ...values });
  };

  const lastUpdated = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString("es-AR", { timeStyle: "medium" })
    : "—";

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: "0 auto" }}>
      {/* Header */}
      <Row justify="space-between" align="middle" style={{ marginBottom: 20 }}>
        <Col>
          <Title level={3} style={{ margin: 0 }}>Central de Monitoreo</Title>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Actualización automática cada 15 s · Última: {lastUpdated}
          </Text>
        </Col>
        <Col>
          <Button
            icon={<ReloadOutlined />}
            loading={isLoading}
            onClick={() => qc.invalidateQueries({ queryKey: ["security-alert-panel"] })}
          >
            Actualizar
          </Button>
        </Col>
      </Row>

      {/* Stats */}
      <Row gutter={16} style={{ marginBottom: 20 }}>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="Alertas nuevas"
              value={newAlerts.length}
              valueStyle={{ color: newAlerts.length > 0 ? "#cf1322" : "#52c41a" }}
              prefix={newAlerts.length > 0 ? <WarningOutlined /> : <CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="En atención"
              value={ackAlerts.length}
              valueStyle={{ color: ackAlerts.length > 0 ? "#d46b08" : "#8c8c8c" }}
            />
          </Card>
        </Col>
      </Row>

      {/* Alert lists */}
      <Row gutter={24}>
        {/* New alerts */}
        <Col xs={24} lg={12}>
          <div style={{ marginBottom: 8 }}>
            <Badge count={newAlerts.length} offset={[6, 0]}>
              <Text strong style={{ fontSize: 14 }}>Nuevas</Text>
            </Badge>
          </div>
          {newAlerts.length === 0 ? (
            <Card size="small">
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={<Text type="secondary">Sin alertas nuevas</Text>}
              />
            </Card>
          ) : (
            newAlerts.map((a) => (
              <AlertCard
                key={a.id}
                alert={a}
                now={now}
                loading={updateMutation.isPending}
                onAcknowledge={() => quickAction(a.id, "acknowledged")}
                onResolve={() => quickAction(a.id, "resolved")}
                onFalseAlarm={() => quickAction(a.id, "false_alarm")}
                onManage={() => { setManageAlert(a); form.setFieldsValue({ status: a.status, operator_notes: a.operator_notes }); }}
              />
            ))
          )}
        </Col>

        {/* Acknowledged alerts */}
        <Col xs={24} lg={12}>
          <div style={{ marginBottom: 8 }}>
            <Badge count={ackAlerts.length} color="orange" offset={[6, 0]}>
              <Text strong style={{ fontSize: 14 }}>En atención</Text>
            </Badge>
          </div>
          {ackAlerts.length === 0 ? (
            <Card size="small">
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={<Text type="secondary">Sin alertas en atención</Text>}
              />
            </Card>
          ) : (
            ackAlerts.map((a) => (
              <AlertCard
                key={a.id}
                alert={a}
                now={now}
                loading={updateMutation.isPending}
                onAcknowledge={() => quickAction(a.id, "acknowledged")}
                onResolve={() => quickAction(a.id, "resolved")}
                onFalseAlarm={() => quickAction(a.id, "false_alarm")}
                onManage={() => { setManageAlert(a); form.setFieldsValue({ status: a.status, operator_notes: a.operator_notes }); }}
              />
            ))
          )}
        </Col>
      </Row>

      {/* Manage modal */}
      <Modal
        open={!!manageAlert}
        title={manageAlert ? `Gestionar: ${ALERT_META[manageAlert.alert_type]?.label ?? manageAlert.alert_type} — ${manageAlert.property_name}` : "Gestionar alerta"}
        onCancel={() => setManageAlert(null)}
        footer={null}
        width={480}
      >
        {manageAlert && (
          <Form form={form} layout="vertical" onFinish={handleManageSubmit}>
            <Form.Item label="Dirección">
              <Text>{manageAlert.property_address}</Text>
            </Form.Item>
            {manageAlert.beat_account_id && (
              <Form.Item label="Cuenta BEAT">
                <Text code>{manageAlert.beat_account_id}</Text>
              </Form.Item>
            )}
            <Form.Item name="status" label="Nuevo estado" rules={[{ required: true }]}>
              <Select
                options={[
                  { value: "acknowledged", label: "Atendiendo" },
                  { value: "resolved",     label: "Resuelta" },
                  { value: "false_alarm",  label: "Falsa alarma" },
                ]}
              />
            </Form.Item>
            <Form.Item name="operator_notes" label="Notas del operador">
              <Input.TextArea rows={3} placeholder="Describe la intervención realizada..." />
            </Form.Item>
            <Form.Item>
              <Space>
                <Button type="primary" htmlType="submit" loading={updateMutation.isPending}>
                  Guardar
                </Button>
                <Button onClick={() => setManageAlert(null)}>Cancelar</Button>
              </Space>
            </Form.Item>
          </Form>
        )}
      </Modal>
    </div>
  );
}

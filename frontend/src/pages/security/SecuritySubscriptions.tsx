import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Badge,
  Button,
  Col,
  DatePicker,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import { BarChartOutlined, CalendarOutlined, ClockCircleOutlined, MobileOutlined, CopyOutlined, DeleteOutlined, DownloadOutlined, EyeOutlined, FilePdfOutlined, HeartOutlined, KeyOutlined, LinkOutlined, PlusOutlined, ReloadOutlined, SettingOutlined, TeamOutlined, ToolOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { useNavigate, useSearchParams } from "react-router-dom";
import ScheduleModal from "./ScheduleModal";
import { featureLabels } from "./labels";
import AppDevicesModal from "./AppDevicesModal";
import { subscriptionsApi, pinsApi, certificatesApi, elderlyApi, monthlyReportsApi, vacationApi, propertiesApi, plansApi } from "@/services/security/api";
import type { ElderlyConfig, MonthlyReport, VacationMode } from "@/types/security";
import type { SecuritySubscription, SecurityFeatureName } from "@/types/security";

const { Title } = Typography;

const statusColor: Record<string, string> = {
  active: "green",
  suspended: "orange",
  cancelled: "red",
  pending_install: "blue",
};

const statusLabel: Record<string, string> = {
  active: "Activo",
  suspended: "Suspendido",
  cancelled: "Cancelado",
  pending_install: "Pendiente instalación",
};

export default function SecuritySubscriptions() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [createOpen, setCreateOpen] = useState(false);
  const [featuresModal, setFeaturesModal] = useState<SecuritySubscription | null>(null);
  const [editModal, setEditModal] = useState<SecuritySubscription | null>(null);
  const [pinsModal, setPinsModal] = useState<SecuritySubscription | null>(null);
  const [elderlyModal, setElderlyModal] = useState<SecuritySubscription | null>(null);
  const [reportsModal, setReportsModal] = useState<SecuritySubscription | null>(null);
  const [vacationModal, setVacationModal] = useState<SecuritySubscription | null>(null);
  const [scheduleModal, setScheduleModal] = useState<SecuritySubscription | null>(null);
  const [appDevicesModal, setAppDevicesModal] = useState<SecuritySubscription | null>(null);
  const [vacationForm] = Form.useForm();
  const [form] = Form.useForm();
  const [editForm] = Form.useForm();
  const [pinForm] = Form.useForm();
  const [elderlyForm] = Form.useForm();

  const { data = [], isLoading } = useQuery({
    queryKey: ["security-subscriptions"],
    queryFn: () => subscriptionsApi.list(),
  });

  const createMutation = useMutation({
    mutationFn: (values: any) => subscriptionsApi.create(values),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["security-subscriptions"] });
      message.success("Suscripción creada");
      setCreateOpen(false);
      form.resetFields();
    },
    onError: (e: any) => message.error(e.response?.data?.detail ?? "Error al crear"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Record<string, unknown> }) =>
      subscriptionsApi.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["security-subscriptions"] });
      message.success("Suscripción actualizada");
      setEditModal(null);
      editForm.resetFields();
    },
    onError: () => message.error("Error al actualizar suscripción"),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, feature_name, enabled }: { id: number; feature_name: SecurityFeatureName; enabled: boolean }) =>
      subscriptionsApi.toggleFeature(id, feature_name, enabled) as Promise<void>,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["security-subscriptions"] }),
    onError: () => message.error("Error al cambiar funcionalidad"),
  });

  const { data: temporaryPins = [], refetch: refetchPins } = useQuery({
    queryKey: ["security-temp-pins", pinsModal?.id],
    queryFn: () => pinsApi.listTemporary(pinsModal!.id),
    enabled: !!pinsModal,
  });

  const createPinMutation = useMutation({
    mutationFn: (values: { new_pin: string; label?: string; expires_at: dayjs.Dayjs }) =>
      pinsApi.setPin({
        subscription_id: pinsModal!.id,
        pin_type: "temporary",
        new_pin: values.new_pin,
        label: values.label,
        expires_at: values.expires_at.toISOString(),
      }),
    onSuccess: () => {
      refetchPins();
      pinForm.resetFields();
      message.success("PIN temporal creado");
    },
    onError: (e: any) => message.error(e.response?.data?.detail ?? "Error al crear PIN"),
  });

  const deletePinMutation = useMutation({
    mutationFn: (pinId: number) => pinsApi.deleteTemporary(pinId, pinsModal!.id),
    onSuccess: () => { refetchPins(); message.success("PIN revocado"); },
    onError: () => message.error("Error al revocar PIN"),
  });

  const { data: elderlyConfig, refetch: refetchElderly } = useQuery<ElderlyConfig | null>({
    queryKey: ["security-elderly", elderlyModal?.id],
    queryFn: async () => {
      try {
        return await elderlyApi.get(elderlyModal!.id);
      } catch {
        return null;
      }
    },
    enabled: !!elderlyModal,
  });

  const { data: monthlyReports = [] } = useQuery<MonthlyReport[]>({
    queryKey: ["security-monthly-reports", reportsModal?.id],
    queryFn: () => monthlyReportsApi.list(reportsModal!.id),
    enabled: !!reportsModal,
  });

  const elderlySaveMutation = useMutation({
    mutationFn: (values: { check_from: string; check_until: string; notify_telegram_id?: string; enabled: boolean }) =>
      elderlyApi.upsert(elderlyModal!.id, values),
    onSuccess: () => {
      refetchElderly();
      message.success("Configuración guardada");
    },
    onError: (e: any) => message.error(e.response?.data?.detail ?? "Error al guardar"),
  });

  const elderlyDeleteMutation = useMutation({
    mutationFn: () => elderlyApi.delete(elderlyModal!.id),
    onSuccess: () => {
      refetchElderly();
      elderlyForm.resetFields();
      message.success("Configuración eliminada");
    },
    onError: () => message.error("Error al eliminar"),
  });

  const certMutation = useMutation({
    mutationFn: (subscriptionId: number) => certificatesApi.generate(subscriptionId),
    onSuccess: async (_, subscriptionId) => {
      message.success("Certificado generado — descargando...");
      const blob = await certificatesApi.download(subscriptionId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `certificado_proteccion_${subscriptionId}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    },
    onError: (e: any) => message.error(e.response?.data?.detail ?? "Error al generar certificado"),
  });

  const portalTokenMutation = useMutation({
    mutationFn: (id: number) => subscriptionsApi.regeneratePortalToken(id),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["security-subscriptions"] });
      message.success("Enlace generado y enviado por Telegram");
      // Copy to clipboard
      navigator.clipboard?.writeText(data.portal_url).catch(() => {});
    },
    onError: (e: any) => message.error(e?.response?.data?.detail ?? "Error al generar enlace"),
  });

  const { data: vacationModes = [], refetch: refetchVacations } = useQuery<VacationMode[]>({
    queryKey: ["security-vacations", vacationModal?.id],
    queryFn: () => vacationApi.list(vacationModal!.id),
    enabled: !!vacationModal,
  });

  const createVacationMutation = useMutation({
    mutationFn: (values: { start_date: dayjs.Dayjs; end_date: dayjs.Dayjs; notes?: string }) =>
      vacationApi.create({
        subscription_id: vacationModal!.id,
        start_date: values.start_date.format("YYYY-MM-DD"),
        end_date: values.end_date.format("YYYY-MM-DD"),
        notes: values.notes,
      }),
    onSuccess: () => {
      refetchVacations();
      vacationForm.resetFields();
      message.success("Modo ausencia activado");
    },
    onError: (e: any) => message.error(e.response?.data?.detail ?? "Error al activar"),
  });

  const cancelVacationMutation = useMutation({
    mutationFn: (id: number) => vacationApi.cancel(id),
    onSuccess: () => {
      refetchVacations();
      message.success("Modo ausencia cancelado");
    },
    onError: (e: any) => message.error(e.response?.data?.detail ?? "Error al cancelar"),
  });

  const { data: properties = [] } = useQuery({
    queryKey: ["security-properties"],
    queryFn: () => propertiesApi.list(),
  });
  const { data: plans = [] } = useQuery({
    queryKey: ["security-plans-all"],
    queryFn: () => plansApi.list(false),
  });
  const propertyById = useMemo(() => new Map(properties.map((p) => [p.id, p])), [properties]);
  const planById = useMemo(() => new Map(plans.map((p) => [p.id, p])), [plans]);

  // /security/subscriptions?new=<property_id> opens the create form preselected
  useEffect(() => {
    const pre = searchParams.get("new");
    if (pre) {
      form.setFieldsValue({ property_id: Number(pre) });
      setCreateOpen(true);
      searchParams.delete("new");
      setSearchParams(searchParams, { replace: true });
    }
  }, [searchParams, setSearchParams, form]);

  const columns = [
    { title: "ID", dataIndex: "id", key: "id", width: 60 },
    {
      title: "Propiedad",
      dataIndex: "property_id",
      key: "property",
      render: (v: number) => {
        const p = propertyById.get(v);
        return p ? (
          <div>
            <div>{p.name}</div>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>{p.address}</Typography.Text>
          </div>
        ) : `Prop. #${v}`;
      },
    },
    {
      title: "Plan",
      dataIndex: "plan_id",
      key: "plan",
      render: (v: number) => planById.get(v)?.name ?? `Plan #${v}`,
    },
    {
      title: "Estado",
      dataIndex: "status",
      key: "status",
      render: (v: string) => <Tag color={statusColor[v] ?? "default"}>{statusLabel[v] ?? v}</Tag>,
    },
    {
      title: "Notificación",
      key: "notification",
      render: (_: unknown, r: SecuritySubscription) => (
        <Tag color={r.client_telegram_id ? "blue" : "default"}>
          {r.client_telegram_id ? "Telegram cliente" : "Sin canal"}
        </Tag>
      ),
    },
    {
      title: "BEAT",
      dataIndex: "beat_account_id",
      key: "beat",
      render: (v: string | undefined) => v ?? <span style={{ color: "#aaa" }}>No configurado</span>,
    },
    {
      title: "Portal cliente",
      key: "portal",
      render: (_: unknown, r: SecuritySubscription) => {
        if (r.portal_token) {
          const url = `/portal?token=${r.portal_token}`;
          return (
            <Space size={4}>
              <Tooltip title="Copiar enlace">
                <Button
                  size="small"
                  icon={<CopyOutlined />}
                  onClick={() => {
                    navigator.clipboard?.writeText(`${window.location.origin}${url}`);
                    message.success("Enlace copiado");
                  }}
                />
              </Tooltip>
              <Tooltip title="Regenerar y reenviar por Telegram">
                <Button
                  size="small"
                  icon={<ReloadOutlined />}
                  loading={portalTokenMutation.isPending && portalTokenMutation.variables === r.id}
                  onClick={() => portalTokenMutation.mutate(r.id)}
                />
              </Tooltip>
            </Space>
          );
        }
        return (
          <Tooltip title="Generar acceso para el cliente">
            <Button
              size="small"
              icon={<LinkOutlined />}
              loading={portalTokenMutation.isPending && portalTokenMutation.variables === r.id}
              onClick={() => portalTokenMutation.mutate(r.id)}
            >
              Generar
            </Button>
          </Tooltip>
        );
      },
    },
    {
      title: "Funcionalidades",
      key: "features",
      render: (_: unknown, r: SecuritySubscription) => {
        const enabled = r.features.filter((f) => f.enabled).length;
        return (
          <Tooltip title="Ver y editar funcionalidades">
            <Button
              size="small"
              icon={<SettingOutlined />}
              onClick={() => setFeaturesModal(r)}
            >
              {enabled}/{r.features.length}
            </Button>
          </Tooltip>
        );
      },
    },
    {
      title: "",
      key: "actions",
      render: (_: unknown, r: SecuritySubscription) => (
        <Space>
          <Button
            size="small"
            icon={<KeyOutlined />}
            onClick={() => setPinsModal(r)}
          >
            PINs
          </Button>
          <Tooltip title="Miembros de la propiedad">
            <Button
              size="small"
              icon={<TeamOutlined />}
              onClick={() => navigate(`/security/members?property_id=${r.property_id}`)}
            />
          </Tooltip>
          <Tooltip title="Equipos instalados">
            <Button
              size="small"
              icon={<ToolOutlined />}
              onClick={() => navigate(`/security/devices?subscription_id=${r.id}`)}
            />
          </Tooltip>
          <Tooltip title="Reportes mensuales">
            <Button
              size="small"
              icon={<BarChartOutlined />}
              onClick={() => setReportsModal(r)}
            />
          </Tooltip>
          <Tooltip title="Check-in adultos mayores">
            <Button
              size="small"
              icon={<HeartOutlined />}
              onClick={() => {
                setElderlyModal(r);
              }}
            />
          </Tooltip>
          <Tooltip title="Teléfonos con la app">
            <Button
              size="small"
              icon={<MobileOutlined />}
              onClick={() => setAppDevicesModal(r)}
            />
          </Tooltip>
          <Tooltip title="Horario comercial">
            <Button
              size="small"
              icon={<ClockCircleOutlined />}
              onClick={() => setScheduleModal(r)}
            />
          </Tooltip>
          <Tooltip title="Modo ausencia / viaje">
            <Button
              size="small"
              icon={<CalendarOutlined />}
              onClick={() => setVacationModal(r)}
            />
          </Tooltip>
          <Tooltip title="Generar certificado PDF para seguros">
            <Button
              size="small"
              icon={<FilePdfOutlined />}
              loading={certMutation.isPending && certMutation.variables === r.id}
              onClick={() => certMutation.mutate(r.id)}
            />
          </Tooltip>
          <Button
            size="small"
            icon={<EyeOutlined />}
            onClick={() => {
              setEditModal(r);
              editForm.setFieldsValue({
                beat_account_id: r.beat_account_id,
                client_telegram_id: r.client_telegram_id,
                notes: r.notes,
              });
            }}
          >
            Editar
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={3} style={{ margin: 0 }}>Abonados de Seguridad</Title>
        </Col>
        <Col>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
            Nueva suscripción
          </Button>
        </Col>
      </Row>

      <Table
        dataSource={data}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        size="small"
        pagination={{ pageSize: 20 }}
      />

      {/* Create modal */}
      <Modal
        open={createOpen}
        title="Nueva suscripción de seguridad"
        onCancel={() => { setCreateOpen(false); form.resetFields(); }}
        footer={null}
      >
        <Form form={form} layout="vertical" onFinish={(v) => createMutation.mutate(v)}>
          <Form.Item
            name="property_id"
            label="Propiedad"
            rules={[{ required: true, message: "Elegí la propiedad" }]}
            extra={properties.length === 0 ? <a onClick={() => navigate("/security/properties")}>Primero creá una propiedad</a> : undefined}
          >
            <Select
              showSearch
              optionFilterProp="label"
              placeholder="Buscar por nombre o dirección"
              options={properties.map((p) => ({ value: p.id, label: `${p.name} — ${p.address}` }))}
            />
          </Form.Item>
          <Form.Item
            name="plan_id"
            label="Plan"
            rules={[{ required: true, message: "Elegí el plan" }]}
            extra={plans.every((p) => !p.is_active) ? <a onClick={() => navigate("/security/plans")}>Primero creá un plan</a> : undefined}
          >
            <Select
              placeholder="Elegí el plan"
              options={plans
                .filter((p) => p.is_active)
                .map((p) => ({
                  value: p.id,
                  label: `${p.name} — ${new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 }).format(p.price)}`,
                }))}
            />
          </Form.Item>
          <Form.Item name="beat_account_id" label="Cuenta BEAT (opcional)">
            <Input />
          </Form.Item>
          <Form.Item name="billing_day" label="Día de facturación" initialValue={1}>
            <InputNumber min={1} max={28} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="notes" label="Notas">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={createMutation.isPending}>
                Crear
              </Button>
              <Button onClick={() => { setCreateOpen(false); form.resetFields(); }}>Cancelar</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* Edit modal — beat_account_id, client_telegram_id, notes */}
      <Modal
        open={!!editModal}
        title={`Editar suscripción #${editModal?.id}`}
        onCancel={() => { setEditModal(null); editForm.resetFields(); }}
        footer={null}
      >
        <Form
          form={editForm}
          layout="vertical"
          onFinish={(v) => editModal && updateMutation.mutate({ id: editModal.id, data: v })}
        >
          <Form.Item name="beat_account_id" label="Cuenta BEAT">
            <Input placeholder="ID de cuenta en central BEAT" />
          </Form.Item>
          <Form.Item
            name="client_telegram_id"
            label="Telegram ID del cliente"
            tooltip="Chat ID de Telegram para notificar al cliente cuando no hay monitoreo operado"
          >
            <Input placeholder="Ej: 123456789" />
          </Form.Item>
          <Form.Item name="notes" label="Notas">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={updateMutation.isPending}>
                Guardar
              </Button>
              <Button onClick={() => { setEditModal(null); editForm.resetFields(); }}>Cancelar</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* Elderly care config modal */}
      <Modal
        open={!!elderlyModal}
        title={`Check-in Adultos Mayores — Suscripción #${elderlyModal?.id}`}
        onCancel={() => { setElderlyModal(null); elderlyForm.resetFields(); }}
        footer={null}
        width={460}
      >
        {elderlyModal && (
          <div>
            <p style={{ color: "#555", marginBottom: 16, fontSize: 13 }}>
              Si la alarma no es desactivada antes del horario configurado, se envía una
              alerta al familiar de confianza y/o al canal de operadores.
            </p>
            <Form
              form={elderlyForm}
              layout="vertical"
              initialValues={elderlyConfig ?? { check_from: "07:00", check_until: "10:00", enabled: true }}
              onFinish={(v) => elderlySaveMutation.mutate(v)}
              key={elderlyConfig?.id ?? "new"}
            >
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item name="check_from" label="Ventana desde">
                    <Input placeholder="07:00" maxLength={5} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="check_until" label="Alerta si no hay actividad antes de">
                    <Input placeholder="10:00" maxLength={5} />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item
                name="notify_telegram_id"
                label="Telegram del familiar (opcional)"
                tooltip="Chat ID de Telegram del familiar que recibirá la alerta"
              >
                <Input placeholder="Ej: 123456789" />
              </Form.Item>
              <Form.Item name="enabled" label="Activado" valuePropName="checked">
                <Switch />
              </Form.Item>
              <Form.Item style={{ marginBottom: 0 }}>
                <Space>
                  <Button type="primary" htmlType="submit" loading={elderlySaveMutation.isPending}>
                    Guardar
                  </Button>
                  {elderlyConfig && (
                    <Popconfirm
                      title="¿Eliminar configuración?"
                      onConfirm={() => elderlyDeleteMutation.mutate()}
                      okText="Eliminar"
                      cancelText="Cancelar"
                    >
                      <Button danger loading={elderlyDeleteMutation.isPending}>
                        Eliminar
                      </Button>
                    </Popconfirm>
                  )}
                  <Button onClick={() => { setElderlyModal(null); elderlyForm.resetFields(); }}>
                    Cancelar
                  </Button>
                </Space>
              </Form.Item>
            </Form>
          </div>
        )}
      </Modal>

      {/* Temporary PINs modal */}
      <Modal
        open={!!pinsModal}
        title={`PINs Temporales — Suscripción #${pinsModal?.id}`}
        onCancel={() => { setPinsModal(null); pinForm.resetFields(); }}
        footer={<Button onClick={() => { setPinsModal(null); pinForm.resetFields(); }}>Cerrar</Button>}
        width={540}
      >
        {pinsModal && (
          <div>
            <Table
              dataSource={temporaryPins}
              rowKey="id"
              size="small"
              pagination={false}
              style={{ marginBottom: 16 }}
              locale={{ emptyText: "Sin PINs temporales activos" }}
              columns={[
                {
                  title: "Etiqueta",
                  dataIndex: "label",
                  key: "label",
                  render: (v: string) => v ?? <span style={{ color: "#aaa" }}>Sin etiqueta</span>,
                },
                {
                  title: "Expira",
                  dataIndex: "expires_at",
                  key: "expires_at",
                  render: (v: string) => {
                    const d = dayjs(v);
                    const expired = d.isBefore(dayjs());
                    return (
                      <Tag color={expired ? "red" : "blue"}>
                        {d.format("DD/MM/YY HH:mm")}
                        {expired ? " (expirado)" : ""}
                      </Tag>
                    );
                  },
                },
                {
                  title: "",
                  key: "delete",
                  render: (_: unknown, row: { id: number }) => (
                    <Popconfirm
                      title="¿Revocar este PIN?"
                      onConfirm={() => deletePinMutation.mutate(row.id)}
                      okText="Revocar"
                      cancelText="Cancelar"
                    >
                      <Button size="small" danger icon={<DeleteOutlined />} />
                    </Popconfirm>
                  ),
                },
              ]}
            />

            <Form
              form={pinForm}
              layout="vertical"
              onFinish={(v) => createPinMutation.mutate(v)}
            >
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item
                    name="new_pin"
                    label="PIN (4+ dígitos)"
                    rules={[
                      { required: true, message: "Ingresá el PIN" },
                      { pattern: /^\d{4,}$/, message: "Solo dígitos, mínimo 4" },
                    ]}
                  >
                    <Input placeholder="Ej: 7391" maxLength={8} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="label" label="Etiqueta (opcional)">
                    <Input placeholder="Ej: Técnico 27/10" />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item
                name="expires_at"
                label="Expira el"
                rules={[{ required: true, message: "Seleccioná fecha de expiración" }]}
              >
                <DatePicker
                  showTime
                  format="DD/MM/YYYY HH:mm"
                  style={{ width: "100%" }}
                  disabledDate={(d) => d.isBefore(dayjs(), "day")}
                />
              </Form.Item>
              <Form.Item style={{ marginBottom: 0 }}>
                <Button type="primary" htmlType="submit" loading={createPinMutation.isPending}>
                  Crear PIN temporal
                </Button>
              </Form.Item>
            </Form>
          </div>
        )}
      </Modal>

      {/* Features modal */}
      <Modal
        open={!!featuresModal}
        title={`Funcionalidades — Suscripción #${featuresModal?.id}`}
        onCancel={() => setFeaturesModal(null)}
        footer={<Button onClick={() => setFeaturesModal(null)}>Cerrar</Button>}
        width={520}
      >
        {featuresModal && (
          <div>
            {featuresModal.features.map((f) => (
              <Row key={f.feature_name} justify="space-between" align="middle" style={{ padding: "6px 0", borderBottom: "1px solid #f0f0f0" }}>
                <Col>{featureLabels[f.feature_name as SecurityFeatureName] ?? f.feature_name}</Col>
                <Col>
                  <Switch
                    checked={f.enabled}
                    loading={toggleMutation.isPending}
                    onChange={(checked) =>
                      toggleMutation.mutate({
                        id: featuresModal.id,
                        feature_name: f.feature_name as SecurityFeatureName,
                        enabled: checked,
                      })
                    }
                  />
                </Col>
              </Row>
            ))}
          </div>
        )}
      </Modal>
      {/* Monthly reports modal */}
      <Modal
        open={!!reportsModal}
        title={`Reportes Mensuales — Suscripción #${reportsModal?.id}`}
        onCancel={() => setReportsModal(null)}
        footer={<Button onClick={() => setReportsModal(null)}>Cerrar</Button>}
        width={560}
      >
        {reportsModal && (
          <Table
            dataSource={monthlyReports}
            rowKey="id"
            size="small"
            pagination={false}
            locale={{ emptyText: "Sin reportes generados aún" }}
            columns={[
              {
                title: "Período",
                dataIndex: "period",
                key: "period",
                render: (p: string) => {
                  const months = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"];
                  const [y, m] = p.split("-");
                  return `${months[parseInt(m) - 1]} ${y}`;
                },
              },
              { title: "Eventos", dataIndex: "event_count", key: "event_count", align: "center" as const },
              { title: "Alertas", dataIndex: "alert_count", key: "alert_count", align: "center" as const },
              {
                title: "Estado",
                dataIndex: "status",
                key: "status",
                render: (s: string) => (
                  <Tag color={s === "ready" ? "green" : s === "failed" ? "red" : "default"}>
                    {s === "ready" ? "Listo" : s === "failed" ? "Error" : "Generando"}
                  </Tag>
                ),
              },
              {
                title: "",
                key: "dl",
                render: (_: unknown, r: MonthlyReport) =>
                  r.status === "ready" ? (
                    <a
                      href={monthlyReportsApi.downloadUrl(r.subscription_id, r.period)}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <Button size="small" icon={<DownloadOutlined />}>PDF</Button>
                    </a>
                  ) : null,
              },
            ]}
          />
        )}
      </Modal>

      <ScheduleModal subscription={scheduleModal} onClose={() => setScheduleModal(null)} />
      <AppDevicesModal subscription={appDevicesModal} onClose={() => setAppDevicesModal(null)} />

      {/* Vacation mode modal */}
      <Modal
        open={!!vacationModal}
        title={`Modo Ausencia — Suscripción #${vacationModal?.id}`}
        onCancel={() => { setVacationModal(null); vacationForm.resetFields(); }}
        footer={<Button onClick={() => { setVacationModal(null); vacationForm.resetFields(); }}>Cerrar</Button>}
        width={520}
      >
        {vacationModal && (
          <div>
            {/* Active or upcoming vacation modes */}
            {vacationModes.filter((v) => v.active).length > 0 && (
              <div style={{ marginBottom: 16 }}>
                {vacationModes.filter((v) => v.active).map((v) => (
                  <div
                    key={v.id}
                    style={{
                      background: "#fff7e6",
                      border: "1px solid #ffd591",
                      borderRadius: 6,
                      padding: "10px 12px",
                      marginBottom: 8,
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <div>
                      <Tag color="orange" icon={<CalendarOutlined />}>Activo</Tag>
                      <span style={{ marginLeft: 8 }}>
                        {dayjs(v.start_date).format("DD/MM/YYYY")} → {dayjs(v.end_date).format("DD/MM/YYYY")}
                      </span>
                      {v.notes && <div style={{ fontSize: 12, color: "#595959", marginTop: 2 }}>{v.notes}</div>}
                    </div>
                    <Popconfirm
                      title="¿Cancelar modo ausencia?"
                      onConfirm={() => cancelVacationMutation.mutate(v.id)}
                      okText="Sí"
                      cancelText="No"
                    >
                      <Button
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                        loading={cancelVacationMutation.isPending}
                      >
                        Cancelar
                      </Button>
                    </Popconfirm>
                  </div>
                ))}
              </div>
            )}

            {/* New vacation form */}
            {vacationModes.filter((v) => v.active).length === 0 && (
              <Form form={vacationForm} layout="vertical" onFinish={(v) => createVacationMutation.mutate(v)}>
                <Row gutter={12}>
                  <Col span={12}>
                    <Form.Item name="start_date" label="Fecha de salida" rules={[{ required: true }]}>
                      <DatePicker style={{ width: "100%" }} format="DD/MM/YYYY" />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item name="end_date" label="Fecha de regreso" rules={[{ required: true }]}>
                      <DatePicker style={{ width: "100%" }} format="DD/MM/YYYY" />
                    </Form.Item>
                  </Col>
                </Row>
                <Form.Item name="notes" label="Notas (opcional)">
                  <Input placeholder="Ej: viaje a la costa" />
                </Form.Item>
                <div style={{ fontSize: 12, color: "#595959", marginBottom: 12 }}>
                  Durante el modo ausencia, cualquier apertura de zona generará una alerta de intrusión inmediata.
                  El cliente recibirá una notificación por Telegram al activar y al finalizar el período.
                </div>
                <Form.Item>
                  <Button type="primary" htmlType="submit" icon={<CalendarOutlined />} loading={createVacationMutation.isPending}>
                    Activar modo ausencia
                  </Button>
                </Form.Item>
              </Form>
            )}

            {/* History */}
            {vacationModes.filter((v) => !v.active).length > 0 && (
              <div style={{ marginTop: 8 }}>
                <div style={{ fontSize: 12, color: "#8c8c8c", marginBottom: 4 }}>Historial</div>
                {vacationModes.filter((v) => !v.active).map((v) => (
                  <div key={v.id} style={{ fontSize: 12, color: "#8c8c8c", marginBottom: 2 }}>
                    {dayjs(v.start_date).format("DD/MM/YYYY")} → {dayjs(v.end_date).format("DD/MM/YYYY")}
                    {v.notes && ` · ${v.notes}`}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}

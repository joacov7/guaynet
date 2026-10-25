import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, InputNumber, Modal, Space, Spin, Switch, TimePicker, Typography, message } from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { scheduleApi, securitySettingsApi } from "@/services/security/api";
import type { ScheduleDay, SecuritySubscription } from "@/types/security";

const { Text } = Typography;

// Parses "HH:mm" or "HH:mm:ss" without needing dayjs' customParseFormat plugin.
const hm = (v: string): Dayjs => {
  const [h, m] = v.split(":").map(Number);
  return dayjs().hour(h).minute(m).second(0).millisecond(0);
};

const DAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];

interface Row {
  open: boolean;
  open_time: Dayjs;
  close_time: Dayjs;
  tolerance_minutes: number;
}

const defaultRow = (weekday: number, tolerance = 15): Row => ({
  open: weekday < 5,
  open_time: hm("09:00"),
  close_time: hm(weekday === 5 ? "13:00" : "18:00"),
  tolerance_minutes: tolerance,
});

export default function ScheduleModal({
  subscription,
  onClose,
}: {
  subscription: SecuritySubscription | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [rows, setRows] = useState<Row[]>(() => DAYS.map((_, i) => defaultRow(i)));
  const featureOn = !!subscription?.features.find((f) => f.feature_name === "schedule_alerts" && f.enabled);

  const { data: settings } = useQuery({
    queryKey: ["security-settings"],
    queryFn: securitySettingsApi.get,
    enabled: !!subscription,
  });
  const defaultTolerance = settings?.params.sec_schedule_default_tolerance ?? 15;

  const { data, isLoading } = useQuery({
    queryKey: ["security-schedule", subscription?.id],
    queryFn: () => scheduleApi.get(subscription!.id),
    enabled: !!subscription,
  });

  useEffect(() => {
    if (!data) return;
    if (data.length === 0) {
      setRows(DAYS.map((_, i) => defaultRow(i, defaultTolerance)));
      return;
    }
    setRows(
      DAYS.map((_, i) => {
        const d = data.find((x) => x.weekday === i);
        return d
          ? {
              open: d.enabled,
              open_time: hm(d.open_time),
              close_time: hm(d.close_time),
              tolerance_minutes: d.tolerance_minutes,
            }
          : { ...defaultRow(i, defaultTolerance), open: false };
      }),
    );
  }, [data, defaultTolerance]);

  const saveMutation = useMutation({
    mutationFn: () => {
      const days: ScheduleDay[] = rows
        .map((r, weekday) => ({ r, weekday }))
        .filter(({ r }) => r.open)
        .map(({ r, weekday }) => ({
          weekday,
          open_time: r.open_time.format("HH:mm:00"),
          close_time: r.close_time.format("HH:mm:00"),
          tolerance_minutes: r.tolerance_minutes,
          enabled: true,
        }));
      return scheduleApi.replace(subscription!.id, days);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["security-schedule", subscription?.id] });
      message.success("Horario guardado");
      onClose();
    },
    onError: (e: any) => {
      const detail = e.response?.data?.detail;
      message.error(Array.isArray(detail) ? detail[0]?.msg : detail ?? "Error al guardar el horario");
    },
  });

  const clearMutation = useMutation({
    mutationFn: () => scheduleApi.replace(subscription!.id, []),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["security-schedule", subscription?.id] });
      message.success("Horario eliminado");
      onClose();
    },
    onError: () => message.error("Error al eliminar el horario"),
  });

  const invalid = rows.some((r) => r.open && !r.open_time.isBefore(r.close_time));
  const update = (i: number, patch: Partial<Row>) =>
    setRows((prev) => prev.map((r, j) => (j === i ? { ...r, ...patch } : r)));

  return (
    <Modal
      open={!!subscription}
      title={`Horario comercial — Suscripción #${subscription?.id}`}
      onCancel={onClose}
      width={720}
      footer={
        <Space>
          {!!data?.length && (
            <Button danger onClick={() => clearMutation.mutate()} loading={clearMutation.isPending}>
              Quitar horario
            </Button>
          )}
          <Button onClick={onClose}>Cancelar</Button>
          <Button type="primary" disabled={invalid} loading={saveMutation.isPending} onClick={() => saveMutation.mutate()}>
            Guardar
          </Button>
        </Space>
      }
    >
      {!featureOn && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 12 }}
          message="La funcionalidad «Alertas de horario» está desactivada para este abonado"
          description="El horario se guarda, pero no genera alertas hasta activarla en Funcionalidades."
        />
      )}
      <Text type="secondary" style={{ fontSize: 12, display: "block", marginBottom: 12 }}>
        Se genera una alerta si la alarma se desarma fuera del horario (más la tolerancia) o si sigue
        desarmada después del cierre. Si pasada la apertura (más la tolerancia) la alarma sigue armada, se le
        avisa al dueño por Telegram. Los días marcados como cerrados no admiten desarmes. Hora de Argentina.
      </Text>
      {isLoading ? (
        <Spin />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {rows.map((r, i) => {
            const bad = r.open && !r.open_time.isBefore(r.close_time);
            return (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <div style={{ width: 90 }}>
                  <Text strong={r.open}>{DAYS[i]}</Text>
                </div>
                <Switch
                  checked={r.open}
                  onChange={(open) => update(i, { open })}
                  checkedChildren="Abierto"
                  unCheckedChildren="Cerrado"
                />
                {r.open && (
                  <>
                    <TimePicker
                      value={r.open_time}
                      format="HH:mm"
                      minuteStep={5}
                      allowClear={false}
                      status={bad ? "error" : undefined}
                      onChange={(v) => v && update(i, { open_time: v })}
                    />
                    <Text type="secondary">a</Text>
                    <TimePicker
                      value={r.close_time}
                      format="HH:mm"
                      minuteStep={5}
                      allowClear={false}
                      status={bad ? "error" : undefined}
                      onChange={(v) => v && update(i, { close_time: v })}
                    />
                    <InputNumber
                      value={r.tolerance_minutes}
                      min={0}
                      max={180}
                      addonAfter="min"
                      style={{ width: 110 }}
                      onChange={(v) => update(i, { tolerance_minutes: v ?? 0 })}
                    />
                  </>
                )}
              </div>
            );
          })}
        </div>
      )}
    </Modal>
  );
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Modal, Popconfirm, Table, Tag, Typography, message } from "antd";
import dayjs from "dayjs";
import { appDevicesApi } from "@/services/security/api";
import type { AppDevice, SecuritySubscription } from "@/types/security";

const { Text } = Typography;

export default function AppDevicesModal({
  subscription,
  onClose,
}: {
  subscription: SecuritySubscription | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const queryKey = ["security-app-devices", subscription?.id];
  const { data = [], isLoading } = useQuery({
    queryKey,
    queryFn: () => appDevicesApi.list(subscription!.id),
    enabled: !!subscription,
  });

  const revokeMutation = useMutation({
    mutationFn: (id: number) => appDevicesApi.revoke(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey });
      message.success("Teléfono desvinculado");
    },
    onError: () => message.error("No se pudo desvincular"),
  });

  return (
    <Modal
      open={!!subscription}
      title={`Teléfonos con la app — Suscripción #${subscription?.id}`}
      onCancel={onClose}
      footer={<Button onClick={onClose}>Cerrar</Button>}
      width={720}
    >
      <Text type="secondary" style={{ fontSize: 12, display: "block", marginBottom: 12 }}>
        El cliente vincula cada teléfono con el enlace del portal y el PIN de la alarma. Si pierde un teléfono,
        desvinculalo acá: deja de recibir alertas y de poder operar.
      </Text>
      <Table<AppDevice>
        dataSource={data}
        rowKey="id"
        size="small"
        loading={isLoading}
        pagination={false}
        locale={{ emptyText: "Ningún teléfono vinculado" }}
        columns={[
          { title: "Nombre", dataIndex: "device_name", key: "name" },
          {
            title: "Notificaciones",
            dataIndex: "has_push",
            key: "push",
            render: (v: boolean, d) => (d.revoked_at ? "—" : v ? <Tag color="green">Activas</Tag> : <Tag>Sin registrar</Tag>),
          },
          {
            title: "Vinculado",
            dataIndex: "created_at",
            key: "created",
            render: (v: string) => dayjs(v).format("DD/MM/YYYY"),
          },
          {
            title: "Último uso",
            dataIndex: "last_seen_at",
            key: "seen",
            render: (v?: string) => (v ? dayjs(v).format("DD/MM/YYYY HH:mm") : "—"),
          },
          {
            title: "Estado",
            key: "state",
            render: (_: unknown, d) =>
              d.revoked_at ? <Tag>Desvinculado {dayjs(d.revoked_at).format("DD/MM")}</Tag> : <Tag color="blue">Activo</Tag>,
          },
          {
            title: "",
            key: "actions",
            render: (_: unknown, d) =>
              !d.revoked_at && (
                <Popconfirm
                  title="¿Desvincular este teléfono?"
                  okText="Desvincular"
                  cancelText="Cancelar"
                  onConfirm={() => revokeMutation.mutate(d.id)}
                >
                  <Button size="small" danger>Desvincular</Button>
                </Popconfirm>
              ),
          },
        ]}
      />
    </Modal>
  );
}

import { Alert, Button, Modal, Space, Typography, message } from "antd";
import { CopyOutlined, SendOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import type { TelegramLink } from "@/types/security";

const { Paragraph, Text } = Typography;

/** Shows a one-time Telegram link for the operator to send to the person. */
export default function TelegramLinkModal({
  link,
  who,
  onClose,
}: {
  link: TelegramLink | null;
  who: string;
  onClose: () => void;
}) {
  const copy = () => {
    if (!link) return;
    navigator.clipboard?.writeText(link.url).then(
      () => {
        message.success("Enlace copiado");
      },
      () => {
        message.info(link.url);
      },
    );
  };

  return (
    <Modal open={!!link} title={`Vincular Telegram — ${who}`} onCancel={onClose} footer={<Button onClick={onClose}>Cerrar</Button>}>
      {link && (
        <Space direction="vertical" style={{ width: "100%" }}>
          <Paragraph style={{ marginBottom: 0 }}>
            Mandale este enlace por WhatsApp o mensaje. Al abrirlo en el celular se abre el bot y queda vinculado:
            empieza a recibir los avisos de la alarma y puede usar /estado, /entrada, /panico y los demás comandos.
          </Paragraph>
          <Text code copyable={false} style={{ wordBreak: "break-all" }}>{link.url}</Text>
          <Space wrap>
            <Button type="primary" icon={<CopyOutlined />} onClick={copy}>Copiar enlace</Button>
            <Button icon={<SendOutlined />} href={link.url} target="_blank" rel="noreferrer">Abrir en Telegram</Button>
          </Space>
          <Alert
            type="info"
            showIcon
            message={`Sirve una sola vez y vence el ${dayjs(link.expires_at).format("DD/MM HH:mm")}.`}
            description="Si se vincula otra persona por error, generá uno nuevo para la persona correcta."
          />
        </Space>
      )}
    </Modal>
  );
}

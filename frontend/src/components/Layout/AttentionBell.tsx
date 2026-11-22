import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Badge, Button, Empty, Popover, Typography, theme } from "antd";
import { BellOutlined, CheckCircleOutlined, ExclamationCircleFilled, InfoCircleFilled, WarningFilled } from "@ant-design/icons";
import dayjs from "dayjs";
import { workspaceApi, type AttentionItem } from "@/services/api";

const { Text } = Typography;

/** "Pendientes": live state of the system (refreshed every minute), filtered by the user's permissions. */
export default function AttentionBell() {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const { token } = theme.useToken();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["attention"],
    queryFn: workspaceApi.attention,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
  });
  const items = data?.items ?? [];
  const critical = items.some((i) => i.severity === "critical");

  const ICON: Record<AttentionItem["severity"], JSX.Element> = {
    critical: <ExclamationCircleFilled style={{ color: token.colorError }} />,
    warning: <WarningFilled style={{ color: token.colorWarning }} />,
    info: <InfoCircleFilled style={{ color: token.colorInfo }} />,
  };

  const content = (
    <div style={{ width: 320, maxWidth: "calc(100vw - 48px)" }}>
      {isError && <Text type="danger">No se pudieron cargar los pendientes.</Text>}
      {!isError && !isLoading && items.length === 0 && (
        <Empty image={<CheckCircleOutlined style={{ fontSize: 36, color: token.colorSuccess }} />} imageStyle={{ height: 40 }} description="Nada pendiente" />
      )}
      {items.map((i) => (
        <div
          key={i.key}
          role="button"
          tabIndex={0}
          onClick={() => { setOpen(false); navigate(i.url); }}
          onKeyDown={(e) => { if (e.key === "Enter") { setOpen(false); navigate(i.url); } }}
          style={{ display: "flex", gap: 10, padding: "8px 6px", borderRadius: 6, cursor: "pointer" }}
          onMouseEnter={(e) => (e.currentTarget.style.background = token.colorFillTertiary)}
          onMouseLeave={(e) => (e.currentTarget.style.background = "")}
        >
          <span style={{ fontSize: 16, lineHeight: "20px" }}>{ICON[i.severity]}</span>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontWeight: 500 }}>{i.title}</div>
            {i.detail && <Text type="secondary" style={{ fontSize: 12 }}>{i.detail}</Text>}
          </div>
        </div>
      ))}
      {data && (
        <Text type="secondary" style={{ fontSize: 11, display: "block", marginTop: 6 }}>
          Actualizado {dayjs(data.checked_at).format("HH:mm")} · se revisa cada minuto
        </Text>
      )}
    </div>
  );

  return (
    <Popover open={open} onOpenChange={setOpen} trigger="click" placement="bottomRight" title="Pendientes" content={content}>
      <Badge count={items.length} size="small" color={critical ? token.colorError : token.colorWarning} offset={[-4, 4]}>
        <Button type="text" icon={<BellOutlined style={{ fontSize: 18 }} />} aria-label={`Pendientes (${items.length})`} />
      </Badge>
    </Popover>
  );
}

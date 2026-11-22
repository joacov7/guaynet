import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Button, Empty, Input, Modal, Spin, Tag, Typography, theme, type InputRef } from "antd";
import { ApartmentOutlined, AppstoreOutlined, CustomerServiceOutlined, SearchOutlined, UserOutlined } from "@ant-design/icons";
import { workspaceApi, type SearchResult } from "@/services/api";
import { useVisibleNav } from "./Sidebar";

const { Text } = Typography;

const TYPE: Record<SearchResult["type"] | "page", { label: string; icon: JSX.Element }> = {
  client: { label: "Cliente", icon: <UserOutlined /> },
  ticket: { label: "Ticket", icon: <CustomerServiceOutlined /> },
  router: { label: "Router", icon: <ApartmentOutlined /> },
  page: { label: "Pantalla", icon: <AppstoreOutlined /> },
};

interface Row {
  key: string;
  type: keyof typeof TYPE;
  title: string;
  subtitle: string;
  url: string;
}

const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
const normalize = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

function useDebounced<T>(value: T, ms: number) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

/** Button for the top bar + the Ctrl+K / ⌘K dialog. */
export default function GlobalSearch({ compact = false }: { compact?: boolean }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<InputRef>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const { token } = theme.useToken();
  const { flat } = useVisibleNav();
  const term = useDebounced(q.trim(), 250);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (!open) {
      setQ("");
      setActive(0);
      return;
    }
    // The dialog keeps focus while it animates in: send any key to the search box, so typing
    // right after Ctrl+K is not lost (focusing during keydown makes the key land in the box)
    const grab = (e: KeyboardEvent) => {
      const el = inputRef.current?.input;
      if (el && document.activeElement !== el && !e.ctrlKey && !e.metaKey && e.key !== "Escape") el.focus();
    };
    window.addEventListener("keydown", grab, true);
    return () => window.removeEventListener("keydown", grab, true);
  }, [open]);

  const { data: found = [], isFetching } = useQuery({
    queryKey: ["global-search", term],
    queryFn: () => workspaceApi.search(term),
    enabled: open && term.length >= 2,
    staleTime: 15_000,
  });

  const rows: Row[] = useMemo(() => {
    const t = normalize(q.trim());
    const pages = flat
      .filter((p) => !t || normalize(`${p.label} ${p.group}`).includes(t))
      .slice(0, t ? 5 : 8)
      .map((p) => ({ key: `page${p.key}`, type: "page" as const, title: p.label, subtitle: p.group, url: p.key }));
    const data = term.length >= 2 && term === q.trim()
      ? found.map((r) => ({ key: `${r.type}${r.id}`, type: r.type, title: r.title, subtitle: r.subtitle, url: r.url }))
      : [];
    return [...data, ...pages];
  }, [q, term, found, flat]);

  useEffect(() => setActive(0), [rows.length, term]);
  useEffect(() => {
    listRef.current?.querySelector<HTMLElement>(`[data-idx="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  const go = (row?: Row) => {
    if (!row) return;
    setOpen(false);
    navigate(row.url);
  };

  return (
    <>
      {compact ? (
        <Button type="text" icon={<SearchOutlined />} aria-label="Buscar" onClick={() => setOpen(true)} />
      ) : (
        <Button onClick={() => setOpen(true)} icon={<SearchOutlined />} style={{ width: 280, textAlign: "left", color: token.colorTextTertiary }}>
          <span style={{ flex: 1 }}>Buscar cliente, IP, ticket…</span>
          <Tag style={{ marginInlineEnd: 0, fontSize: 11 }}>{isMac ? "⌘" : "Ctrl"} K</Tag>
        </Button>
      )}
      <Modal
        open={open}
        onCancel={() => setOpen(false)}
        footer={null}
        closable={false}
        width={620}
        style={{ top: 80 }}
        styles={{ content: { padding: 0 } }}
        destroyOnClose
        afterOpenChange={(o) => { if (o) inputRef.current?.focus(); }}
      >
        <div style={{ padding: 12, borderBottom: `1px solid ${token.colorBorderSecondary}` }}>
          <Input
            ref={inputRef}
            autoFocus
            size="large"
            variant="borderless"
            prefix={<SearchOutlined />}
            suffix={isFetching ? <Spin size="small" /> : null}
            placeholder="Nombre, apellido, IP, DNI, teléfono, MAC, dirección, #ticket, router o pantalla"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, rows.length - 1)); }
              else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
              else if (e.key === "Enter") { e.preventDefault(); go(rows[active]); }
            }}
          />
        </div>
        <div ref={listRef} role="listbox" style={{ maxHeight: "60vh", overflowY: "auto", padding: 6 }}>
          {rows.length === 0 && !isFetching && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Sin resultados" />}
          {rows.map((r, i) => (
            <div
              key={r.key}
              data-idx={i}
              role="option"
              aria-selected={i === active}
              onMouseEnter={() => setActive(i)}
              onClick={() => go(r)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                padding: "8px 10px",
                borderRadius: 6,
                cursor: "pointer",
                background: i === active ? token.colorPrimaryBg : undefined,
              }}
            >
              <span style={{ color: token.colorTextSecondary, fontSize: 16 }}>{TYPE[r.type].icon}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.title}</div>
                {r.subtitle && (
                  <Text type="secondary" style={{ fontSize: 12, display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {r.subtitle}
                  </Text>
                )}
              </div>
              <Tag bordered={false}>{TYPE[r.type].label}</Tag>
            </div>
          ))}
        </div>
        <div style={{ padding: "6px 12px", borderTop: `1px solid ${token.colorBorderSecondary}`, fontSize: 12, color: token.colorTextTertiary }}>
          ↑ ↓ para moverte · Enter para abrir · Esc para cerrar
        </div>
      </Modal>
    </>
  );
}

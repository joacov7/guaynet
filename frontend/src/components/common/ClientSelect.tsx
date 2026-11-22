import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Select } from "antd";
import type { SelectProps } from "antd";
import { clientsApi } from "@/services/api";

/**
 * Customer picker that searches on the server (name, IP, phone, DNI, MAC, email)
 * instead of loading every customer into memory. Works as a Form.Item control
 * (value / onChange = client id).
 */
export default function ClientSelect({
  value,
  onChange,
  placeholder = "Buscá por nombre, IP, DNI o teléfono",
  ...rest
}: {
  value?: number | null;
  onChange?: (id: number | undefined) => void;
} & Omit<SelectProps, "value" | "onChange" | "options">) {
  const [typed, setTyped] = useState("");
  const [search, setSearch] = useState("");

  useEffect(() => {
    const t = setTimeout(() => setSearch(typed.trim()), 300);
    return () => clearTimeout(t);
  }, [typed]);

  const { data: results = [], isFetching } = useQuery({
    queryKey: ["client-select", search],
    queryFn: () => clientsApi.list({ search: search || undefined, limit: 20 }),
    staleTime: 30_000,
  });

  // The selected customer may not be among the results (editing an existing record)
  const { data: current } = useQuery({
    queryKey: ["client", value],
    queryFn: () => clientsApi.get(value as number),
    enabled: !!value && !results.some((c) => c.id === value),
    staleTime: 60_000,
  });

  const list = current && !results.some((c) => c.id === current.id) ? [current, ...results] : results;
  return (
    <Select
      showSearch
      allowClear
      filterOption={false}
      onSearch={setTyped}
      loading={isFetching}
      value={value ?? undefined}
      onChange={(v) => onChange?.(v as number | undefined)}
      placeholder={placeholder}
      notFoundContent={isFetching ? "Buscando…" : "Sin resultados"}
      options={list.map((c) => ({ value: c.id, label: `${c.full_name} · ${c.ip_address}` }))}
      {...rest}
    />
  );
}

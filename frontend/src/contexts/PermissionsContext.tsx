import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { permissionsApi, MyPermissions } from "@/services/api";

interface PermissionsCtx {
  loaded: boolean;
  isAdmin: boolean;
  canView: (section: string) => boolean;
  canEdit: (section: string) => boolean;
  reload: () => void;
}

const Ctx = createContext<PermissionsCtx>({
  loaded: false,
  isAdmin: false,
  canView: () => false,
  canEdit: () => false,
  reload: () => undefined,
});

export function PermissionsProvider({ children }: { children: ReactNode }) {
  const [data, setData] = useState<MyPermissions | null>(null);

  async function load() {
    try {
      const p = await permissionsApi.my();
      setData(p);
    } catch {
      setData(null);
    }
  }

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (token) load();
  }, []);

  const canView = (section: string) => {
    if (!data) return false;
    if (data.is_admin) return true;
    return data.permissions[section]?.can_view ?? false;
  };

  const canEdit = (section: string) => {
    if (!data) return false;
    if (data.is_admin) return true;
    return data.permissions[section]?.can_edit ?? false;
  };

  return (
    <Ctx.Provider value={{ loaded: !!data, isAdmin: data?.is_admin ?? false, canView, canEdit, reload: load }}>
      {children}
    </Ctx.Provider>
  );
}

export function usePermissions() {
  return useContext(Ctx);
}

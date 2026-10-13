import { usePermissions } from "@/contexts/PermissionsContext";

export function usePermission(section: string) {
  const { canView, canEdit, isAdmin } = usePermissions();
  return {
    canView: canView(section),
    canEdit: canEdit(section),
    isAdmin,
  };
}

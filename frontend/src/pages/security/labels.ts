import type { SecurityFeatureName } from "@/types/security";

export const featureLabels: Record<SecurityFeatureName, string> = {
  entry_secure:            "Entrada Segura",
  panic_button:            "Botón de pánico",
  duress_pin:              "PIN de coacción",
  safe_word:               "Palabra segura",
  vacation_mode:           "Modo ausencia",
  member_access:           "Miembros",
  camera_access:           "Cámaras",
  elderly_care:            "Adultos mayores",
  schedule_alerts:         "Alertas de horario",
  alert_confirmation:      "Confirmación de alerta",
  equipment_status:        "Estado de equipos",
  monitoring_certificate:  "Certificado de monitoreo",
  tech_survey:             "Encuesta técnica",
  event_history:           "Historial de eventos",
  monthly_report:          "Reporte mensual",
  weekly_report:           "Reporte semanal",
  digital_contract:        "Contrato digital",
};

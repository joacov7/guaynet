import React from "react";
import { Alert, Typography } from "antd";

const { Title } = Typography;

const SecurityAlerts: React.FC = () => (
  <div style={{ padding: 24 }}>
    <Title level={3}>Alertas de Seguridad</Title>
    <Alert type="info" message="Disponible en Etapa 2" showIcon />
  </div>
);

export default SecurityAlerts;

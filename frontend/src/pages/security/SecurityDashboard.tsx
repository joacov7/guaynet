import React from "react";
import { Alert, Typography } from "antd";

const { Title } = Typography;

const SecurityDashboard: React.FC = () => (
  <div style={{ padding: 24 }}>
    <Title level={3}>Seguridad</Title>
    <Alert
      type="info"
      message="Módulo en desarrollo"
      description="Guaynet Seguridad estará disponible próximamente."
      showIcon
    />
  </div>
);

export default SecurityDashboard;

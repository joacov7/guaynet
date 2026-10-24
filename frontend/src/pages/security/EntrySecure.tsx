import React from "react";
import { Alert, Typography } from "antd";

const { Title } = Typography;

const EntrySecure: React.FC = () => (
  <div style={{ padding: 24 }}>
    <Title level={3}>Entrada Segura</Title>
    <Alert type="info" message="Disponible en Etapa 2" showIcon />
  </div>
);

export default EntrySecure;

import { useState } from "react";
import { useNavigate, useOutletContext } from "react-router-dom";
import { Button, Form, Input, Typography, message } from "antd";
import { portalApi } from "@/services/api";
import { PortalContext, setPortalToken } from "./PortalLayout";
import type { PortalClient } from "./PortalLayout";

export default function PortalLogin() {
  const navigate = useNavigate();
  const { setClient } = useOutletContext<{ setClient: (c: PortalClient) => void }>();
  const [loading, setLoading] = useState(false);

  async function handleLogin(values: { email: string; password: string }) {
    setLoading(true);
    try {
      const { access_token, client } = await portalApi.login(values.email, values.password);
      setPortalToken(access_token);
      setClient(client);
      PortalContext.client = client;
      navigate("/portal");
    } catch {
      message.error("Email o contraseña incorrectos");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      minHeight: "100dvh", display: "flex", alignItems: "center", justifyContent: "center",
      background: "linear-gradient(135deg, #1677ff 0%, #0958d9 100%)",
      padding: 16,
    }}>
      <div style={{
        background: "#fff", borderRadius: 16, padding: 32,
        width: "100%", maxWidth: 360,
        boxShadow: "0 8px 32px rgba(0,0,0,.18)",
      }}>
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <div style={{ fontSize: 40, marginBottom: 8 }}>🌐</div>
          <Typography.Title level={3} style={{ margin: 0 }}>Portal de Clientes</Typography.Title>
          <Typography.Text type="secondary">Guaynet WISP</Typography.Text>
        </div>

        <Form layout="vertical" onFinish={handleLogin}>
          <Form.Item name="email" label="Email" rules={[{ required: true, type: "email" }]}>
            <Input size="large" placeholder="tu@email.com" autoComplete="email" />
          </Form.Item>
          <Form.Item name="password" label="Contraseña" rules={[{ required: true }]}>
            <Input.Password size="large" placeholder="Contraseña" autoComplete="current-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={loading} block size="large">
            Ingresar
          </Button>
        </Form>

        <Typography.Text type="secondary" style={{ display: "block", textAlign: "center", marginTop: 16, fontSize: 12 }}>
          ¿No tenés acceso? Contactá a tu proveedor.
        </Typography.Text>
      </div>
    </div>
  );
}

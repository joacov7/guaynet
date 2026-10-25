import { useState } from "react";
import { useNavigate, useOutletContext } from "react-router-dom";
import { Button, Form, Input, Typography, message } from "antd";
import { LockOutlined, UserOutlined } from "@ant-design/icons";
import { authApi } from "@/services/api";
import { TechContext } from "./TechLayout";

const { Title, Text } = Typography;

export default function TechLogin() {
  const navigate = useNavigate();
  const ctx = useOutletContext<{ setUser: (u: any) => void }>();
  const [loading, setLoading] = useState(false);

  async function handleLogin(values: { username: string; password: string }) {
    setLoading(true);
    try {
      const { access_token } = await authApi.login(values.username, values.password);
      localStorage.setItem("access_token", access_token);
      const user = await authApi.me();
      TechContext.user = user;
      ctx.setUser(user);
      navigate("/tech/tickets", { replace: true });
    } catch {
      message.error("Usuario o contraseña incorrectos");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      minHeight: "100dvh",
      background: "linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%)",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      padding: 24,
    }}>
      <div style={{
        width: "100%",
        maxWidth: 360,
        background: "#fff",
        borderRadius: 16,
        padding: 32,
        boxShadow: "0 20px 60px rgba(0,0,0,.3)",
      }}>
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <div style={{ fontSize: 48, marginBottom: 8 }}>🔧</div>
          <Title level={3} style={{ margin: 0 }}>Guaynet Técnicos</Title>
          <Text type="secondary">Acceso para técnicos de campo</Text>
        </div>

        <Form layout="vertical" onFinish={handleLogin}>
          <Form.Item name="username" rules={[{ required: true, message: "Ingresá tu usuario" }]}>
            <Input
              prefix={<UserOutlined />}
              placeholder="Usuario"
              size="large"
              autoCapitalize="none"
              autoCorrect="off"
            />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: "Ingresá tu contraseña" }]}>
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="Contraseña"
              size="large"
            />
          </Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            loading={loading}
            block
            size="large"
            style={{ marginTop: 8, height: 48, fontSize: 16, borderRadius: 8 }}
          >
            Ingresar
          </Button>
        </Form>
      </div>
    </div>
  );
}

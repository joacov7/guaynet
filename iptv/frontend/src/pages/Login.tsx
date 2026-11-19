import { useState } from "react";
import { Card, Form, Input, Button, Tabs, Typography, message } from "antd";
import { UserOutlined, LockOutlined, NumberOutlined } from "@ant-design/icons";
import { authApi } from "../services/api";

const { Title } = Typography;

function decodeRole(token: string): string {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return payload.role ?? "viewer";
  } catch {
    return "viewer";
  }
}

export default function Login({ onLogin }: { onLogin: (role: string) => void }) {
  const [loading, setLoading] = useState(false);

  async function handlePassword(values: { username: string; password: string }) {
    setLoading(true);
    try {
      const { data } = await authApi.login(values.username, values.password);
      localStorage.setItem("iptv_token", data.access_token);
      const role = decodeRole(data.access_token);
      localStorage.setItem("iptv_role", role);
      onLogin(role);
    } catch {
      message.error("Credenciales incorrectas");
    } finally {
      setLoading(false);
    }
  }

  async function handleCode(values: { code: string }) {
    setLoading(true);
    try {
      const { data } = await authApi.loginCode(values.code);
      localStorage.setItem("iptv_token", data.access_token);
      localStorage.setItem("iptv_role", "viewer");
      onLogin("viewer");
    } catch {
      message.error("Código inválido o inactivo");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#0a0a0a" }}>
      <Card style={{ width: 380, background: "#141414", border: "1px solid #303030" }}>
        <Title level={3} style={{ color: "#fff", textAlign: "center", marginBottom: 24 }}>
          IPTV
        </Title>
        <Tabs
          defaultActiveKey="code"
          centered
          items={[
            {
              key: "code",
              label: "Código de acceso",
              children: (
                <Form onFinish={handleCode} layout="vertical">
                  <Form.Item name="code" rules={[{ required: true, message: "Ingresa tu código" }]}>
                    <Input
                      prefix={<NumberOutlined />}
                      placeholder="Código de acceso"
                      size="large"
                      style={{ textTransform: "uppercase" }}
                      onChange={(e) => e.target.value = e.target.value.toUpperCase()}
                    />
                  </Form.Item>
                  <Button type="primary" htmlType="submit" block size="large" loading={loading}>
                    Ingresar
                  </Button>
                </Form>
              ),
            },
            {
              key: "password",
              label: "Administrador",
              children: (
                <Form onFinish={handlePassword} layout="vertical">
                  <Form.Item name="username" rules={[{ required: true }]}>
                    <Input prefix={<UserOutlined />} placeholder="Usuario" size="large" />
                  </Form.Item>
                  <Form.Item name="password" rules={[{ required: true }]}>
                    <Input.Password prefix={<LockOutlined />} placeholder="Contraseña" size="large" />
                  </Form.Item>
                  <Button type="primary" htmlType="submit" block size="large" loading={loading}>
                    Ingresar
                  </Button>
                </Form>
              ),
            },
          ]}
        />
      </Card>
    </div>
  );
}

import { useCallback, useEffect, useState } from "react";
import { Alert, App as AntApp, Button, Popconfirm, Result, Spin, notification } from "antd";
import axios from "axios";
import Portal from "@/pages/Portal";
import PairScreen from "./PairScreen";
import { clearCredential, loadCredential, saveCredential, setupPush } from "./native";

const API_BASE = import.meta.env.VITE_API_BASE_URL;

function useDeviceAuth(credential: string | null) {
  useEffect(() => {
    if (credential) axios.defaults.headers.common.Authorization = `Device ${credential}`;
    else delete axios.defaults.headers.common.Authorization;
  }, [credential]);
}

export default function MobileApp() {
  const [credential, setCredential] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [pushState, setPushState] = useState<"off" | "on" | "denied">("off");

  useDeviceAuth(credential);

  const unlinkLocally = useCallback(async (msg: string | null) => {
    await clearCredential();
    delete axios.defaults.headers.common.Authorization;
    setCredential(null);
    setNotice(msg);
  }, []);

  useEffect(() => {
    if (API_BASE) axios.defaults.baseURL = API_BASE;
    const id = axios.interceptors.response.use(
      (r) => r,
      async (error) => {
        if (error.response?.status === 401 && error.response.headers?.["x-device-revoked"] === "1") {
          await unlinkLocally("Este teléfono fue desvinculado. Volvé a vincularlo para seguir usando la app.");
        }
        return Promise.reject(error);
      },
    );
    loadCredential().then((c) => {
      if (c) axios.defaults.headers.common.Authorization = `Device ${c}`;
      setCredential(c);
      setReady(true);
    });
    return () => axios.interceptors.response.eject(id);
  }, [unlinkLocally]);

  useEffect(() => {
    if (!credential) return;
    setupPush(
      (token) => {
        axios.put("/api/v1/mobile/push-token", { push_token: token }).catch(() => {});
      },
      (title, body) => notification.warning({ message: title, description: body, duration: 0 }),
    )
      .then((ok) => setPushState(ok ? "on" : "denied"))
      .catch(() => setPushState("denied"));
  }, [credential]);

  if (!API_BASE) {
    return (
      <Result
        status="error"
        title="App sin configurar"
        subTitle="Falta VITE_API_BASE_URL en la compilación de la app."
      />
    );
  }

  if (!ready) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "100vh" }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!credential) {
    return (
      <PairScreen
        notice={notice}
        onPaired={async (c) => {
          await saveCredential(c);
          axios.defaults.headers.common.Authorization = `Device ${c}`;
          setNotice(null);
          setCredential(c);
        }}
      />
    );
  }

  return (
    <AntApp>
      {pushState === "denied" && import.meta.env.VITE_PUSH_ENABLED === "true" && (
        <Alert
          type="warning"
          banner
          message="Las notificaciones están desactivadas: no vas a recibir alertas en este teléfono."
        />
      )}
      <Portal appMode />
      <div style={{ textAlign: "center", padding: "0 16px 32px" }}>
        <Popconfirm
          title="¿Desvincular este teléfono?"
          description="Dejará de recibir alertas hasta que lo vuelvas a vincular."
          okText="Desvincular"
          cancelText="Cancelar"
          onConfirm={async () => {
            await axios.delete("/api/v1/mobile/device").catch(() => {});
            await unlinkLocally(null);
          }}
        >
          <Button type="link" danger size="small">Desvincular este teléfono</Button>
        </Popconfirm>
      </div>
    </AntApp>
  );
}

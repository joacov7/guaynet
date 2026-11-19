import React from "react";
import ReactDOM from "react-dom/client";
import { ConfigProvider } from "antd";
import esES from "antd/locale/es_ES";
import dayjs from "dayjs";
import "dayjs/locale/es";
import MobileApp from "./MobileApp";

dayjs.locale("es");

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider locale={esES} theme={{ token: { colorPrimary: "#1677ff", borderRadius: 6 } }}>
      <MobileApp />
    </ConfigProvider>
  </React.StrictMode>,
);

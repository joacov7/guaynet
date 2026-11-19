import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "ar.com.guaynet.seguridad",
  appName: "Guaynet Seguridad",
  webDir: "dist-app",
  android: {
    // The API must be served over HTTPS; never allow cleartext in release builds.
    allowMixedContent: false,
  },
  plugins: {
    PushNotifications: {
      presentationOptions: ["badge", "sound", "alert"],
    },
  },
};

export default config;

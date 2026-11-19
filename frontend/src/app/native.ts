import { Capacitor } from "@capacitor/core";
import { Preferences } from "@capacitor/preferences";
import { PushNotifications } from "@capacitor/push-notifications";

const CREDENTIAL_KEY = "device_credential";

export const isNative = () => Capacitor.isNativePlatform();

// Push needs Firebase (google-services.json) in the Android project; calling
// register() without it crashes the app, so it is opt-in at build time.
export const pushEnabled = () => isNative() && import.meta.env.VITE_PUSH_ENABLED === "true";

export async function loadCredential(): Promise<string | null> {
  const { value } = await Preferences.get({ key: CREDENTIAL_KEY });
  return value;
}

export async function saveCredential(value: string): Promise<void> {
  await Preferences.set({ key: CREDENTIAL_KEY, value });
}

export async function clearCredential(): Promise<void> {
  await Preferences.remove({ key: CREDENTIAL_KEY });
}

/**
 * Creates the notification channels, asks for permission and registers with FCM.
 * Returns false when push is disabled or the user denied permission.
 */
export async function setupPush(
  onToken: (token: string) => void,
  onForegroundAlert: (title: string, body: string) => void,
): Promise<boolean> {
  if (!pushEnabled()) return false;

  // Channel ids must match the backend (app/services/security/push.py)
  await PushNotifications.createChannel({
    id: "alarmas",
    name: "Alarmas",
    description: "Alertas de seguridad de tu propiedad",
    importance: 5,
    visibility: 1,
    vibration: true,
    lights: true,
  });
  await PushNotifications.createChannel({
    id: "general",
    name: "Avisos",
    description: "Avisos generales del servicio",
    importance: 3,
  });

  let perm = await PushNotifications.checkPermissions();
  if (perm.receive === "prompt" || perm.receive === "prompt-with-rationale") {
    perm = await PushNotifications.requestPermissions();
  }
  if (perm.receive !== "granted") return false;

  await PushNotifications.removeAllListeners();
  await PushNotifications.addListener("registration", (t) => onToken(t.value));
  await PushNotifications.addListener("registrationError", (e) => console.warn("Push registration error", e.error));
  await PushNotifications.addListener("pushNotificationReceived", (n) => onForegroundAlert(n.title ?? "", n.body ?? ""));
  await PushNotifications.register();
  return true;
}

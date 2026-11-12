# Guaynet Smart Gateway Agent (MVP)

Agente local para una instalación de Home Assistant. Descubre dispositivos,
áreas y entidades; envía heartbeat e inventario a Guaynet Smart. Solo realiza
conexiones salientes: no abre puertos ni publica Home Assistant en Internet.

## Alcance de esta primera versión

- Lee estados mediante la REST API local de Home Assistant.
- Lee los registros de dispositivos, entidades y áreas mediante WebSocket.
- Envía `POST /smart/gateway/heartbeat` y `PUT /smart/gateway/inventory`.
- Reintenta en el siguiente ciclo cuando falla una conexión.
- Escucha `state_changed` y agrupa ráfagas para sincronizar el inventario.
- No ejecuta servicios ni controla dispositivos todavía.
- No implementa cola persistente offline: el estado actual se recupera en la
  siguiente sincronización. Home Assistant sigue funcionando localmente.

## Requisitos

- Python 3.11 o superior.
- Home Assistant accesible desde el equipo donde corre el agente.
- Un Long-Lived Access Token de Home Assistant.
- Credencial de gateway creada desde Guaynet Smart (se muestra una sola vez).
- URL HTTPS de la API Guaynet accesible desde la instalación.

## Configuración

Desde esta carpeta, crear un entorno virtual e instalar dependencias:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Configurar las variables en el entorno del proceso. No guardar tokens en Git:

| Variable | Ejemplo | Descripción |
|---|---|---|
| `HA_URL` | `http://homeassistant.local:8123` | URL local de Home Assistant |
| `HA_TOKEN` | — | Long-Lived Access Token de Home Assistant |
| `GUAYNET_API_BASE_URL` | `https://api.ejemplo.com/api/v1` | Base API, sin `/smart` |
| `GUAYNET_GATEWAY_TOKEN` | — | Credencial de gateway emitida por Guaynet |
| `GATEWAY_EXTERNAL_ID` | UUID estable | Identificador externo opcional; si se omite se genera uno al iniciar |
| `SYNC_INTERVAL_SECONDS` | `300` | Intervalo de sincronización (mínimo 30 s) |
| `LOG_LEVEL` | `INFO` | Nivel de log |

Ejecutar manualmente:

```bash
python guaynet_gateway_agent.py
```

## Límites y seguridad

- El token de gateway se envía únicamente en HTTPS hacia Guaynet.
- El token de Home Assistant se usa únicamente contra la URL local configurada.
- Los logs no imprimen tokens, cabeceras ni cuerpos de respuesta.
- No configurar port forwarding para Home Assistant ni publicar el puerto 8123.
- El agente no debe ejecutarse con privilegios de administrador si no son
  necesarios.
- La API actual admite hasta 500 dispositivos y 2000 entidades por sincronización.
- Esta versión no elimina del backend dispositivos que ya no aparecen en un
  snapshot; la política de baja/ausencia debe definirse antes de implementarla.

## Prueba aislada

Primero validar sintaxis y dependencias en un entorno de prueba. Después usar
una instalación de Home Assistant de laboratorio y una instalación Smart de
prueba. No usar la credencial de producción para ensayos. No instalar como
servicio ni iniciar en el servidor de producción hasta completar la validación.

## Próximos pasos

1. Pruebas unitarias con respuestas HA simuladas.
2. Prueba de integración contra HA de laboratorio y API Smart de prueba.
3. Cola local persistente y reintentos con backoff.
4. Sincronización incremental de estados, sin reenviar todo el inventario ante
   cada cambio.
5. Canal de comandos salientes autorizado, con permisos y auditoría.

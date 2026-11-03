# Centro de control de infraestructura Ubiquiti

## Objetivo

Centralizar en Guaynet la observabilidad y la administración de infraestructura Ubiquiti sin mezclar protocolos ni ejecutar cambios remotos por defecto. La primera entrega debe ser de solo lectura y convivir con el módulo actual.

## Familias que deben modelarse por separado

| Familia | Ejemplos | Integración prevista |
|---|---|---|
| airMAX / airOS | LiteBeam, NanoBeam, PowerBeam, Rocket Prism | API HTTP de airOS y, cuando corresponda, SSH restringido |
| UniFi Network | Access points, switches y gateways UniFi | API del controlador UniFi Network; no tratar cada equipo como si fuera airOS |
| EdgeMAX | EdgeSwitch 8 150W y otros EdgeSwitch | SNMP/SSH/API según modelo y firmware; confirmar capacidades antes de implementar escritura |
| UISP | Sitios, radios y CPE gestionados por UISP | API UISP, si está disponible y autorizada |

## Separación de conceptos

- **Dispositivo:** equipo físico con fabricante, modelo, MAC, IP de administración, firmware, ubicación y estado.
- **Controlador:** servicio UniFi Network que administra uno o más dispositivos. Sus credenciales y URL pertenecen al controlador, no deben duplicarse en cada AP/switch.
- **Conexión/integración:** adaptador y credenciales cifradas para consultar una familia o controlador.
- **Histórico:** muestras fechadas de métricas y eventos. No sobrescribir la última lectura como única fuente de información.
- **Relaciones:** controlador → dispositivos; MikroTik/sitio → dispositivos; dispositivo → clientes/abonados cuando la identidad esté confirmada.

## Primera entrega: inventario y monitoreo de solo lectura

1. Inventario unificado con filtros por familia, modelo, ubicación, controlador, estado y última lectura.
2. Identificación de dispositivos por MAC normalizada. La IP es un atributo mutable y no debe ser clave de identidad.
3. Lecturas de estado, uptime, firmware y métricas que el adaptador realmente soporte.
4. Para UniFi: inventario, estado de adopción, AP/switch/gateway, clientes conectados y eventos disponibles desde el controlador.
5. Para EdgeSwitch: modelo, firmware, estado de puertos, velocidad/duplex, contadores RX/TX y PoE solo cuando el protocolo y firmware lo expongan.
6. Para airOS: conservar las consultas existentes, registrando explícitamente qué métricas no están disponibles en cada versión/modelo.
7. Historial de consultas y errores por adaptador, para distinguir equipo caído, credenciales inválidas, timeout y función no soportada.

## Diseño técnico propuesto

- Mantener los endpoints actuales de airOS durante la transición.
- Introducir una interfaz común de adaptadores de solo lectura: `identify`, `get_status`, `get_inventory` y `get_metrics`.
- Implementar adaptadores independientes: `AirOSAdapter`, `UniFiNetworkAdapter`, `EdgeMaxAdapter` y, en una etapa posterior, `UISPAdapter`.
- Crear entidades de controlador separadas de dispositivos; no representar un controlador UniFi como si fuera un AP.
- Guardar secretos cifrados y nunca devolverlos en respuestas API ni logs.
- Ejecutar sondeos en segundo plano con límites de concurrencia, timeout y backoff. La interfaz consulta los datos almacenados, no espera a que cientos de equipos respondan en una petición web.
- Registrar cada lectura con timestamp, origen, resultado y capacidades disponibles.

## Seguridad y operación

- Fase inicial estrictamente de solo lectura.
- No hacer descubrimientos masivos ni escaneos de subred automáticamente.
- No enviar comandos SSH arbitrarios desde la interfaz.
- No cambiar canales, potencia, VLAN, SSID, PoE, firmware ni reiniciar equipos en la primera entrega.
- Toda futura acción de escritura requerirá permiso específico, confirmación, auditoría y validación del impacto.
- No desactivar la verificación TLS ni aceptar claves SSH desconocidas silenciosamente.
- Probar primero en `guaynet-test`; no desplegar ni migrar producción desde esta rama.

## Información que falta antes de implementar cada adaptador

- UniFi: tipo/versión del controlador, URL accesible desde el backend y método de autenticación soportado.
- EdgeMAX: modelos y versiones de firmware adicionales, SNMP habilitado o no, y credenciales/protocolo de solo lectura disponibles.
- airMAX: inventario real de modelos y versiones airOS.
- UISP: confirmar si existe instancia propia y acceso API habilitado.

## Orden de implementación

1. Modelo de datos de controladores e inventario, con migración reversible.
2. Adaptador UniFi Network de solo lectura contra un controlador de prueba.
3. Adaptador EdgeMAX de solo lectura, empezando por información del switch y estado de puertos.
4. Normalización de métricas e históricos.
5. Vista de operaciones unificada y alertas.
6. Diagnóstico correlacionado por sitio, sector, switch, AP y abonado.
7. Acciones remotas controladas, solo después de validar las fases anteriores.

## Criterio de aceptación

La primera entrega se considera lista cuando Guaynet puede listar dispositivos de cada familia sin confundir sus protocolos, identificar controlador y ubicación, mostrar la última lectura con su timestamp y explicar claramente los datos no disponibles, sin modificar la configuración de ningún equipo.

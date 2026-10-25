import { Collapse, Tag, Typography } from "antd";
import {
  AlertOutlined,
  ApartmentOutlined,
  AreaChartOutlined,
  AuditOutlined,
  BarChartOutlined,
  BellOutlined,
  ClusterOutlined,
  CustomerServiceOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  EnvironmentOutlined,
  FileTextOutlined,
  GlobalOutlined,
  LockOutlined,
  MonitorOutlined,
  SafetyOutlined,
  SettingOutlined,
  SwapOutlined,
  TagsOutlined,
  TeamOutlined,
  ToolOutlined,
  UserOutlined,
  WifiOutlined,
} from "@ant-design/icons";

const { Title, Text, Paragraph } = Typography;

interface Module {
  key: string;
  icon: React.ReactNode;
  label: string;
  summary: string;
  admin?: boolean;
  content: React.ReactNode;
}

interface Group {
  label: string;
  modules: Module[];
}

const GROUPS: Group[] = [
  {
    label: "General",
    modules: [
      {
        key: "dashboard",
        icon: <DashboardOutlined />,
        label: "Dashboard",
        summary: "Vista general del estado del negocio y la red en tiempo real.",
        content: (
          <>
            <Paragraph>La pantalla de inicio. Detectá de un vistazo si algo requiere atención antes de arrancar el día.</Paragraph>
            <ul>
              <li><Text strong>Clientes activos / suspendidos / cancelados</Text> — conteo rápido del estado de la cartera.</li>
              <li><Text strong>Facturación</Text> — ingresos del mes actual vs. mes anterior, facturas pendientes y vencidas.</li>
              <li><Text strong>Routers</Text> — cuántos están online y offline, listado por estado.</li>
              <li><Text strong>Alarmas activas</Text> — acceso rápido a problemas de red sin resolver.</li>
            </ul>
          </>
        ),
      },
    ],
  },
  {
    label: "Clientes y Planes",
    modules: [
      {
        key: "clientes",
        icon: <TeamOutlined />,
        label: "Clientes",
        summary: "Gestión completa de la cartera de clientes del WISP.",
        content: (
          <>
            <Paragraph><Text strong>Qué se puede hacer:</Text></Paragraph>
            <ul>
              <li>Crear, editar y eliminar clientes con datos personales, dirección e IP asignada.</li>
              <li>Asignar plan y router a cada cliente.</li>
              <li>Cambiar estado: <Tag color="green">Activo</Tag> <Tag color="orange">Suspendido</Tag> <Tag color="red">Cancelado</Tag>. Al suspender, la queue en MikroTik se deshabilita automáticamente.</li>
              <li>Sincronizar con MikroTik — crea o actualiza la queue de ancho de banda en el router.</li>
              <li>Ver historial de facturas y pagos desde el detalle del cliente.</li>
            </ul>
            <Paragraph type="secondary" style={{ marginTop: 12, fontSize: 13 }}>
              💡 El campo <Text strong>IP</Text> debe coincidir con la IP real del cliente en la red. Si cambia, el sistema la detecta por MAC desde Monitoreo y te ofrece actualizarla.
            </Paragraph>
          </>
        ),
      },
      {
        key: "planes",
        icon: <TagsOutlined />,
        label: "Planes",
        summary: "Definición de los planes de servicio con velocidades y precios.",
        content: (
          <>
            <Paragraph><Text strong>Cada plan contiene:</Text></Paragraph>
            <ul>
              <li><Text strong>Velocidad</Text>: bajada y subida en Mbps (ej: 10 / 2 Mbps).</li>
              <li><Text strong>Burst</Text>: velocidad de ráfaga temporaria para usuarios con poco uso acumulado.</li>
              <li><Text strong>Precio mensual</Text>: se usa al generar facturas.</li>
              <li><Text strong>Max-limit MikroTik</Text>: string exacto para la queue (ej: <Text code>10M/2M</Text>).</li>
            </ul>
            <Paragraph style={{ marginTop: 12, fontSize: 13 }}>
              Al cambiar el plan de un cliente, sincronizá manualmente con MikroTik para que tome el nuevo límite.
            </Paragraph>
          </>
        ),
      },
      {
        key: "zonas",
        icon: <EnvironmentOutlined />,
        label: "Zonas",
        summary: "Agrupación geográfica de clientes para organizar la red por sectores.",
        content: (
          <>
            <ul>
              <li>Dividir la red en sectores o NAPs (ej: Zona Norte, Zona Industrial).</li>
              <li>Cada zona tiene un <Text strong>color</Text> para identificarla en el Mapa de Red.</li>
              <li>Se pueden asociar a un router específico.</li>
              <li>Los clientes se asignan a una zona para facilitar la organización y los reportes.</li>
            </ul>
            <Paragraph type="secondary" style={{ marginTop: 12, fontSize: 13 }}>
              💡 Usar zonas ayuda a filtrar clientes por área geográfica y a identificar rápidamente qué sector afecta una falla.
            </Paragraph>
          </>
        ),
      },
    ],
  },
  {
    label: "Red",
    modules: [
      {
        key: "routers",
        icon: <ApartmentOutlined />,
        label: "Routers",
        summary: "Gestión y monitoreo de los routers MikroTik del WISP.",
        content: (
          <>
            <Paragraph><Text strong>Qué se puede hacer:</Text></Paragraph>
            <ul>
              <li>Agregar y editar routers: IP/host, puerto API (8728), usuario y contraseña.</li>
              <li>Ver estado: Online / Offline con timestamp del último acceso exitoso.</li>
              <li>Panel de utilización con CPU, RAM, disco flash, interfaces con tráfico en tiempo real.</li>
              <li>Gestionar queues directamente en el router.</li>
            </ul>
            <Paragraph><Text strong>Recursos del sistema:</Text></Paragraph>
            <ul>
              <li><Text strong>Flash</Text>: espacio libre. Un flash lleno puede causar fallos en logs o scripts.</li>
              <li><Text strong>RAM</Text>: alta ocupación puede indicar demasiadas conexiones.</li>
              <li><Text strong>CPU</Text>: carga alta sostenida genera una alarma automática.</li>
            </ul>
            <Paragraph type="warning" style={{ marginTop: 12, fontSize: 13, color: "#d46b08" }}>
              ⚠️ Si el router no conecta, verificá que la API esté habilitada: en MikroTik ir a <Text code>IP → Services → api</Text>.
            </Paragraph>
          </>
        ),
      },
      {
        key: "monitoreo",
        icon: <MonitorOutlined />,
        label: "Monitoreo",
        summary: "Clientes online en tiempo real y estadísticas de ancho de banda por queue.",
        content: (
          <>
            <Paragraph><Text strong>Pestaña: Clientes online</Text></Paragraph>
            <ul>
              <li>Lista de IPs en la tabla ARP del router, con estado Conectado / Desconectado.</li>
              <li>Identifica a qué cliente pertenece cada IP.</li>
              <li>Si un cliente cambió de IP (detectado por MAC), muestra la nueva IP con botón para actualizarla en el sistema y en MikroTik.</li>
            </ul>
            <Paragraph><Text strong>Pestaña: Ancho de banda</Text></Paragraph>
            <ul>
              <li>Queues del router con bytes descargados y subidos acumulados.</li>
              <li>Si una queue existe en el sistema pero no en el router, aparece con ⚠️ y botón Sync para recrearla.</li>
              <li>Se refresca cada 30 segundos automáticamente.</li>
            </ul>
          </>
        ),
      },
      {
        key: "alarmas",
        icon: <BellOutlined />,
        label: "Alarmas",
        summary: "Alertas automáticas generadas por el sistema ante eventos de red.",
        content: (
          <>
            <Paragraph><Text strong>Tipos de alarmas:</Text></Paragraph>
            <ul>
              <li><Text strong>Router offline</Text>: el router dejó de responder al chequeo periódico.</li>
              <li><Text strong>CPU alto</Text>: el CPU del router supera el umbral configurado.</li>
              <li><Text strong>WAN caída</Text>: una interfaz WAN monitoreada dejó de tener tráfico.</li>
              <li><Text strong>Uplink saturado</Text>: el enlace de subida está cerca del límite.</li>
              <li><Text strong>RAM alta</Text>: la RAM del router está casi llena.</li>
            </ul>
            <Paragraph type="secondary" style={{ marginTop: 12, fontSize: 13 }}>
              💡 Las alarmas se generan automáticamente. <Tag color="red">Activa</Tag> = problema vigente. <Tag color="green">Resuelta</Tag> = condición normalizada.
            </Paragraph>
          </>
        ),
      },
      {
        key: "wan",
        icon: <SwapOutlined />,
        label: "Gestión WAN",
        summary: "Control de interfaces WAN: encendido/apagado, consumo, balanceo y horarios.",
        content: (
          <>
            <Paragraph><Text strong>Interfaces WAN:</Text></Paragraph>
            <ul>
              <li>Registrar cada interfaz WAN (fibra, 4G, backup) con su nombre en MikroTik.</li>
              <li><Text strong>Habilitar / Deshabilitar</Text>: activa o corta la interfaz directamente en el router.</li>
              <li><Text strong>Cap de datos</Text>: límite mensual en GB. Al alcanzarlo, la interfaz se deshabilita automáticamente.</li>
              <li><Text strong>Peso de balanceo</Text>: controla qué proporción del tráfico va por cada WAN en balanceo PCC.</li>
            </ul>
            <Paragraph><Text strong>Horarios:</Text></Paragraph>
            <ul>
              <li>Programar encendido o apagado de una WAN en horarios específicos.</li>
              <li>Se crean como scripts en el scheduler de MikroTik y se ejecutan a la hora configurada.</li>
              <li>Se pueden editar o eliminar desde la misma interfaz.</li>
            </ul>
          </>
        ),
      },
    ],
  },
  {
    label: "Infraestructura",
    modules: [
      {
        key: "firewall",
        icon: <SafetyOutlined />,
        label: "Firewall & QoS",
        summary: "Vista de reglas de firewall, mangle y colas PCQ del router MikroTik.",
        content: (
          <>
            <ul>
              <li><Text strong>Reglas de Firewall</Text>: chains forward/input/output con bytes y paquetes procesados.</li>
              <li><Text strong>Reglas Mangle</Text>: marcado de paquetes y conexiones para QoS y PCC.</li>
              <li><Text strong>PCQ</Text>: colas Per Connection Queue para QoS avanzado.</li>
            </ul>
            <Paragraph type="secondary" style={{ marginTop: 12, fontSize: 13 }}>
              💡 Esta sección es de solo lectura. Las reglas se gestionan desde el router o mediante Gestión WAN.
            </Paragraph>
          </>
        ),
      },
      {
        key: "ubiquiti",
        icon: <WifiOutlined />,
        label: "Ubiquiti",
        summary: "Gestión de radios y APs Ubiquiti AirMax y UniFi.",
        content: (
          <>
            <Paragraph><Text strong>Dispositivos soportados:</Text> AirMax AP/Station, AirMax AC AP/Station, UniFi AP/Switch/Gateway.</Paragraph>
            <Paragraph><Text strong>Qué se puede ver:</Text></Paragraph>
            <ul>
              <li>Estado Online/Offline, modelo, firmware, uptime, CPU y RAM.</li>
              <li>Configuración wireless: modo, SSID, frecuencia, ancho de canal y potencia.</li>
              <li>Info de enlace: señal, ruido, CCQ, tasas TX/RX y distancia al par.</li>
              <li>Estaciones asociadas al AP con señal y tasa de cada una.</li>
              <li>Survey de frecuencias: escaneo de redes vecinas y recomendación de canal menos congestionado.</li>
            </ul>
          </>
        ),
      },
      {
        key: "mapa",
        icon: <GlobalOutlined />,
        label: "Mapa de Red",
        summary: "Visualización geográfica de clientes, routers y dispositivos Ubiquiti.",
        content: (
          <>
            <ul>
              <li>Pines en el mapa para cada elemento con coordenadas cargadas.</li>
              <li>Color del pin según estado: verde = online, rojo = offline.</li>
              <li>Clic en un pin: nombre, estado, IP y enlace al detalle.</li>
            </ul>
            <Paragraph style={{ marginTop: 12, fontSize: 13 }}>
              Para que aparezcan en el mapa, completar <Text strong>Latitud</Text> y <Text strong>Longitud</Text> en el formulario de cada cliente, router o dispositivo (se obtienen desde Google Maps con clic derecho).
            </Paragraph>
          </>
        ),
      },
      {
        key: "ippool",
        icon: <ClusterOutlined />,
        label: "Pool de IPs",
        summary: "Visualización del uso de IPs dentro de una subred.",
        content: (
          <>
            <ul>
              <li>Ingresás una subred (ej: <Text code>192.168.1.0/24</Text>) y muestra todas las IPs del rango.</li>
              <li>Marca cada IP como libre o usada, indicando a qué cliente está asignada.</li>
              <li>Muestra totales: hosts totales, usados y libres.</li>
            </ul>
            <Paragraph type="secondary" style={{ marginTop: 12, fontSize: 13 }}>
              💡 Útil para saber qué IPs están disponibles antes de dar de alta un cliente nuevo.
            </Paragraph>
          </>
        ),
      },
      {
        key: "bandwidth",
        icon: <AreaChartOutlined />,
        label: "Ancho de Banda",
        summary: "Historial de consumo de bajada y subida por cliente a lo largo del tiempo.",
        content: (
          <>
            <ul>
              <li>Gráficas de consumo histórico por cliente o queue con muestras guardadas periódicamente.</li>
              <li>Permite ver picos de consumo y evolución del uso en el tiempo.</li>
            </ul>
            <Paragraph style={{ marginTop: 12, fontSize: 13 }}>
              <Text strong>Diferencia con Monitoreo:</Text> Monitoreo muestra el acumulado desde el último reset del router (tiempo real). Ancho de Banda guarda muestras históricas a intervalos regulares para ver tendencias.
            </Paragraph>
          </>
        ),
      },
    ],
  },
  {
    label: "Facturación",
    modules: [
      {
        key: "facturacion",
        icon: <FileTextOutlined />,
        label: "Facturación",
        summary: "Emisión de facturas, registro de pagos y control de deuda.",
        content: (
          <>
            <Paragraph><Text strong>Facturas:</Text></Paragraph>
            <ul>
              <li>Crear facturas por cliente con período, monto y fecha de vencimiento.</li>
              <li><Text strong>Generación masiva</Text>: genera facturas para todos los clientes activos de un período con un clic.</li>
              <li>Estados: <Tag>Borrador</Tag> <Tag color="blue">Pendiente</Tag> <Tag color="green">Pagada</Tag> <Tag color="red">Vencida</Tag> <Tag>Cancelada</Tag></li>
            </ul>
            <Paragraph><Text strong>Pagos:</Text></Paragraph>
            <ul>
              <li>Registrar pagos parciales o totales en cada factura.</li>
              <li>Métodos: efectivo, transferencia, MercadoPago u otro.</li>
            </ul>
            <Paragraph><Text strong>Clientes vencidos:</Text></Paragraph>
            <ul>
              <li>Vista de morosos con días de mora y monto adeudado. Permite suspender al cliente con un clic.</li>
            </ul>
            <Paragraph type="secondary" style={{ marginTop: 12, fontSize: 13 }}>
              💡 La generación masiva usa el <Text strong>día de facturación</Text> configurado en cada cliente para calcular el vencimiento.
            </Paragraph>
          </>
        ),
      },
      {
        key: "reportes",
        icon: <BarChartOutlined />,
        label: "Reportes",
        summary: "Reportes financieros e históricos del WISP.",
        content: (
          <>
            <ul>
              <li><Text strong>Ingresos por período</Text>: resumen de pagos recibidos en un rango de fechas.</li>
              <li><Text strong>Clientes por estado</Text>: evolución de altas, bajas y suspensiones.</li>
              <li><Text strong>Deuda acumulada</Text>: total adeudado por clientes morosos.</li>
              <li>Reportes exportables para planilla o contabilidad.</li>
            </ul>
          </>
        ),
      },
    ],
  },
  {
    label: "Operaciones",
    modules: [
      {
        key: "soporte",
        icon: <CustomerServiceOutlined />,
        label: "Soporte",
        summary: "Sistema de tickets para gestionar reclamos y consultas de clientes.",
        content: (
          <>
            <ul>
              <li>Crear tickets asociados a un cliente (o sin cliente para temas internos).</li>
              <li>Categorías: conectividad, velocidad, facturación, equipamiento, instalación u otro.</li>
              <li>Prioridad: baja, media o alta.</li>
              <li>Asignar a un técnico del equipo.</li>
              <li>Comentarios internos y seguimiento del historial.</li>
              <li>Estados: <Tag color="blue">Abierto</Tag> <Tag color="orange">En progreso</Tag> <Tag color="green">Resuelto</Tag> <Tag>Cerrado</Tag></li>
            </ul>
          </>
        ),
      },
      {
        key: "workorders",
        icon: <ToolOutlined />,
        label: "Órdenes de Trabajo",
        summary: "Planificación y seguimiento de trabajos en campo para técnicos.",
        content: (
          <>
            <ul>
              <li>Tipos: instalación, reparación, mantenimiento, inspección u otro.</li>
              <li>Se asignan a un técnico con fecha programada y dirección del trabajo.</li>
              <li>Pueden asociarse a un cliente existente.</li>
              <li>Al completar, el técnico registra notas de cierre y puede adjuntar fotos.</li>
              <li>Estados: <Tag>Pendiente</Tag> <Tag color="orange">En progreso</Tag> <Tag color="green">Completado</Tag> <Tag>Cancelado</Tag></li>
            </ul>
          </>
        ),
      },
      {
        key: "inventario",
        icon: <DatabaseOutlined />,
        label: "Inventario",
        summary: "Control de equipamiento: stock, estado y asignación a clientes.",
        content: (
          <>
            <ul>
              <li>Registrar equipos con nombre, categoría, marca, modelo y número de serie.</li>
              <li>Condición: Nuevo, Bueno, Dañado o Descartado.</li>
              <li>Estado: En stock, Asignado, Devuelto o Perdido.</li>
              <li>Asignar un ítem a un cliente para registrar que está en su domicilio.</li>
            </ul>
            <Paragraph type="secondary" style={{ marginTop: 12, fontSize: 13 }}>
              💡 Sirve para llevar control de radios, cables, fuentes y cualquier material que sale del depósito.
            </Paragraph>
          </>
        ),
      },
    ],
  },
  {
    label: "Administración",
    modules: [
      {
        key: "usuarios",
        icon: <UserOutlined />,
        label: "Usuarios",
        summary: "Gestión de cuentas de acceso al sistema.",
        admin: true,
        content: (
          <>
            <ul>
              <li>Crear usuarios con username, email, contraseña y rol (admin o técnico).</li>
              <li>Habilitar o deshabilitar cuentas sin eliminarlas.</li>
              <li>Los <Text strong>administradores</Text> ven todo el sistema.</li>
              <li>Los <Text strong>técnicos</Text> solo ven las secciones que se les otorguen en Permisos.</li>
            </ul>
          </>
        ),
      },
      {
        key: "permisos",
        icon: <SettingOutlined />,
        label: "Permisos",
        summary: "Control de acceso a secciones del sistema por rol.",
        admin: true,
        content: (
          <>
            <ul>
              <li>Los permisos se configuran por <Text strong>rol</Text>, no por usuario individual.</li>
              <li>Para cada sección se puede otorgar <Text strong>Ver</Text> y/o <Text strong>Editar</Text>.</li>
              <li>Los administradores tienen acceso total siempre.</li>
            </ul>
            <Paragraph type="secondary" style={{ marginTop: 12, fontSize: 13 }}>
              💡 Si un técnico no ve una sección en el menú, verificá que su rol tenga habilitado el permiso de <Text strong>Ver</Text> en esa sección.
            </Paragraph>
          </>
        ),
      },
      {
        key: "vpn",
        icon: <LockOutlined />,
        label: "VPN",
        summary: "Gestión de conexiones VPN para acceso remoto a la red.",
        admin: true,
        content: (
          <>
            <ul>
              <li><Text strong>WireGuard</Text>: VPN moderna. Requiere clave pública/privada, IP del túnel y endpoint.</li>
              <li><Text strong>L2TP/IPsec</Text>: VPN tradicional compatible con la mayoría de sistemas operativos.</li>
              <li>Registrar los parámetros de cada conexión VPN para acceso remoto a routers.</li>
            </ul>
          </>
        ),
      },
      {
        key: "auditoria",
        icon: <AuditOutlined />,
        label: "Auditoría",
        summary: "Registro histórico de todas las acciones realizadas en el sistema.",
        content: (
          <>
            <ul>
              <li>Cada acción que crea, modifica o elimina un registro queda guardada con usuario, fecha y detalle.</li>
              <li>Incluye: altas de clientes, cambios de estado, pagos, sincronizaciones con MikroTik, cambios de configuración.</li>
              <li>Permite saber quién hizo cada cambio y cuándo, e investigar problemas operativos.</li>
            </ul>
          </>
        ),
      },
      {
        key: "configuracion",
        icon: <AlertOutlined />,
        label: "Configuración",
        summary: "Parámetros globales del sistema y acciones administrativas.",
        admin: true,
        content: (
          <>
            <ul>
              <li><Text strong>Acción de suspensión</Text>: define si al suspender un cliente se deshabilita su queue en MikroTik, se bloquea su IP en el firewall, o ambas.</li>
              <li><Text strong>Parámetros de notificaciones</Text>: configuración de alertas del sistema.</li>
              <li><Text strong>Datos del WISP</Text>: nombre y datos de contacto para documentos generados.</li>
            </ul>
          </>
        ),
      },
    ],
  },
];

export default function Help() {
  return (
    <div style={{ maxWidth: 820 }}>
      <div style={{ marginBottom: 28 }}>
        <Title level={4} style={{ margin: 0 }}>Ayuda — Guía de módulos</Title>
        <Text type="secondary">Descripción y modo de uso de cada sección del sistema.</Text>
      </div>

      {GROUPS.map((group) => (
        <div key={group.label} style={{ marginBottom: 32 }}>
          <Text
            type="secondary"
            style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase" }}
          >
            {group.label}
          </Text>
          <div style={{ marginTop: 8 }}>
            <Collapse
              size="small"
              items={group.modules.map((mod) => ({
                key: mod.key,
                label: (
                  <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    {mod.icon}
                    <span style={{ fontWeight: 500 }}>{mod.label}</span>
                    {mod.admin && <Tag color="gold" style={{ marginLeft: 4, fontSize: 11 }}>Admin</Tag>}
                    <Text type="secondary" style={{ fontSize: 13, fontWeight: 400, marginLeft: 4 }}>
                      — {mod.summary}
                    </Text>
                  </span>
                ),
                children: (
                  <div style={{ fontSize: 14, lineHeight: 1.65, paddingLeft: 4 }}>
                    {mod.content}
                  </div>
                ),
              }))}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Spin } from "antd";
import { useAuth } from "@/hooks/useAuth";
import MainLayout from "@/components/Layout/MainLayout";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import ClientList from "@/pages/clients/ClientList";
import ClientForm from "@/pages/clients/ClientForm";
import Plans from "@/pages/Plans";
import Routers from "@/pages/Routers";
import Invoices from "@/pages/Invoices";
import Firewall from "@/pages/Firewall";
import Monitoring from "@/pages/Monitoring";
import Ubiquiti from "@/pages/Ubiquiti";
import NetworkMap from "@/pages/NetworkMap";
import AuditLog from "@/pages/AuditLog";
import IpPool from "@/pages/IpPool";
import BandwidthDashboard from "@/pages/BandwidthDashboard";
import Permissions from "@/pages/Permissions";
import Users from "@/pages/Users";
import Vpn from "@/pages/Vpn";
import Settings from "@/pages/Settings";
import Tickets from "@/pages/Tickets";
import Inventory from "@/pages/Inventory";
import Reports from "@/pages/Reports";
import Zones from "@/pages/Zones";
import TechLayout from "@/pages/tech/TechLayout";
import TechLogin from "@/pages/tech/TechLogin";
import TechHome from "@/pages/tech/TechHome";
import TechHistory from "@/pages/tech/TechHistory";
import TechTicket from "@/pages/tech/TechTicket";
import Portal from "@/pages/Portal";
import { PermissionsProvider } from "@/contexts/PermissionsContext";

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return <Spin fullscreen />;
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  const { isAuthenticated, loading } = useAuth();

  if (loading) return <Spin fullscreen />;

  return (
    <PermissionsProvider>
    <BrowserRouter>
      <Routes>
        <Route
          path="/login"
          element={isAuthenticated ? <Navigate to="/" replace /> : <Login />}
        />
        <Route
          path="/"
          element={
            <PrivateRoute>
              <MainLayout />
            </PrivateRoute>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="clients" element={<ClientList />} />
          <Route path="clients/new" element={<ClientForm />} />
          <Route path="clients/:id" element={<ClientForm />} />
          <Route path="plans" element={<Plans />} />
          <Route path="routers" element={<Routers />} />
          <Route path="billing" element={<Invoices />} />
          <Route path="firewall" element={<Firewall />} />
          <Route path="monitoring" element={<Monitoring />} />
          <Route path="ubiquiti" element={<Ubiquiti />} />
          <Route path="map" element={<NetworkMap />} />
          <Route path="audit" element={<AuditLog />} />
          <Route path="ip-pool" element={<IpPool />} />
          <Route path="bandwidth" element={<BandwidthDashboard />} />
          <Route path="permissions" element={<Permissions />} />
          <Route path="users" element={<Users />} />
          <Route path="vpn" element={<Vpn />} />
          <Route path="tickets" element={<Tickets />} />
          <Route path="inventory" element={<Inventory />} />
          <Route path="reports" element={<Reports />} />
          <Route path="zones" element={<Zones />} />
          <Route path="settings" element={<Settings />} />
        </Route>

        {/* Client self-service portal — public, no auth */}
        <Route path="/portal" element={<Portal />} />

        {/* Tech PWA — separate layout, no sidebar */}
        <Route path="/tech" element={<TechLayout />}>
          <Route index element={<Navigate to="/tech/tickets" replace />} />
          <Route path="login" element={<TechLogin />} />
          <Route path="tickets" element={<TechHome />} />
          <Route path="tickets/:id" element={<TechTicket />} />
          <Route path="history" element={<TechHistory />} />
        </Route>
      </Routes>
    </BrowserRouter>
    </PermissionsProvider>
  );
}

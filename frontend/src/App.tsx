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
        </Route>
      </Routes>
    </BrowserRouter>
    </PermissionsProvider>
  );
}

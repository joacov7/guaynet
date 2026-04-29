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

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return <Spin fullscreen />;
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  const { isAuthenticated, loading } = useAuth();

  if (loading) return <Spin fullscreen />;

  return (
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
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

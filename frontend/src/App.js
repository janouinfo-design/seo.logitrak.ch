import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import "@/App.css";

import { AuthProvider } from "@/contexts/AuthContext";
import { SiteProvider } from "@/contexts/SiteContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import Layout from "@/components/Layout";

import Login from "@/pages/Login";
import Register from "@/pages/Register";
import Dashboard from "@/pages/Dashboard";
import Sites from "@/pages/Sites";
import Audit from "@/pages/Audit";
import Generator from "@/pages/Generator";
import Drafts from "@/pages/Drafts";
import DraftDetail from "@/pages/DraftDetail";
import HistoryPage from "@/pages/History";
import Performance from "@/pages/Performance";
import Automation from "@/pages/Automation";
import Billing from "@/pages/Billing";
import Keywords from "@/pages/Keywords";
import Optimizer from "@/pages/Optimizer";
import AIVisibility from "@/pages/AIVisibility";
import KeywordIntelligence from "@/pages/KeywordIntelligence";
import Aide from "@/pages/Aide";

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <SiteProvider>
          <Toaster richColors position="top-right" />
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route
              element={
                <ProtectedRoute>
                  <Layout />
                </ProtectedRoute>
              }
            >
              <Route path="/" element={<Dashboard />} />
              <Route path="/sites" element={<Sites />} />
              <Route path="/audit" element={<Audit />} />
              <Route path="/ai-visibility" element={<AIVisibility />} />
              <Route path="/keywords" element={<Keywords />} />
              <Route path="/keyword-intelligence" element={<KeywordIntelligence />} />
              <Route path="/optimizer" element={<Optimizer />} />
              <Route path="/generator" element={<Generator />} />
              <Route path="/drafts" element={<Drafts />} />
              <Route path="/drafts/:id" element={<DraftDetail />} />
              <Route path="/history" element={<HistoryPage />} />
              <Route path="/performance" element={<Performance />} />
              <Route path="/automation" element={<Automation />} />
              <Route path="/billing" element={<Billing />} />
              <Route path="/aide" element={<Aide />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </SiteProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;

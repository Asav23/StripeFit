import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { MeProvider, ToastProvider } from "./context";
import "./index.css";
import AddPage from "./pages/AddPage";
import AiLogPage from "./pages/AiLogPage";
import DemoCheckoutPage from "./pages/DemoCheckoutPage";
import PlanPage from "./pages/PlanPage";
import ProPage from "./pages/ProPage";
import ProSuccessPage from "./pages/ProSuccessPage";
import ReviewPage from "./pages/ReviewPage";
import TodayPage from "./pages/TodayPage";
import WardrobePage from "./pages/WardrobePage";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <ToastProvider>
        <MeProvider>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<WardrobePage />} />
              <Route path="add" element={<AddPage />} />
              <Route path="review" element={<ReviewPage />} />
              <Route path="today" element={<TodayPage />} />
              <Route path="plan" element={<PlanPage />} />
              <Route path="pro" element={<ProPage />} />
              <Route path="pro/checkout" element={<DemoCheckoutPage />} />
              <Route path="pro/success" element={<ProSuccessPage />} />
              <Route path="ai-log" element={<AiLogPage />} />
              <Route path="*" element={<WardrobePage />} />
            </Route>
          </Routes>
        </MeProvider>
      </ToastProvider>
    </BrowserRouter>
  </StrictMode>,
);

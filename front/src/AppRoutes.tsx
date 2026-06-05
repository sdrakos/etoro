import { Routes, Route } from "react-router-dom";
import App from "./App";
import { ChartView } from "./views/ChartView";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<App />} />
      <Route path="/chart/:instrumentId" element={<ChartView />} />
    </Routes>
  );
}

import { useState } from "react";
import { AppNav, type AppView } from "./components/AppNav";
import { ScreenerView } from "./views/ScreenerView";
import { PortfolioView } from "./views/PortfolioView";

export default function App() {
  const [view, setView] = useState<AppView>("screener");
  return (
    <div className="flex min-h-screen flex-col bg-bg-base text-fg-default">
      <div className="border-b border-border-default bg-bg-base/90">
        <AppNav value={view} onChange={setView} />
      </div>
      {view === "screener" ? <ScreenerView /> : <PortfolioView />}
    </div>
  );
}

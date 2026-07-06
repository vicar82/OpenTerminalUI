import { NavLink } from "react-router-dom";
import { useStockStore } from "../../store/stockStore";
import logo from "../../assets/logo.png";
import { useAlertsStore } from "../../store/alertsStore";
import { UserAccountPanel } from "./UserAccountPanel";

export function Sidebar() {
  const ticker = useStockStore((s) => s.ticker);
  const unreadCount = useAlertsStore((s) => s.unreadCount);
  const nav = [
    { label: "Рынок", path: "/equity/stocks", key: "F1" },
    { label: "Карточка актива", path: "/equity/security", key: "SH", hint: "Исследования" },
    { label: "Экономика", path: "/equity/economics", key: "E", hint: "Macro" },
    { label: "Товары", path: "/equity/commodities", key: "CMDTY", hint: "Macro" },
    { label: "Форекс", path: "/equity/forex", key: "FX", hint: "Macro" },
    { label: "ETF-аналитика", path: "/equity/etf-analytics", key: "ETFA", hint: "Funds" },
    { label: "Облигации", path: "/equity/bonds", key: "BOND", hint: "Fixed Income" },
    { label: "Доходная кривая", path: "/equity/yield-curve", key: "YC", hint: "Fixed Income" },
    { label: "Ротация секторов", path: "/equity/sector-rotation", key: "ROT", hint: "Relative" },
    { label: "Крипто", path: "/equity/crypto", key: "CR", hint: "Digital" },
    { label: "Сравнение", path: "/equity/compare", key: "CMP", hint: "Split View" },
    { label: "Скринер", path: "/equity/screener", key: "F2" },
    { label: "Лидеры", path: "/equity/hotlists", key: "HOT", hint: "Movers" },
    { label: "Инсайдеры", path: "/equity/insider", key: "RU", hint: "Исследования" },
    { label: "Тепловая карта", path: "/equity/heatmap", key: "HM", hint: "Рынок" },
    { label: "Дивиденды", path: "/equity/dividends", key: "DIV", hint: "Income" },
    { label: "Отн. сила", path: "/equity/rs", key: "RS", hint: "Relative" },
    { label: "Панель запуска", path: "/equity/launchpad", key: "LP", hint: "Workspace" },
    { label: "Рабочая станция", path: "/equity/chart-workstation", key: "6", hint: "6 Charts" },
    { label: "Исследования", path: "/equity/research", key: "RES", hint: "Papers" },
    { label: "Мульти-ТФ", path: "/equity/mta", key: "MT", hint: "Multi-TF" },
    { label: "Стакан", path: "/equity/dom", key: "D", hint: "Depth" },
    { label: "Лента", path: "/equity/tape", key: "T", hint: "Time & Sales" },
    { label: "Портфель", path: "/equity/portfolio", key: "F3" },
    { label: "Лаб. портфеля", path: "/equity/portfolio/lab", key: "PLB", hint: "Исследования" },
    { label: "Бумажная торговля", path: "/equity/paper", key: "P" },
    { label: "Кальк. позиции", path: "/equity/position-sizer", key: "PS", hint: "Trading" },
    { label: "Журнал", path: "/equity/journal", key: "J", hint: "Trading" },
    { label: "Наблюдение", path: "/equity/watchlist", key: "F4" },
    { label: "Новости", path: "/equity/news", key: "F5" },
    { label: "Алерты", path: "/equity/alerts", key: "A" },
    { label: "Риск", path: "/equity/risk", key: "R" },
    { label: "Корреляция", path: "/equity/correlation", key: "CR", hint: "Риски" },
    { label: "Стат. лаборатория", path: "/equity/stat-lab", key: "SL", hint: "Quant" },
    { label: "Парный трейдинг", path: "/equity/pair-trading", key: "PT", hint: "Quant" },
    { label: "Ордер-менеджмент", path: "/equity/oms", key: "O" },
    { label: "Операции", path: "/equity/ops", key: "K" },
    { label: "Плагины", path: "/equity/plugins", key: "PL" },
    { label: "Настройки", path: "/equity/settings", key: "F6" },
    { label: "О программе", path: "/equity/stocks/about", key: "F7" },
    { label: "Модельная лаборатория", path: "/backtesting/model-lab", key: "ML", hint: "Backtest" },
    { label: "Кокпит", path: "/equity/cockpit", key: "CP", hint: "Overview" },
    { label: "Бэктестинг", path: "/backtesting", key: "F9" },
  ];

  return (
    <aside className="relative z-30 flex h-full w-48 shrink-0 flex-col border-r border-terminal-border bg-terminal-panel p-0">
      <div className="border-b border-terminal-border bg-terminal-panel px-3 py-2">
        <img src={logo} alt="OpenTerminalUI" className="h-8 w-auto object-contain" />
      </div>
      <div className="border-b border-terminal-border px-3 py-2 text-[11px] text-terminal-muted">
        NSE АНАЛИТИКА АКЦИЙ
      </div>
      <div className="space-y-1 border-b border-terminal-border p-2 text-xs">
        <NavLink to="/" className="block rounded px-2 py-2 text-terminal-muted hover:bg-terminal-bg hover:text-terminal-text">
          Главная
        </NavLink>
        <NavLink
          to={`/fno?symbol=${encodeURIComponent((ticker || "IMOEX").toUpperCase())}`}
          className="block rounded px-2 py-2 text-terminal-muted hover:bg-terminal-bg hover:text-terminal-text"
        >
          Переключиться в F&O {"->"}
        </NavLink>
      </div>
      <nav className="flex-1 space-y-1 overflow-auto p-2 text-xs">
        {nav.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `flex cursor-pointer items-center justify-between rounded px-2 py-2 ${
                isActive
                  ? "bg-terminal-accent/20 text-terminal-accent"
                  : "text-terminal-muted hover:bg-terminal-bg hover:text-terminal-text"
              }`
            }
          >
            <div className="flex flex-col">
              <span>{item.label}</span>
              {(item as any).hint && <span className="text-[8px] text-terminal-accent/70 -mt-0.5 uppercase">{(item as any).hint}</span>}
            </div>
            <span className="text-[10px]">
              {item.path === "/equity/alerts" && unreadCount > 0 ? `${unreadCount}` : item.key}
            </span>
          </NavLink>
        ))}
      </nav>
      <UserAccountPanel />
    </aside>
  );
}

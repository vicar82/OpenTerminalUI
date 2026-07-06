import { useEffect, useMemo, useRef } from "react";

import { useSettingsStore } from "../store/settingsStore";
import { formatMoney } from "../lib/format";
import { useMarketStatus } from "./useStocks";

type MarketStatusPayload = {
  usdRub?: number | null;
  rubUsd?: number | null;
};

function toNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value.replace(/,/g, "").trim());
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

export function useDisplayCurrency() {
  const displayCurrency = useSettingsStore((s) => s.displayCurrency);
  const selectedMarket = useSettingsStore((s) => s.selectedMarket);
  const { data } = useMarketStatus();

  const liveUsdRub = useMemo(() => {
    const payload = (data ?? {}) as MarketStatusPayload;
    const direct = toNumber(payload.usdRub);
    if (direct && direct > 0) return direct;
    const inverse = toNumber(payload.rubUsd);
    if (inverse && inverse > 0) return 1 / inverse;
    return null;
  }, [data]);

  const lastKnownUsdRubRef = useRef<number | null>(null);
  useEffect(() => {
    if (liveUsdRub && liveUsdRub > 0) {
      lastKnownUsdRubRef.current = liveUsdRub;
    }
  }, [liveUsdRub]);

  const usdRub = liveUsdRub ?? lastKnownUsdRubRef.current;
  const isRussiaMarket = selectedMarket === "MOEX";
  const isUsMarket = selectedMarket === "NASDAQ" || selectedMarket === "NYSE";
  const financialUnit = displayCurrency === "USD" ? "M" : "млн";
  const financialDivisor = 1e6;
  const moneySymbol = displayCurrency === "USD" ? "$" : "₽";
  const moneyLocale = displayCurrency === "USD" ? "en-US" : "ru-RU";

  const convertAmount = (value: number): number => {
    if (!Number.isFinite(value)) return value;
    if (isRussiaMarket && displayCurrency === "USD") {
      if (!usdRub || usdRub <= 0) return Number.NaN;
      return value / usdRub;
    }
    if (isUsMarket && displayCurrency === "RUB") {
      if (!usdRub || usdRub <= 0) return Number.NaN;
      return value * usdRub;
    }
    return value;
  };

  const formatDisplayMoney = (value: number): string => {
    const converted = convertAmount(value);
    return formatMoney(converted, displayCurrency);
  };

  const scaleFinancialAmount = (value: number): number => {
    const converted = convertAmount(value);
    if (!Number.isFinite(converted)) return Number.NaN;
    return converted / financialDivisor;
  };

  const formatFinancialCompact = (value: number): string => {
    const scaled = scaleFinancialAmount(value);
    if (!Number.isFinite(scaled)) return "-";
    return `${moneySymbol} ${scaled.toLocaleString(moneyLocale, { maximumFractionDigits: 2 })} ${financialUnit}`;
  };

  return {
    displayCurrency,
    usdRub,
    convertAmount,
    formatDisplayMoney,
    financialUnit,
    scaleFinancialAmount,
    formatFinancialCompact,
  };
}

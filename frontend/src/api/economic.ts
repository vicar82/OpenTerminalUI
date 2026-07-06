import { api } from "./base";
import type {
  EconomicEvent,
  MacroIndicatorsResponse,
} from "../types";

export async function fetchEconomicCalendar(from: string, to: string): Promise<EconomicEvent[]> {
  const { data } = await api.get<{ items: EconomicEvent[] }>("/economics/calendar", { params: { from, to } });
  return Array.isArray(data?.items) ? data.items : [];
}

export async function fetchMacroIndicators(country = "RU"): Promise<MacroIndicatorsResponse> {
  const { data } = await api.get<MacroIndicatorsResponse>("/economics/indicators", { params: { country } });
  return data;
}

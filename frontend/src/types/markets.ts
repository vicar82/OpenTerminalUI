export type CountryCode = "RU" | "US";

export type MarketCode = "MOEX" | "NYSE" | "NASDAQ";

export const COUNTRY_MARKETS: Record<CountryCode, MarketCode[]> = {
  RU: ["MOEX"],
  US: ["NYSE", "NASDAQ"],
};

import { api } from "./base";
import type {
  NewsApiItem,
  NewsLatestApiItem,
  QuarterlyReportApiItem,
} from "./types";

export async function fetchSymbolNews(market: string, symbol: string, limit = 30): Promise<NewsApiItem[]> {
  const { data } = await api.get<{ results: NewsApiItem[] }>(`/news/${market}/${symbol}`, { params: { limit } });
  return Array.isArray(data?.results) ? data.results : [];
}

export async function fetchMarketNews(market: string, limit = 30): Promise<NewsApiItem[]> {
  const { data } = await api.get<{ results: NewsApiItem[] }>(`/news/${market}`, { params: { limit } });
  return Array.isArray(data?.results) ? data.results : [];
}

export async function fetchLatestNews(limit = 100): Promise<NewsLatestApiItem[]> {
  const { data } = await api.get<{ items: NewsLatestApiItem[] }>("/v1/news/latest", { params: { limit } });
  return Array.isArray(data?.items) ? data.items : [];
}

export async function searchLatestNews(q: string, limit = 100): Promise<NewsLatestApiItem[]> {
  const { data } = await api.get<{ items: NewsLatestApiItem[] }>("/v1/news/search", { params: { q, limit } });
  return Array.isArray(data?.items) ? data.items : [];
}

export async function fetchNewsByTicker(ticker: string, limit = 100, market?: string): Promise<NewsLatestApiItem[]> {
  const { data } = await api.get<{ items: NewsLatestApiItem[] }>(`/news/by-ticker/${encodeURIComponent(ticker)}`, {
    params: { limit, market },
  });
  return Array.isArray(data?.items) ? data.items : [];
}

export async function fetchQuarterlyReports(market: string, symbol: string, limit = 8): Promise<QuarterlyReportApiItem[]> {
  const { data } = await api.get<{ items: QuarterlyReportApiItem[] }>(`/news/reports/${market}/${symbol}`, { params: { limit } });
  return Array.isArray(data?.items) ? data.items : [];
}

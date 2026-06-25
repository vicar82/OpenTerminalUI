import { useCallback } from "react";
import { ruTranslations, type TranslationKey } from "./ru";

export function useI18n() {
  const t = useCallback((key: TranslationKey | string, fallback?: string): string => {
    return ruTranslations[key as TranslationKey] ?? fallback ?? key;
  }, []);

  return { t };
}

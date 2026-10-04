import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./locales/en.json";
import hi from "./locales/hi.json";
import mr from "./locales/mr.json";

// Adding a language = adding one JSON file here (same keys as en.json).
i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, hi: { translation: hi }, mr: { translation: mr } },
  lng: localStorage.getItem("ss_lang") || "en",
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});
document.documentElement.lang = i18n.language;
i18n.on("languageChanged", (l) => { localStorage.setItem("ss_lang", l); document.documentElement.lang = l; });
export default i18n;
export const LANGS = [["en", "English"], ["hi", "हिन्दी"], ["mr", "मराठी"]];

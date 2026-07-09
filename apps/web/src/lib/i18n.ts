import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "../locales/en.json";
import nl from "../locales/nl.json";
import de from "../locales/de.json";

// Maps the natural-language values already stored in UserPreference.preferred_language
// (see api.preferences.build_language_instruction, which injects them straight into an
// LLM prompt) to i18next locale codes. Same setting drives both the UI language and the
// AI response language -- deliberately not a separate UI-only language picker.
export const LANGUAGE_NAME_TO_CODE: Record<string, string> = {
  English: "en",
  Nederlands: "nl",
  Deutsch: "de",
};

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    nl: { translation: nl },
    de: { translation: de },
  },
  lng: "en",
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

export default i18n;

// hCaptcha widget lifecycle (explicit render). Returns a container ref plus the
// current token; the widget is required on every /api/research call in prod (§10).

import { useEffect, useRef, useState } from "react";

declare global {
  interface Window {
    hcaptcha?: {
      render: (
        container: string | HTMLElement,
        options: {
          sitekey: string;
          callback?: (token: string) => void;
          "expired-callback"?: () => void;
          "error-callback"?: () => void;
          theme?: "light" | "dark" | "auto";
          size?: "normal" | "compact" | "invisible";
        }
      ) => string;
      reset: (widgetId?: string) => void;
    };
  }
}

export type HcaptchaState = {
  siteKey?: string;
  enabled: boolean;
  ref: React.RefObject<HTMLDivElement>;
  token: string | null;
  reset: () => void;
};

export function useHcaptcha(theme: "light" | "dark" = "light"): HcaptchaState {
  const siteKey = import.meta.env.VITE_HCAPTCHA_SITE_KEY as string | undefined;
  const ref = useRef<HTMLDivElement | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [ready, setReady] = useState<boolean>(!siteKey);
  const [widgetId, setWidgetId] = useState<string | null>(null);

  useEffect(() => {
    if (!siteKey) return;
    if (window.hcaptcha) {
      setReady(true);
      return;
    }
    const script = document.createElement("script");
    script.src = "https://js.hcaptcha.com/1/api.js?render=explicit";
    script.async = true;
    script.defer = true;
    script.onload = () => setReady(true);
    document.head.appendChild(script);
    return () => {
      script.remove();
    };
  }, [siteKey]);

  useEffect(() => {
    if (!siteKey || !ready || !ref.current || !window.hcaptcha || widgetId) return;
    const id = window.hcaptcha.render(ref.current, {
      sitekey: siteKey,
      theme,
      size: "normal",
      callback: (t: string) => setToken(t),
      "expired-callback": () => setToken(null),
      "error-callback": () => setToken(null),
    });
    setWidgetId(id);
  }, [ready, siteKey, theme, widgetId]);

  const reset = () => {
    if (window.hcaptcha && widgetId) window.hcaptcha.reset(widgetId);
    setToken(null);
  };

  return { siteKey, enabled: Boolean(siteKey), ref, token, reset };
}

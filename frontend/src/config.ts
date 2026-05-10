/**
 * Centralized frontend configuration.
 * All values can be overridden via VITE_ environment variables.
 */

// Validate required environment variables - only in production
function getRequiredEnv(name: string, fallback: string): string {
  const envValue = import.meta.env[name];
  
  // In dev mode, allow fallback; in prod, require env var
  if (import.meta.env.PROD && (!envValue || envValue === `{{${name}}}`)) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  
  return envValue || fallback;
}

export const APP_CONFIG = {
  // ── Application Identity ──────────────────────────
  appName: import.meta.env.VITE_APP_NAME || "DAMA",
  appSubtitle: import.meta.env.VITE_APP_SUBTITLE || "NSE 500 Signal Engine",

  // ── API ───────────────────────────────────────────
  apiBaseUrl: getRequiredEnv("VITE_API_BASE_URL", 
    import.meta.env.VITE_API_URL || "http://127.0.0.1:8090"),
  apiTimeout: Number(import.meta.env.VITE_API_TIMEOUT) || 30000,

  // ── WebSocket ─────────────────────────────────────
  get wsUrl(): string {
    return (
      import.meta.env.VITE_WS_URL ||
      this.apiBaseUrl.replace("http", "ws")
    );
  },
  wsReconnectDelay: Number(import.meta.env.VITE_WS_RECONNECT_DELAY) || 5000,

  // ── Polling ───────────────────────────────────────
  healthPollIntervalMs: Number(import.meta.env.VITE_HEALTH_POLL_MS) || 30000,

  // ── Trading Defaults ─────────────────────────────
  defaultPaperCapital: Number(import.meta.env.VITE_DEFAULT_PAPER_CAPITAL) || 1_000_000,
  defaultInitialCapital: Number(import.meta.env.VITE_DEFAULT_INITIAL_CAPITAL) || 10_000,

  // ── Chart Colors ──────────────────────────────────
  chartPrimaryColor: import.meta.env.VITE_CHART_PRIMARY || "#3b82f6",
  chartPositiveColor: import.meta.env.VITE_CHART_POSITIVE || "#10b981",
  chartNegativeColor: import.meta.env.VITE_CHART_NEGATIVE || "#ef4444",

  // ── Formatting ───────────────────────────────────
  currencyLocale: import.meta.env.VITE_CURRENCY_LOCALE || "en-IN",
  currency: (import.meta.env.VITE_CURRENCY || "INR") as string,
} as const;

export default APP_CONFIG;

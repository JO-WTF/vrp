// VRP Studio runtime configuration.
//
// This file is copied to the built frontend as /config.js and is loaded before
// the Vue application. Edit it after deployment when the backend service is
// exposed on a different domain, host, or port than the frontend.
window.VRP_STUDIO_CONFIG = {
  // Full backend HTTP origin. When set, it takes precedence over the split
  // BACKEND_* fields below. Example: "https://vrp-api.example.com:8000".
  API_BASE_URL: "",

  // Full backend WebSocket origin. When empty, it is derived from API_BASE_URL
  // or from BACKEND_PROTOCOL/BACKEND_HOST/BACKEND_PORT.
  // Example: "wss://vrp-api.example.com:8000".
  WS_BASE_URL: "",

  // Split backend address configuration used when API_BASE_URL is empty.
  // Defaults target the same host/port that serves the frontend.
  BACKEND_PROTOCOL: window.location.protocol.replace(/:$/, ""),
  BACKEND_HOST: window.location.hostname,
  BACKEND_PORT: window.location.port,
};

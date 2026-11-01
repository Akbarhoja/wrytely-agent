import { registerCanvasHost } from "./canvas-pairing/host-events.mjs";
import { config } from "./config.mjs";

// Registration reconciles persisted preferences; a fresh profile stays inactive.
registerCanvasHost({ chrome, ...config });

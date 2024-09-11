import { chromium } from "playwright-core";

export const connectToCdp = async (enableProxy?: boolean, sessionId?: string) =>
  chromium.connectOverCDP(
    // we connect to a Session created via the API
    `wss://connect.browserbase.com?apiKey=${process.env.BROWSERBASE_API_KEY}${enableProxy ? "&enableProxy=true" : ""}${sessionId ? `&sessionId=${sessionId}` : ""}`,
  );

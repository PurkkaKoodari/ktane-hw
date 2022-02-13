import { h, render } from "preact";
import ApiConnection from "./ApiConnection";
import App from "./App";
import LogProvider from "./LogProvider";

const UI_VERSION = "0.1-a1";
const WS_PORT = 8081;
const WS_PATH = "/ws";

// const wsUrl = `ws://${location.hostname}:${WS_PORT}${WS_PATH}`;
const wsUrl = `ws://pommipeli.tunk.org:${WS_PORT}${WS_PATH}`;

render(
  (
    <LogProvider>
      <ApiConnection wsUrl={wsUrl} uiVersion={UI_VERSION}>
        <App />
      </ApiConnection>
    </LogProvider>
  ), document.getElementById("root")!,
);

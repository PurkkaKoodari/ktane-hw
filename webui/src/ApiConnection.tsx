import { ComponentChildren, h } from "preact";
import { useEffect, useReducer, useState } from "preact/hooks";
import { BombContext, Connection, ConnectionContext } from "./contexts";
import { useLogs } from "./LogProvider";
import messageHandler from "./messageHandler";

type Props = {
  wsUrl: string;
  uiVersion: string;
  children: ComponentChildren;
};

export default function ApiConnection({ wsUrl, uiVersion, children }: Props) {
  const [, log] = useLogs();
  const [bombState, handleMessage] = useReducer(messageHandler(log), null);
  const [connection, setConnection] = useState<Connection>({ send: () => {} });

  useEffect(() => {
    const ws = new WebSocket(wsUrl);
    let connected = false;

    ws.addEventListener("open", () => {
      connected = true;
      ws.send(JSON.stringify({
        type: "login",
        ui_version: uiVersion,
        password: null,
      }));
      setConnection({ send(msg: any) { ws.send(JSON.stringify(msg)); } });
    });

    ws.addEventListener("message", (e) => {
      let data;
      try {
        data = JSON.parse(e.data);
      } catch (_) {
        log("[ERROR] Invalid data received from WebSocket");
        return;
      }
      handleMessage(data);
    });

    ws.addEventListener("close", (e) => {
      setConnection({ send() {} });
      switch (e.code) {
        case 4000:
          log("[INFO] Disconnected because another client connected");
          break;
        case 4001:
          log("[ERROR] UI version mismatch, please refresh the page");
          break;
        case 4002:
          log("[ERROR] The server requires a password, which is not supported yet");
          break;
        case 4003:
          log("[ERROR] The entered password was incorrect");
          break;
        case 1001:
          log("[INFO] The server is shutting down");
          break;
        case 1005:
        case 1006:
          if (connected) {
            log("[ERROR] WebSocket closed abnormally");
          } else {
            log("[ERROR] WebSocket failed to connect");
          }
          break;
        default:
          log(`[ERROR] WebSocket closed with code ${e.code}: ${e.reason}`);
          break;
      }
      connected = false;
    });

    return () => ws.close();
  }, [wsUrl, uiVersion, log]);

  return (
    <ConnectionContext.Provider value={connection}>
      <BombContext.Provider value={bombState}>
        {children}
      </BombContext.Provider>
    </ConnectionContext.Provider>
  );
}

import { ComponentChildren, createContext, h } from "preact";
import { useContext, useReducer } from "preact/hooks";

type LogContextValue = readonly [string[], (msg: string) => void];
const LogContext = createContext<LogContextValue | null>(null);

export function useLogs() {
  const value = useContext(LogContext);
  if (!value) throw new Error("Missing <LogProvider>");
  return value;
}

type Props = {
  children: ComponentChildren;
};

function logReducer(logs: string[], msg: string) {
  return [msg, ...logs];
}

export default function LogProvider({ children }: Props) {
  const value = useReducer(logReducer, []);
  return (
    <LogContext.Provider value={value}>
      {children}
    </LogContext.Provider>
  );
}

import { createContext } from "preact";
import { BombState, ModuleState } from "./types";

export type Connection = {
  send(msg: any): void;
};

export const ConnectionContext = createContext<Connection>({ send() {} });
export const BombContext = createContext<BombState | null>(null);
export const ModuleContext = createContext<ModuleState | null>(null);

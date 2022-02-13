import { h } from "preact";
import { useContext } from "preact/hooks";
import modules from ".";
import { BombContext, ModuleContext } from "../contexts";
import UnknownModule from "./UnknownModule";

type Props = {
  slot: number;
};

export default function Module({ slot }: Props) {
  const bombState = useContext(BombContext);
  const moduleState = bombState && bombState.modules[slot];

  if (!moduleState) {
    return (
      <div className="module" />
    );
  }

  const ModuleComponent = modules[moduleState.type] || UnknownModule;

  return (
    <ModuleContext.Provider value={moduleState}>
      <ModuleComponent />
    </ModuleContext.Provider>
  );
}

import { h } from "preact";
import { useContext } from "preact/hooks";
import { ModuleContext } from "../contexts";
import ModuleBase from "./ModuleBase";

export default function UnknownModule() {
  const module = useContext(ModuleContext)!;
  return (
    <ModuleBase className="unknown">
      <text x="2" y="15" font-size="14" font-weight="bold">Unknown</text>
      <text x="2" y="30" font-size="12">{`ID ${module.type}`}</text>
      <text className="details">{JSON.stringify(module.details)}</text>
    </ModuleBase>
  );
}

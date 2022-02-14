import { h } from "preact";
import { useContext } from "preact/hooks";
import { ModuleContext } from "../contexts";
import ModuleBase from "./ModuleBase";

type Details = {
  needy_state: string;
  question: string;
};

const questions: Record<string, string> = {
  VENT_GAS: "VENT GAS?\nY/N",
  DETONATE: "DETONATE?\nY/N",
};

export default function VentingGasModule() {
  const { needy_state: needyState, question } = useContext(ModuleContext)!.details as Details;
  return (
    <ModuleBase noStatusLed className="venting-gas">
      <rect x="0" y="0" width="100" height="100" fill="#808090" />
      <rect x="5" y="25" width="90" height="70" fill="#ab8a64" stroke-width="4" />
      {needyState === "ACTIVE" && (
        <text x="50" y="70" text-anchor="middle" fill="#0f0" font-size="12">
          {questions[question]}
        </text>
      )}
    </ModuleBase>
  );
}

VentingGasModule.moduleName = "Timer";

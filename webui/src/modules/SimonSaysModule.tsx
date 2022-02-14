import { h } from "preact";
import { useContext, useMemo } from "preact/hooks";
import { ModuleContext } from "../contexts";
import ModuleBase from "./ModuleBase";

type Color = "NONE" | "BLUE" | "YELLOW" | "GREEN" | "RED";

type Details = Partial<{
  sequence: Color[];
  pressed: Color[];
}>;

const unlitFills: Record<string, string> = {
  blue: "#010370",
  yellow: "#7f6b01",
  green: "#156105",
  red: "#6a0409",
};
const litFills: Record<string, string> = {
  blue: "#0207f4",
  yellow: "#f9d202",
  green: "#33ed21",
  red: "#f10914",
};

export default function SimonSaysModule() {
  const { state, details } = useContext(ModuleContext)!;

  const animation = useMemo(() => {
    const sequence = (state === "GAME" && (details as Details).sequence) || [null];
    return (
      ["blue", "yellow", "green", "red"].map((button) => `
      .${button} {
        animation: ${sequence.length + 2}s infinite step-end ${button}-seq;
      }
      @keyframes ${button}-seq {
        ${sequence.map((color, idx) => `
          ${100 * idx / (sequence.length + 2)}% {
            fill: ${color === button.toUpperCase() ? litFills[button] : unlitFills[button]};
          }
          ${100 * (idx + 0.5) / (sequence.length + 2)}% {
            fill: ${unlitFills[button]};
          }
        `).join("\n")}
      }
    `).join("\n")
    );
  }, [state, details]);

  return (
    <ModuleBase className="keypad">
      <style>
        {animation}
      </style>
      <rect x="0" y="0" width="100" height="100" fill="#808090" />
      <polygon points="50,20 68,38 50,56 32,38" className="blue" />
      <polygon points="70,40 88,58 70,76 52,58" className="yellow" />
      <polygon points="50,60 68,78 50,96 32,78" className="green" />
      <polygon points="30,40 48,58 30,76 12,58" className="red" />
    </ModuleBase>
  );
}

SimonSaysModule.moduleName = "Simon Says";

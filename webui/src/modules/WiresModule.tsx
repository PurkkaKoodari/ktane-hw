import range from "lodash/range";
import { h, Fragment } from "preact";
import { useContext } from "preact/hooks";
import { ModuleContext } from "../contexts";
import ModuleBase from "./ModuleBase";

type WireState = "RED" | "BLUE" | "YELLOW" | "BLACK" | "WHITE" | "RED_BLUE" | "DISCONNECTED" | "SHORT" | "INVALID";

type Details = Partial<{
  wires: WireState[];
  connected: WireState[];
  cut: boolean[];
  solution: number;
}>;

const wireFills: Record<WireState, string> = {
  RED: "red",
  BLUE: "blue",
  YELLOW: "yellow",
  BLACK: "black",
  WHITE: "white",
  RED_BLUE: "url(#red_blue)",
  DISCONNECTED: "",
  SHORT: "",
  INVALID: "",
};

export default function WiresModule() {
  const { wires, cut, solution } = useContext(ModuleContext)!.details as Details;
  return (
    <ModuleBase className="wires">
      <style>
        {`
        rect.bad-wire, rect.bad-wire {
          animation: infinite 0.6s step-end bad-wire;
        }
        @keyframes bad-wire {
          0% {
            fill: red;
          }
          50% {
            fill: #333;
          }
        }
        `}
      </style>
      <pattern id="red_blue" viewBox="0,0 10,15" width="10" height="15" patternUnits="userSpaceOnUse">
        <rect x="0" y="0" width="10" height="15" fill="red" />
        <polygon points="5,0 10,0 0,15 -5,15" fill="blue" />
        <polygon points="15,0 20,0 10,15 5,15" fill="blue" />
      </pattern>
      <rect x="0" y="0" width="100" height="100" fill="#808090" />
      {wires && range(6).map((pos) => {
        const bad = wires[pos] === "SHORT" || wires[pos] === "INVALID";
        return (
          <>
            <rect x="5" y={22 + 13 * pos} width="8" height="8" fill="#333" className={bad ? "bad-wire" : ""} />
            <rect x="87" y={22 + 13 * pos} width="8" height="8" fill="#333" className={bad ? "bad-wire" : ""} />
            <rect x="9" y={24 + 13 * pos} width="82" height="4" fill={wireFills[wires[pos]] || "transparent"} />
            {cut![pos] && <rect x="35" y={22 + 13 * pos} width="30" height="8" fill="#808090" />}
            {solution === pos && (
              <text
                x="50"
                y={26 + 13 * pos}
                text-anchor="middle"
                dominant-baseline="middle"
                fill="lime"
                font-size="16"
              >
                &#x2714;
              </text>
            )}
          </>
        );
      })}
    </ModuleBase>
  );
}

WiresModule.moduleName = "Wires";

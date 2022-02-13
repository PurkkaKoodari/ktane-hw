import range from "lodash/range";
import { h, Fragment } from "preact";
import { useContext } from "preact/hooks";
import { ModuleContext } from "../contexts";
import ModuleBase from "./ModuleBase";

type WireState = "RED" | "BLUE" | "YELLOW" | "BLACK" | "WHITE" | "RED_BLUE" | "DISCONNECTED" | "SHORT" | "INVALID";

type Details = Partial<{
  wires: WireState[];
  leds: boolean[];
  stars: boolean[];
  connected: WireState[];
  cut: boolean[];
  solution: boolean[];
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

const star = "0.000,-3.804 0.944,-0.898 4.000,-0.898 1.528,0.898 2.472,3.804 "
  + "0.000,2.008 -2.472,3.804 -1.528,0.898 -4.000,-0.898 -0.944,-0.898";

export default function ComplicatedWiresModule() {
  const {
    wires, cut, leds, stars, solution,
  } = useContext(ModuleContext)!.details as Details;
  return (
    <ModuleBase className="complicated-wires">
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
      <pattern id="red_blue" viewBox="0,0 15,10" width="15" height="10" patternUnits="userSpaceOnUse">
        <rect x="0" y="0" width="15" height="10" fill="red" />
        <polygon points="0,5 0,10 15,0 15,-5" fill="blue" />
        <polygon points="0,15 0,20 15,10 15,5" fill="blue" />
      </pattern>
      <rect x="0" y="0" width="100" height="100" fill="#808090" />
      {wires && range(6).map((pos) => {
        const bad = wires[pos] === "SHORT" || wires[pos] === "INVALID";
        return (
          <>
            <circle cx={10 + 16 * pos} cy="24" r="4" fill={leds?.[pos] ? "white" : "#333"} />
            <rect x={6 + 16 * pos} y="30" width="8" height="8" fill="#333" className={bad ? "bad-wire" : ""} />
            <rect x={6 + 16 * pos} y="75" width="8" height="8" fill="#333" className={bad ? "bad-wire" : ""} />
            <rect x={8 + 16 * pos} y="34" width="4" height="45" fill={wireFills[wires[pos]] || "transparent"} />
            {cut![pos] && <rect x={6 + 16 * pos} y="49" width="8" height="15" fill="#808090" />}
            <rect x={5 + 16 * pos} y="85" width="10" height="10" fill="white" />
            {stars![pos] && <polygon points={star} transform={`translate(${10 + 16 * pos} 90)`} fill="black" />}
            {solution![pos] && (
              <text
                x={10 + 16 * pos}
                y="56.5"
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

ComplicatedWiresModule.moduleName = "Complicated Wires";

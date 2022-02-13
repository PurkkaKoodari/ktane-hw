import { h } from "preact";
import { useContext } from "preact/hooks";
import { ModuleContext } from "../contexts";
import ModuleBase from "./ModuleBase";

type ButtonColor = "BLUE" | "WHITE" | "RED" | "YELLOW";
type LightColor = "BLUE" | "WHITE" | "YELLOW" | "RED";

type Details = {
  color: ButtonColor;
  text: string;
  should_hold: boolean;
  light_color: LightColor;
  pressed: boolean;
};

const buttonFills: Record<ButtonColor, string> = {
  BLUE: "blue",
  WHITE: "white",
  RED: "red",
  YELLOW: "yellow",
};
const textFills: Record<ButtonColor, string> = {
  BLUE: "white",
  WHITE: "black",
  RED: "white",
  YELLOW: "black",
};
const lightFills: Record<LightColor, string> = {
  BLUE: "royalblue",
  WHITE: "white",
  YELLOW: "gold",
  RED: "crimson",
};

export default function ButtonModule() {
  const {
    color, text, light_color: lightColor, pressed,
  } = useContext(ModuleContext)!.details as Details;
  return (
    <ModuleBase className="wires">
      <style>
        {`
        .button {
          animation: transform 0.25s ease;
          transform: scale(1);
        }
        .button.pressed {
          transform: scale(0.8);
        }
        `}
      </style>
      <rect x="0" y="0" width="100" height="100" fill="#808090" />
      <circle
        cx="40"
        cy="60"
        r="35"
        fill={buttonFills[color]}
        className={`button ${pressed ? "pressed" : ""}`}
        transform-origin="40 60"
      />
      <text x="40" y="60" text-anchor="middle" dominant-baseline="middle" fill={textFills[color]} font-size="14">
        {text}
      </text>
      <rect x="80" y="50" width="15" height="45" fill={pressed ? lightFills[lightColor] : "#333"} />
    </ModuleBase>
  );
}

ButtonModule.moduleName = "Button";

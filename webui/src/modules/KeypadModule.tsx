import { h, Fragment } from "preact";
import { useContext } from "preact/hooks";
import { ModuleContext } from "../contexts";
import ModuleBase from "./ModuleBase";

const positions: [string, number, number][] = [
  ["TOP_LEFT", 0, 0],
  ["TOP_RIGHT", 1, 0],
  ["BOTTOM_LEFT", 0, 1],
  ["BOTTOM_RIGHT", 1, 1],
];

type Details = Partial<{
  buttons: string[];
  solution: string[];
  pressed: string[];
}>;

export default function KeypadModule() {
  const { buttons, pressed } = useContext(ModuleContext)!.details as Details;
  return (
    <ModuleBase className="keypad">
      <rect x="0" y="0" width="100" height="100" fill="#808090" />
      {buttons && positions.map(([name, x, y], idx) => (
        <>
          <rect x={5 + 39 * x} y={22 + 39 * y} width="34" height="34" fill="#fff" />
          <text
            key={name}
            x={22 + 39 * x}
            y={49 + 39 * y}
            text-anchor="middle"
            fill="#000"
            font-size="18"
          >
            {buttons[idx]}
          </text>
          <rect x={18 + 39 * x} y={25 + 39 * y} width="8" height="3" fill={pressed?.includes(name) ? "#0f0" : "#000"} />
        </>
      ))}
    </ModuleBase>
  );
}

KeypadModule.moduleName = "Keypad";

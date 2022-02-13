import range from "lodash/range";
import { h } from "preact";
import { useContext } from "preact/hooks";
import { ModuleContext } from "../contexts";
import ModuleBase from "./ModuleBase";

type Details = {
  characters: string[][] | null;
  solution: string | null;
};

const animations = range(6).map((i) => `
.char-${i} {
  animation: 6s infinite step-end char-loop-${i};
}
@keyframes char-loop-${i} {
  0% {
    visibility: hidden;
  }
  ${0.0001 + 16.6666 * i}% {
    visibility: visible;
  }
  ${0.0001 + 16.6666 * (i + 1)}% {
    visibility: hidden;
  }
}
`).join("\n");

export default function PasswordModule() {
  const { state, details } = useContext(ModuleContext)!;
  const { characters, solution } = details as Details;
  return (
    <ModuleBase className="complicated-wires">
      <style>
        {animations}
      </style>
      <rect x="0" y="0" width="100" height="100" fill="#808090" />
      <rect x="7" y="35" width="86" height="30" fill="#9d1" stroke="#334" stroke-width="4" />
      {characters && range(5).flatMap((pos) => [
        state === "DEFUSED" ? (
          <text
            key={pos}
            x={20 + 15 * pos}
            y="56"
            text-anchor="middle"
            fill="#090"
            font-family="monospace"
            font-size="18"
          >
            {solution![pos]}
          </text>
        ) : characters[pos].flatMap((char, idx) => (
          <text
            key={`${pos}_${idx}`}
            x={20 + 15 * pos}
            y="56"
            text-anchor="middle"
            fill="#333"
            font-family="monospace"
            font-size="18"
            className={`char-${idx}`}
          >
            {char}
          </text>
        )),
        <polygon points="0,23 4,30 -4,30" transform={`translate(${20 + 15 * pos} 0)`} fill="#fff" />,
        <polygon points="4,70 0,77 -4,70" transform={`translate(${20 + 15 * pos} 0)`} fill="#fff" />,
      ])}
      <rect x="36" y="84" width="28" height="8" fill="#fff" />
    </ModuleBase>
  );
}

PasswordModule.moduleName = "Password";

import { h } from "preact";
import ModuleBase from "./ModuleBase";

export default function TimerModule() {
  return (
    <ModuleBase noStatusLed className="timer">
      <rect x="0" y="0" width="100" height="100" fill="#333" />
      <rect x="27" y="27" width="46" height="21" fill="#000" stroke="#808090" stroke-width="4" />
      <rect x="7" y="57" width="86" height="36" fill="#000" stroke="#808090" stroke-width="4" />
      <text className="x1">&times;</text>
      <text className="x2">&times;</text>
      <text
        x="50"
        y="44"
        text-anchor="middle"
        className="number"
        fill="#f00"
      >
        {`${1}/${2}`}
      </text>
      <text
        x="50"
        y="90"
        text-anchor="middle"
        fill="#f00"
        font-family="monospace"
        font-size="26"
        transform="scale(1 1.5)"
        transform-origin="50 90"
      >
        00:00
      </text>
    </ModuleBase>
  );
}

TimerModule.moduleName = "Timer";

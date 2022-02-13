import { ComponentChildren, h } from "preact";
import { useContext } from "preact/hooks";
import { ModuleContext } from "../contexts";
import { ErrorLevel } from "../types";

const errorColors: Partial<Record<ErrorLevel, string>> = {
  [ErrorLevel.INFO]: "royalblue",
  [ErrorLevel.RECOVERED]: "royalblue",
  [ErrorLevel.WARNING]: "yellow",
  [ErrorLevel.RECOVERABLE]: "darkorange",
  [ErrorLevel.MINOR]: "orangered",
  [ErrorLevel.MAJOR]: "red",
  [ErrorLevel.FATAL]: "darkred",
};

type Props = {
  present?: boolean;
  noStatusLed?: boolean;
  className?: string;
  children: ComponentChildren;
};

export default function ModuleBase({
  present = true,
  noStatusLed = false,
  className = "",
  children,
}: Props) {
  const module = useContext(ModuleContext)!;
  const statusColor = module.state === "DEFUSED" ? "#0f0" : "lightgray";
  const errorColor = errorColors[module.errorLevel];
  return (
    <div className={`module ${present ? "present" : ""} ${className}`}>
      <svg viewBox="0 0 100 100">
        {children}
        {present && !noStatusLed && (
          <circle cx="92" cy="8" r="8" fill={statusColor} />
        )}
        {present && errorColor && (
          <rect x={noStatusLed ? "84" : "68"} y="0" width="16" height="16" fill={errorColor} />
        )}
      </svg>
    </div>
  );
}

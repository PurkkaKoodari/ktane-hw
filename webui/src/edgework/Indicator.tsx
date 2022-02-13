import { h } from "preact";
import { IndicatorState } from "../types";

type Props = {
  details: IndicatorState;
};

export default function Indicator({ details }: Props) {
  return (
    <div className="indicator">
      <div className="type">INDICATOR</div>
      <div className="name">{details.name}</div>
      <div className={`light ${details.lit ? "lit" : "unlit"}`} />
    </div>
  );
}

import { h } from "preact";
import { PortPlateState } from "../types";

type Props = {
  details: PortPlateState;
};

export default function PortPlate({ details }: Props) {
  return (
    <div className="portPlate">
      <div className="type">PORT PLATE</div>
      <div className="ports">{details.ports.join(" ") || "empty"}</div>
    </div>
  );
}

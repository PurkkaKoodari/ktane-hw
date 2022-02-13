import { h, Fragment } from "preact";
import { BatteryState } from "../types";

type Props = {
  details: BatteryState;
};

export default function Battery({ details }: Props) {
  return (
    <div className="battery">
      <div className="type">BATTERY</div>
      {details.battery_type === "aa" ? (
        <>
          <div className="aa" />
          <div className="aa" />
        </>
      ) : (
        <div className="d" />
      )}
    </div>
  );
}

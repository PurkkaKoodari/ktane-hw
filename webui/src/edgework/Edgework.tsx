import { h } from "preact";
import { useContext } from "preact/hooks";
import { BombContext } from "../contexts";
import Battery from "./Battery";
import Indicator from "./Indicator";
import PortPlate from "./PortPlate";
import Serial from "./Serial";

export default function Edgework() {
  const bombState = useContext(BombContext);

  if (!bombState) return null;

  return (
    <div id="widgets">
      <Serial serial={bombState.serial} />
      {bombState.edgework.map((widget) => {
        switch (widget.type) {
          case "battery":
            return <Battery details={widget} />;
          case "indicator":
            return <Indicator details={widget} />;
          case "port_plate":
            return <PortPlate details={widget} />;
          default:
            return null;
        }
      })}
    </div>
  );
}

import { h } from "preact";
import Module from "../modules/Module";

export default function VanillaCasing() {
  return (
    <div id="bomb">
      <div className="bombSide">
        <h3 className="title">Front side</h3>
        <Module slot={0} />
        <Module slot={4} />
        <Module slot={8} />
        <Module slot={1} />
        <Module slot={5} />
        <Module slot={9} />
      </div>
      <div className="bombSide">
        <h3 className="title">Back side</h3>
        <Module slot={10} />
        <Module slot={6} />
        <Module slot={2} />
        <Module slot={11} />
        <Module slot={7} />
        <Module slot={3} />
      </div>
    </div>
  );
}

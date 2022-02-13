import { h } from "preact";
import { useLogs } from "./LogProvider";

export default function LogView() {
  const [logs] = useLogs();
  return (
    <div id="errorLog">
      {logs.join("\n")}
    </div>
  );
}

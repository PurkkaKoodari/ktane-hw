import { h } from "preact";
import Bomb from "./casings/Bomb";
import Controls from "./Controls";
import Edgework from "./edgework/Edgework";
import LogView from "./LogView";

export default function App() {
  return (
    <div id="app">
      <LogView />
      <Edgework />
      <Bomb />
      <Controls />
    </div>
  );
}

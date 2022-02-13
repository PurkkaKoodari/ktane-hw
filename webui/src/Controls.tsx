import { h } from "preact";
import { useContext } from "preact/hooks";
import { BombContext, ConnectionContext } from "./contexts";

export default function Controls() {
  const { send } = useContext(ConnectionContext);
  const bomb = useContext(BombContext);
  return (
    <div id="controls">
      <button onClick={() => send({ type: "reset" })} type="button">
        Reset
      </button>
      {bomb?.state === "INITIALIZED" && (
        <button onClick={() => send({ type: "start_game" })} type="button">
          Start game
        </button>
      )}
      {bomb?.state === "GAME_STARTING" && (
        <button onClick={() => send({ type: "start_timer" })} type="button">
          Start timer
        </button>
      )}
    </div>
  );
}

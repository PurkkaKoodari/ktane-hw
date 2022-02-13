import { h } from "preact";
import { useContext } from "preact/hooks";
import casings from ".";
import { BombContext } from "../contexts";

export default function Bomb() {
  const bombState = useContext(BombContext);

  if (!bombState) return null;

  const CasingComponent = casings[bombState.casing];
  return <CasingComponent />;
}

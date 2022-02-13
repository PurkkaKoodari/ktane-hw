import { ComponentType } from "preact";
import ButtonModule from "./ButtonModule";
import ComplicatedWiresModule from "./ComplicatedWiresModule";
import KeypadModule from "./KeypadModule";
import PasswordModule from "./PasswordModule";
import SimonSaysModule from "./SimonSaysModule";
import TimerModule from "./TimerModule";
import WiresModule from "./WiresModule";

export type ModuleComponent = ComponentType & {
  moduleName: string;
};

const modules: Record<number, ModuleComponent> = {
  1: TimerModule,
  2: WiresModule,
  3: ButtonModule,
  4: KeypadModule,
  5: SimonSaysModule,
  9: ComplicatedWiresModule,
  12: PasswordModule,
  // 13: "Venting Gas",
};

export default modules;

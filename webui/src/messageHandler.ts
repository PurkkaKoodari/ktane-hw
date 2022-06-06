/* eslint-disable react/destructuring-assignment */
import modules from "./modules";
import { BombState, ErrorLevel } from "./types";

// eslint-disable-next-line react/function-component-definition
const messageHandler = (log: (msg: string) => void) => (prevState: BombState | null, msg: any): BombState | null => {
  switch (msg.type) {
    case "reset":
      return null;
    case "state":
      log(`[STATE] ${msg.state}`);
      return {
        ...prevState!,
        state: msg.state,
      };
    case "add_module":
      return {
        ...prevState!,
        modules: prevState!.modules.map((prev, index) => (index !== msg.location ? prev : {
          type: msg.module_type,
          name: modules[msg.module_type]?.moduleName || `Unknown Module ${msg.module_type}`,
          serial: msg.serial,
          state: msg.state,
          errorLevel: msg.error_level,
          details: msg.details,
        })),
      };
    case "update_module":
      if (prevState!.modules[msg.location] === null) throw new Error("Bad module state received");
      return {
        ...prevState!,
        modules: prevState!.modules.map((prev, index) => (index !== msg.location ? prev : {
          ...prev,
          state: msg.state,
          details: msg.details,
        })),
      };
    case "bomb":
      return {
        state: "INITIALIZED",
        serial: msg.serial_number,
        casing: "VanillaCasing",
        modules: Array(12).fill(null),
        edgework: msg.widgets,
      };
    case "error":
      if (msg.module !== null && prevState!.modules[msg.module] !== null) {
        const module = prevState!.modules[msg.module];
        log(`[${msg.level}] ${module.name}: ${msg.message}`);
        return {
          ...prevState!,
          modules: prevState!.modules.map((prev, index) => (index !== msg.location ? prev : {
            ...prev,
            errorLevel: Math.max(prev.errorLevel, ErrorLevel[msg.level] as any),
          })),
        };
      }
      log(`[${msg.level}] ${msg.message}`);
      return prevState;
    default:
      log(`[MSG] ${JSON.stringify(msg)}`);
      return prevState;
  }
};

export default messageHandler;

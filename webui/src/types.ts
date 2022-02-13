export enum ErrorLevel {
  NONE = 0,
  INFO = 1,
  RECOVERED = 2,
  WARNING = 3,
  RECOVERABLE = 4,
  MINOR = 5,
  MAJOR = 6,
  INIT_FAILURE = 7,
  FATAL = 8,
}

export type ModuleState = {
  type: number;
  name: string;
  serial: number;
  state: string;
  errorLevel: ErrorLevel;
  details: any;
};

export type BatteryState = {
  type: "battery";
  battery_type: "aa" | "d";
};

export type PortPlateState = {
  type: "port_plate";
  ports: string[];
};

export type IndicatorState = {
  type: "indicator";
  name: string;
  lit: boolean;
};

export type EdgeworkState = BatteryState | PortPlateState | IndicatorState;

export type BombState = {
  state: string;
  serial: string;
  casing: string;
  modules: ModuleState[];
  edgework: EdgeworkState[];
};

#include "wires.h"

#if MODULE_TYPE == MODULE_TYPE_WIRES

uint8_t prevConnected = 255;

const uint8_t wire_pins[6] = { WIRE_PINS };

struct wire_cut_data {
  uint8_t position;
};
struct wire_positions_data {
  uint8_t positions;
};

void moduleInitHardware() {
  for (uint8_t i = 0; i < 6; i++) {
    pinMode(wire_pins[i], INPUT_PULLUP);
  }
}

void moduleReset() {
  prevConnected = 255;
}

bool moduleHandleMessage(uint16_t messageId) {
  return false;
}

void moduleLoop() {
  if (mode == CONFIGURATION || mode == GAME) {
    uint8_t reallyConnected = 0;
    for (uint8_t i = 0; i < 6; i++) {
      reallyConnected |= !digitalRead(wire_pins[i]) << i;
    }
    if (reallyConnected != prevConnected) {
      ((struct wire_positions_data *) &canFrame.data)->positions = reallyConnected;
      sendMessage(MESSAGE_MODULE_SPECIFIC_0, 1);
      prevConnected = reallyConnected;
    }
  }
}

#endif

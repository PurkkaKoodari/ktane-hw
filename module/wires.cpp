#include "wires.h"

#if MODULE_TYPE == MODULE_TYPE_WIRES || MODULE_TYPE == MODULE_TYPE_COMPLICATED_WIRES

#define WIRES_WAIT_MEASUREMENTS 3
#define WIRES_TOLERANCE 31 // 0.15V

enum wire_color : uint8_t {
  RED = 0, BLUE = 1, YELLOW = 2, BLACK = 3, WHITE = 4, RED_BLUE = 5,
  DISCONNECTED = 6, SHORT = 7, INVALID = 8
};

enum wire_color last_detected_wires[6] = { DISCONNECTED, DISCONNECTED, DISCONNECTED, DISCONNECTED, DISCONNECTED, DISCONNECTED };
uint8_t consecutive_measurements[6] = { 0, 0, 0, 0, 0, 0 };
enum wire_color sent_wires[6] = { DISCONNECTED, DISCONNECTED, DISCONNECTED, DISCONNECTED, DISCONNECTED, DISCONNECTED };

const uint8_t wire_pins[6] = { WIRE_PINS };
const int16_t color_voltages[8] = {
  409, // red: 2V
  614, // blue: 3V
  205, // yellow: 1V
  819, // black: 4V
  717, // white: 3.5V
  921, // red+blue: 4.5V
  1024, // disconnected: 5V
  0 // short circuit: 0V
};

#ifdef DEBUG
const char *color_names[8] = {
  "red", "blue", "yellow", "black", "white", "none", "short", "invalid"
};
#endif

#if MODULE_TYPE == MODULE_TYPE_COMPLICATED_WIRES
const uint8_t led_row_pins[2] = { LED_ROW_PINS };
const uint8_t led_column_pins[3] = { LED_COLUMN_PINS };

uint8_t led_states;
#endif

struct wire_colors_data {
  enum wire_color wires[6];
};
#if MODULE_TYPE == MODULE_TYPE_COMPLICATED_WIRES
struct wire_leds_data {
  uint8_t leds;
};
#endif

void moduleInitHardware() {
  for (uint8_t i = 0; i < 6; i++) {
    pinMode(wire_pins[i], INPUT);
  }
#if MODULE_TYPE == MODULE_TYPE_COMPLICATED_WIRES
  for (uint8_t i = 0; i < 2; i++) {
    digitalWrite(led_row_pins[i], LOW);
    pinMode(led_row_pins[i], OUTPUT);
  }
  for (uint8_t i = 0; i < 3; i++) {
    digitalWrite(led_column_pins[i], HIGH);
    pinMode(led_column_pins[i], OUTPUT);
  }
#endif
}

void moduleReset() {
  // reset consecutive measurements to ensure we re-send the wire values
  for (uint8_t i = 0; i < 6; i++) {
    consecutive_measurements[i] = 0;
  }
}

bool moduleHandleMessage(uint16_t messageId) {
#if MODULE_TYPE == MODULE_TYPE_COMPLICATED_WIRES
  switch (messageId) {
  case MESSAGE_MODULE_SPECIFIC_1:
    led_states = (uint8_t) ((struct wire_leds_data *) &canFrame.data)->leds;
    return true;
  default:
    return false;
  }
#else
  return false;
#endif
}

uint8_t current_led_row = 0;

void moduleLoop() {
#if MODULE_TYPE == MODULE_TYPE_COMPLICATED_WIRES
  digitalWrite(led_row_pins[current_led_row], LOW);
  current_led_row = (current_led_row + 1) % 2;
  digitalWrite(led_row_pins[current_led_row], HIGH);
  uint8_t led = current_led_row * 3;
  for (uint8_t i = 0; i < 3; i++) {
    digitalWrite(led_column_pins[i], (led_states >> led) & 1);
    led++;
  }
#endif

  if (mode == CONFIGURATION || mode == GAME) {
    bool changed = false;
    for (uint8_t wire = 0; wire < 6; wire++) {
      // detect wire color
      int16_t read_value = analogRead(wire_pins[wire]);
      enum wire_color detected = INVALID;
      for (uint8_t color = 0; color < INVALID; color++) {
        if (color_voltages[color] - WIRES_TOLERANCE <= read_value && read_value <= color_voltages[color] + WIRES_TOLERANCE) {
          detected = (enum wire_color)color;
          break;
        }
      }

      if (detected != last_detected_wires[wire]) {
        // when the status changes, reset the counter
        last_detected_wires[wire] = detected;
        consecutive_measurements[wire] = 1;
      } else if (consecutive_measurements[wire] < WIRES_WAIT_MEASUREMENTS) {
        // when the status stays the same, increment the counter
        // and send the new states when they stay long enough
        if (++consecutive_measurements[wire] == WIRES_WAIT_MEASUREMENTS) {
          sent_wires[wire] = last_detected_wires[wire];
          changed = true;
          DEBUG_PRINT("wire ");
          DEBUG_PRINT(wire);
          DEBUG_PRINT(" changed to ");
          DEBUG_PRINTLN(color_names[sent_wires[wire]]);
        }
      }
    }

    if (changed) {
      for (uint8_t j = 0; j < 6; j++) {
        ((struct wire_colors_data *) &canFrame.data)->wires[j] = sent_wires[j];
      }
      sendMessage(MESSAGE_MODULE_SPECIFIC_0, 6);
    }
  }
}

#endif

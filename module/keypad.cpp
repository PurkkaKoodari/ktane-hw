#include "keypad.h"

#if MODULE_TYPE == MODULE_TYPE_KEYPAD

#define KEYPAD_DEBOUNCE_LENGTH 50

const uint8_t button_pins[4] = { BUTTON_PINS };
const uint8_t led_pins[4] = { LED_PINS };

struct keypad_press_data {
  uint8_t position;
};
struct keypad_leds_data {
  uint8_t leds;
};

bool pressed[4] = { 0, 0, 0, 0 };
unsigned long debounce[4] = { 0, 0, 0, 0 };

void moduleInitHardware() {
  for (uint8_t i = 0; i < 4; i++) {
    pinMode(button_pins[i], INPUT_PULLUP);
    digitalWrite(led_pins[i], HIGH);
    pinMode(led_pins[i], OUTPUT);
  }
}

void moduleReset() {
  for (uint8_t i = 0; i < 4; i++) {
    digitalWrite(led_pins[i], HIGH);
  }
}

bool moduleHandleMessage(uint16_t messageId) {
  switch (messageId) {
  case MESSAGE_MODULE_SPECIFIC_1:
    uint8_t leds = (uint8_t) ((struct keypad_leds_data *) &canFrame.data)->leds;
    for (uint8_t i = 0; i < 4; i++) {
      digitalWrite(led_pins[i], !((leds >> i) & 1));
    }
    return true;
  default:
    return false;
  }
}

void moduleLoop() {
  if (mode == GAME) {
    for (uint8_t i = 0; i < 4; i++) {
      bool now = !digitalRead(button_pins[i]);
      if (now != pressed[i] && millis() >= debounce[i]) {
        debounce[i] = millis() + KEYPAD_DEBOUNCE_LENGTH;
        pressed[i] = now;
        if (now) {
          DEBUG_PRINT("press at ");
          DEBUG_PRINTLN(millis());
          ((struct keypad_press_data *) &canFrame.data)->position = i;
          sendMessage(MESSAGE_MODULE_SPECIFIC_0, 1);
        } else {
          DEBUG_PRINT("release at ");
          DEBUG_PRINTLN(millis());
        }
      }
    }
  }
}

#endif

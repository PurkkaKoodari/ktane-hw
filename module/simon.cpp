#include "simon.h"

#if MODULE_TYPE == MODULE_TYPE_SIMON_SAYS

#define SIMON_BLINK_LENGTH 500
#define SIMON_DEBOUNCE_LENGTH 50

enum simon_color : uint8_t {
    NONE = 0, BLUE = 1, YELLOW = 2, GREEN = 3, RED = 4
};

struct simon_color_data {
  uint8_t color;
};

enum simon_color blinking = NONE;
unsigned long blink_until;

bool pressed[4] = { 0, 0, 0, 0 };
unsigned long debounce[4] = { 0, 0, 0, 0 };

const uint8_t button_pins[4] = { BUTTON_BLUE_PIN, BUTTON_YELLOW_PIN, BUTTON_GREEN_PIN, BUTTON_RED_PIN };
const uint8_t led_pins[4] = { LED_BLUE_PIN, LED_YELLOW_PIN, LED_GREEN_PIN, LED_RED_PIN };

void moduleInitHardware() {
  for (uint8_t i = 0; i < 4; i++) {
    pinMode(button_pins[i], INPUT_PULLUP);
    digitalWrite(led_pins[i], LOW);
    pinMode(led_pins[i], OUTPUT);
  }
}

bool moduleHandleMessage(uint16_t messageId) {
  switch (messageId) {
  case MESSAGE_MODULE_SPECIFIC_0:
    DEBUG_PRINT("blink at ");
    DEBUG_PRINTLN(millis());
    blinking = (uint8_t) ((struct simon_color_data *) &canFrame.data)->color;
    blink_until = millis() + SIMON_BLINK_LENGTH;
    return true;
  default:
    return false;
  }
}

void moduleLoop() {
  if (mode == GAME) {
    if (millis() > blink_until) {
      blinking = NONE;
    }
    for (uint8_t i = 0; i < 4; i++) {
      digitalWrite(led_pins[i], (blinking == i + 1) ? HIGH : LOW);
      bool now = !digitalRead(button_pins[i]);
      if (now != pressed[i] && millis() >= debounce[i]) {
        debounce[i] = millis() + SIMON_DEBOUNCE_LENGTH;
        pressed[i] = now;
        if (now) {
          DEBUG_PRINT("press at ");
          DEBUG_PRINTLN(millis());
          ((struct simon_color_data *) &canFrame.data)->color = i + 1;
          sendMessage(MESSAGE_MODULE_SPECIFIC_1, 1);
        } else {
          DEBUG_PRINT("release at ");
          DEBUG_PRINTLN(millis());
        }
      }
    }
  }
}

#endif

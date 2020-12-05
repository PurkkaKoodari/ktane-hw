#include "button.h"

#if MODULE_TYPE == MODULE_TYPE_BUTTON

#define BUTTON_DEBOUNCE_LENGTH 50
#define BUTTON_HOLD_LENGTH 500

bool pressed = 0;
unsigned long hold_trigger = 0;
unsigned long debounce = 0;

enum button_action {
    PRESS, HOLD, RELEASE_PRESS, RELEASE_HOLD;
};

struct button_press_data {
    enum button_action action;
};
struct button_light_data {
  uint8_t color;
};

void moduleInitHardware() {
  pinMode(LED_RED_PIN, OUTPUT);
  digitalWrite(LED_RED_PIN, LOW);
  pinMode(LED_GREEN_PIN, OUTPUT);
  digitalWrite(LED_GREEN_PIN, LOW);
  pinMode(LED_BLUE_PIN, OUTPUT);
  digitalWrite(LED_BLUE_PIN, LOW);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
}

bool moduleHandleMessage(uint16_t messageId) {
  switch (messageId) {
  case MESSAGE_MODULE_SPECIFIC_1:
    uint8_t color = (uint8_t) ((struct button_light_data *) &canFrame.data)->color;
    // TODO: neopixel control
    digitalWrite(LED_RED_PIN, (color >> 2) & 1);
    digitalWrite(LED_GREEN_PIN, (color >> 1) & 1);
    digitalWrite(LED_BLUE_PIN, color & 1);
    return true;
  default:
    return false;
  }
}

void moduleLoop() {
  if (mode == GAME) {
      bool now = !digitalRead(BUTTON_PIN);
      if (now != pressed && millis() >= debounce) {
        pressed = now;
        debounce = millis() + BUTTON_DEBOUNCE_LENGTH;
        if (now) {
          // just pressed
          hold_trigger = millis() + BUTTON_HOLD_LENGTH;
          DEBUG_PRINT("press at ");
          DEBUG_PRINTLN(millis());
          ((struct button_press_data *) &canFrame.data)->action = PRESS;
          sendMessage(MESSAGE_MODULE_SPECIFIC_0, 1);
        } else {
          pressed = 0;
          DEBUG_PRINT("release at ");
          DEBUG_PRINTLN(millis());
          if (hold_trigger == 0) {
          // hold already triggered, send RELEASE_HOLD
            ((struct button_press_data *) &canFrame.data)->action = RELEASE_HOLD;
            sendMessage(MESSAGE_MODULE_SPECIFIC_0, 1);
          } else {
            // hold not triggered yet, send RELEASE_PRESS
            ((struct button_press_data *) &canFrame.data)->action = RELEASE_PRESS;
            sendMessage(MESSAGE_MODULE_SPECIFIC_0, 1);
          }
        }
      }
      if (pressed && hold_trigger != 0 && millis() >= hold_trigger) {
        // held long enough, send HOLD
        DEBUG_PRINT("hold detected at ");
        DEBUG_PRINTLN(millis());
        hold_trigger = 0;
        ((struct button_press_data *) &canFrame.data)->action = HOLD;
        sendMessage(MESSAGE_MODULE_SPECIFIC_1, 1);
      }
    }
  }
}

#endif

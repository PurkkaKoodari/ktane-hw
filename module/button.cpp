#include "button.h"

#if MODULE_TYPE == MODULE_TYPE_BUTTON

#define BUTTON_DEBOUNCE_LENGTH 50
#define BUTTON_HOLD_LENGTH 500

bool pressed = 0;
unsigned long hold_trigger = 0;
unsigned long debounce = 0;

enum button_action : uint8_t {
    PRESS = 0, HOLD = 1, RELEASE_PRESS = 2, RELEASE_HOLD = 3
};

struct button_action_data {
    enum button_action action;
};
struct button_light_data {
  uint8_t red;
  uint8_t green;
  uint8_t blue;
};

CRGB leds[NUM_LEDS];

void moduleInitHardware() {
  pinMode(LED_DATA_PIN, OUTPUT);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  FastLED.addLeds<WS2812B, LED_DATA_PIN, GRB>(leds, NUM_LEDS);
}

void setLightStripColor(uint8_t red, uint8_t green, uint8_t blue) {
  for (uint8_t i = 0; i < NUM_LEDS; i++) {
      leds[i].r = red;
      leds[i].g = green;
      leds[i].b = blue;
    }
    FastLED.show();
}

void moduleReset() {
  setLightStripColor(0, 0, 0);
}

bool moduleHandleMessage(uint16_t messageId) {
  switch (messageId) {
  case MESSAGE_MODULE_SPECIFIC_1:
    uint8_t red = (uint8_t) ((struct button_light_data *) &canFrame.data)->red;
    uint8_t green = (uint8_t) ((struct button_light_data *) &canFrame.data)->green;
    uint8_t blue = (uint8_t) ((struct button_light_data *) &canFrame.data)->blue;
    setLightStripColor(red, green, blue);
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
        ((struct button_action_data *) &canFrame.data)->action = PRESS;
        sendMessage(MESSAGE_MODULE_SPECIFIC_0, 1);
      } else {
        pressed = 0;
        DEBUG_PRINT("release at ");
        DEBUG_PRINTLN(millis());
        if (hold_trigger == 0) {
        // hold already triggered, send RELEASE_HOLD
          ((struct button_action_data *) &canFrame.data)->action = RELEASE_HOLD;
          sendMessage(MESSAGE_MODULE_SPECIFIC_0, 1);
        } else {
          // hold not triggered yet, send RELEASE_PRESS
          ((struct button_action_data *) &canFrame.data)->action = RELEASE_PRESS;
          sendMessage(MESSAGE_MODULE_SPECIFIC_0, 1);
        }
      }
    }
    if (pressed && hold_trigger != 0 && millis() >= hold_trigger) {
      // held long enough, send HOLD
      DEBUG_PRINT("hold detected at ");
      DEBUG_PRINTLN(millis());
      hold_trigger = 0;
      ((struct button_action_data *) &canFrame.data)->action = HOLD;
      sendMessage(MESSAGE_MODULE_SPECIFIC_0, 1);
    }
  }
}

#endif

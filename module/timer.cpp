#include "timer.h"

#if MODULE_TYPE == MODULE_TYPE_TIMER

struct timer_tick_data {
  uint16_t time_left;
  uint16_t timer_speed;
  uint8_t strikes;
  uint8_t max_strikes;
};

unsigned long last_tick;
uint16_t seconds_left;
uint16_t timer_speed;
uint8_t strikes;
uint8_t max_strikes;

HT1632 matrix(HT1632_DATA_PIN, HT1632_WR_PIN, HT1632_CS_PIN, 5, 8);

const uint8_t digits_7seg[10] = {
  0b0111111,
  0b0000110,
  0b1011011,
  0b1001111,
  0b1100110,
  0b1101101,
  0b1111101,
  0b0000111,
  0b1111111,
  0b1101111
};

void moduleInitHardware() {
  matrix.begin();
  delay(50);
  matrix.clear();
  matrix.update();
  pinMode(STRIKE_1_PIN, OUTPUT);
  digitalWrite(STRIKE_1_PIN, LOW);
  pinMode(STRIKE_2_PIN, OUTPUT);
  digitalWrite(STRIKE_2_PIN, LOW);
}

void moduleReset() {
  seconds_left = 0xffff;
  timer_speed = 0;
  strikes = 0;
  max_strikes = 3;
}

void moduleStartTimer() {
  last_tick = millis();
}

bool moduleHandleMessage(uint16_t messageId) {
  switch (messageId) {
  case MESSAGE_MODULE_SPECIFIC_0:
    last_tick = millis();
    seconds_left = ((struct timer_tick_data *) &canFrame.data)->time_left;
    timer_speed = ((struct timer_tick_data *) &canFrame.data)->timer_speed;
    strikes = ((struct timer_tick_data *) &canFrame.data)->strikes;
    max_strikes = ((struct timer_tick_data *) &canFrame.data)->max_strikes;
    DEBUG_PRINT("updated secs ");
    DEBUG_PRINT(seconds_left);
    DEBUG_PRINT(" speed ");
    DEBUG_PRINTLN(timer_speed);
    return true;
  default:
    return false;
  }
}

void moduleLoop() {
  if (mode == CONFIGURATION || mode == GAME) {
    if (exploded) {
      matrix.clear();
      matrix.update();
      digitalWrite(STRIKE_1_PIN, LOW);
      digitalWrite(STRIKE_2_PIN, LOW);
    } else {
      if (seconds_left == 0xffff) {
        matrix.clear();
        matrix.set(0, 6, true);
        matrix.set(1, 6, true);
        matrix.set(2, 6, true);
        matrix.set(3, 6, true);
        matrix.set(4, 7, true);
      } else {
        uint16_t real_speed = mode == GAME && timer_started && !game_ended ? timer_speed : 0;
        unsigned long centis_elapsed = (millis() - last_tick) * real_speed / 2560;
        int16_t seconds_elapsed = (int16_t) (centis_elapsed / 100);
        centis_elapsed %= 100;
        if (seconds_elapsed > 0 && centis_elapsed == 0) {
          centis_elapsed = 100;
          seconds_elapsed -= 1;
        }
        int16_t real_secs_left = (int16_t) seconds_left - seconds_elapsed;
        if (real_secs_left < 0) {
          real_secs_left = 0;
          centis_elapsed = 100;
        }
        uint8_t digits[4];
        if (real_secs_left < 60) {
          digits[0] = digits_7seg[real_secs_left / 10];
          digits[1] = digits_7seg[real_secs_left % 10];
          uint16_t centis_left = 100 - (uint16_t) centis_elapsed;
          digits[2] = digits_7seg[centis_left / 10];
          digits[3] = digits_7seg[centis_left % 10];
        } else {
          uint16_t mins_left = real_secs_left / 60;
          real_secs_left %= 60;
          digits[0] = digits_7seg[mins_left / 10];
          digits[1] = digits_7seg[mins_left % 10];
          digits[2] = digits_7seg[real_secs_left / 10];
          digits[3] = digits_7seg[real_secs_left % 10];
        }
        bool colon_on = centis_elapsed >= 50;
        for (uint8_t i = 0; i < 4; i++) {
          for (uint8_t j = 0; j < 7; j++) {
            matrix.set(i, j, (digits[i] >> j) & 1);
          }
        }
        matrix.set(4, 7, colon_on);
      }
      matrix.update();
      if (strikes == 0) {
        digitalWrite(STRIKE_1_PIN, LOW);
        digitalWrite(STRIKE_2_PIN, LOW);
      } else if (strikes == 1) {
        digitalWrite(STRIKE_1_PIN, HIGH);
        digitalWrite(STRIKE_2_PIN, LOW);
      } else {
        bool state = millis() % 200 < 100 ? HIGH : LOW;
        digitalWrite(STRIKE_1_PIN, state);
        digitalWrite(STRIKE_2_PIN, state);
      }
    }
  }
}

#endif

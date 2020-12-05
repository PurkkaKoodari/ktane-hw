#include "password.h"

#if MODULE_TYPE == MODULE_TYPE_PASSWORD

#define PASSWORD_LENGTH 5
#define PASSWORD_COLUMN_SIZE 6

#define PASSWORD_DEBOUNCE_LENGTH 50

struct password_chars_data {
  uint8_t position;
  uint8_t characters[PASSWORD_COLUMN_SIZE];
};
struct password_submit_data {
  uint8_t word[PASSWORD_LENGTH];
};

uint8_t columns[PASSWORD_LENGTH][PASSWORD_COLUMN_SIZE];
uint8_t positions[PASSWORD_LENGTH];

HT1632 matrix(HT1632_DATA_PIN, HT1632_WR_PIN, HT1632_CS_PIN, 24, 16);

// start positions in HT1632C grid of each character
const uint8_t row_starts[5] = { 0, 0, 0, 7, 7 };
const uint8_t col_starts[5] = { 10, 5, 0, 0, 5 };

// mapping of incoming button states to pressed buttons
#define INV_BTN 0xfe
#define NO_BTN 0xff
const uint8_t button_map[16] = {
  INV_BTN, INV_BTN, INV_BTN, 9, INV_BTN, 5, 3, 6, INV_BTN, 1, 7, 4, 8, 2, 0, NO_BTN
};

uint8_t pressed = 0xff;
unsigned long debounce = 0;

bool submit_pressed = 0;
unsigned long submit_debounce = 0;

uint8_t letters[5] = {
  0, 0, 0, 0, 0
};

void moduleInitHardware() {
  matrix.begin(HT1632_16COM_NMOS);
  delay(50);
  matrix.clear();
  matrix.update();
  pinMode(BTN_PIN_0, INPUT_PULLUP);
  pinMode(BTN_PIN_1, INPUT_PULLUP);
  pinMode(BTN_PIN_2, INPUT_PULLUP);
  pinMode(BTN_PIN_3, INPUT_PULLUP);
  pinMode(SUBMIT_PIN, INPUT_PULLUP);
}

bool moduleHandleMessage(uint16_t messageId) {
  switch (messageId) {
  case MESSAGE_MODULE_SPECIFIC_0:
    uint8_t position = ((struct password_chars_data *) &canFrame.data)->position;
    if (position < PASSWORD_LENGTH) {
      memcpy(columns[position], &((struct password_chars_data *) &canFrame.data)->characters, PASSWORD_COLUMN_SIZE);
    } else {
      DEBUG_PRINTLN("Received password chars for bad position");
      sendError(MESSAGE_RECOVERED_ERROR, ERROR_INVALID_MESSAGE);
    }
    return true;
  default:
    return false;
  }
}

void moduleReset() {
  memset(positions, 0, PASSWORD_LENGTH);
}

void moduleLoop() {
  if (mode == CONFIGURATION || mode == GAME) {
    // read multiplexed buttons
    uint8_t btn_pins = digitalRead(BTN_PIN_0) << 0;
    btn_pins |= digitalRead(BTN_PIN_1) << 1;
    btn_pins |= digitalRead(BTN_PIN_2) << 2;
    btn_pins |= digitalRead(BTN_PIN_3) << 3;
    uint8_t read = button_map[btn_pins];

    if (read != pressed && millis() >= debounce) {
      DEBUG_PRINT2(read, 16);
      DEBUG_PRINTLN(" pressed");
      debounce = millis() + PASSWORD_DEBOUNCE_LENGTH;
      // only accept a new button if it is valid and nothing was previously down
      if (read < INV_BTN && pressed == NO_BTN) {
        uint8_t pos = read >> 1;
        uint8_t direction = read & 1;
        uint8_t curr = positions[pos];
        curr += direction ? PASSWORD_COLUMN_SIZE - 1 : 1;
        curr %= PASSWORD_COLUMN_SIZE;
        positions[pos] = curr;
      }
      pressed = read;
    }
    
    if (mode == GAME) {
      // read submit button separately
      uint8_t submit = !digitalRead(SUBMIT_PIN);
      if (submit != submit_pressed && millis() >= submit_debounce) {
        submit_debounce = millis() + PASSWORD_DEBOUNCE_LENGTH;
        submit_pressed = submit;
        if (submit) {
          DEBUG_PRINTLN("submit pressed");
          for (uint8_t pos = 0; pos < PASSWORD_LENGTH; pos++) {
            ((struct password_submit_data *) &canFrame.data)->word[pos] = columns[pos][positions[pos]];
          }
          sendMessage(MESSAGE_MODULE_SPECIFIC_1, PASSWORD_LENGTH);
        }
      }
    }
    
    matrix.clear();
    if (!exploded) {
      for (uint8_t pos = 0; pos < 5; pos++) {
        uint8_t ch = columns[pos][positions[pos]];
        uint8_t row_start = row_starts[pos];
        uint8_t col_start = col_starts[pos];
        for (uint8_t col = 0; col < 5; col++) {
          uint8_t bits = pgm_read_byte((uint8_t*)font + ch * 5 + col);
          for (uint8_t row = 0; row < 7; row++) {
            matrix.set(row_start + row, col_start + col, (bits >> row) & 1);
          }
        }
      }
    }
    matrix.update();
  }
}

#endif

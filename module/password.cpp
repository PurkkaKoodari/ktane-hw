#include "password.h"

#if MODULE_TYPE == MODULE_TYPE_PASSWORD

#define PASSWORD_LENGTH 5
#define PASSWORD_COLUMN_SIZE 6

struct password_chars_data {
  uint8_t position;
  uint8_t data[7];
};
struct password_event_data {
  uint8_t correct;
};

char columns[PASSWORD_LENGTH][PASSWORD_COLUMN_SIZE];
char solution[PASSWORD_LENGTH];

HT1632 matrix(HT1632_DATA_PIN, HT1632_WR_PIN, HT1632_CS_PIN, 25, 8);

const uint8_t font[128][5] = { TODO };

void moduleInitHardware() {
  matrix.begin();
  delay(50);
  matrix.clear();
  matrix.update();
  // TODO init button pins
}

bool moduleHandleMessage(uint16_t messageId) {
  switch (messageId) {
  case MESSAGE_MODULE_SPECIFIC_0:
    uint8_t position = ((struct password_chars_data *) &canFrame.data)->position;
    if (position < PASSWORD_LENGTH) {
      memcpy(columns[position], &((struct password_chars_data *) &canFrame.data)->data, PASSWORD_COLUMN_SIZE);
    } else if (position == PASSWORD_LENGTH) {
      memcpy(solution, &((struct password_chars_data *) &canFrame.data)->data, PASSWORD_LENGTH);
    } else {
      DEBUG_PRINTLN("received password chars for bad position");
      sendError(MESSAGE_RECOVERED_ERROR, ERROR_INVALID_MESSAGE);
    }
    return true;
  default:
    return false;
  }
}

void moduleLoop() {
  if (mode == GAME) {
    // TODO update HT1632
    // TODO check buttons
  }
}

#endif

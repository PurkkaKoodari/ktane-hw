#include "ventinggas.h"

#if MODULE_TYPE == MODULE_TYPE_VENTING_GAS

LiquidCrystal_I2C lcd(0x27, 16, 2);
Adafruit_LEDBackpack matrix = Adafruit_LEDBackpack();

const char *texts[2] = {"VENT GAS?", "DETONATE?"};

uint8_t char_ae[8] = {
  0b01010,
  0b00000,
  0b00100,
  0b01010,
  0b10001,
  0b11111,
  0b10001,
  0b10001,
};
uint8_t char_oe[8] = {
  0b01010,
  0b00000,
  0b01110,
  0b10001,
  0b10001,
  0b10001,
  0b10001,
  0b01110,
};

const char *answers[2] = {"YES", "NO"};

const uint8_t digits_7seg[10] = {
//  decbfa.g
  0b11111100,
  0b00110000,
  0b11010101,
  0b10110101,
  0b00111001,
  0b10101101,
  0b11101101,
  0b00110100,
  0b11111101,
  0b10111101
};

bool pressed[2] = { 0, 0 };

enum question_id : uint8_t {
  VENT_GAS = 0,
  DETONATE = 1,
  NO_TEXT = 0xff
};

enum answer_id : uint8_t {
  YES = 0,
  NO = 1,
  OUT_OF_TIME = 0xff
};

struct venting_question_data {
  uint8_t text;
};

struct venting_answer_data {
  uint8_t answer;
};

enum screen_state : uint8_t {
  SLEEP = 0,
  QUESTION = 1,
  ANSWER = 2,
  PREVENTS = 3,
  COMPLETE = 4
};

question_id question = NO_TEXT;
answer_id answer = OUT_OF_TIME;
screen_state state = QUESTION;
uint8_t step = 0;
unsigned long nextStep;
unsigned long needyStart = 0;

void clearMatrix() {
  for (uint8_t i = 0; i < 8; i++) {
    matrix.displaybuffer[i] = 0;
  }
  matrix.writeDisplay();
}

void showNumber(uint8_t time_left) {
  uint8_t digits[2] = {digits_7seg[time_left % 10], digits_7seg[time_left / 10]};
  matrix.clear();
  for (uint8_t i = 0; i < 8; i++) {
    uint16_t segs = 0;
    for (uint8_t j = 0; j < 2; j++) {
      segs |= ((digits[j] >> i) & 1) << j;
    }
    matrix.displaybuffer[i] = segs;
  }
  matrix.writeDisplay();
}

void moduleInitHardware() {
  lcd.init();
  lcd.clear();
  lcd.createChar(1, char_ae);
  lcd.createChar(2, char_oe);
  matrix.begin(HT16K33_ADDR);
  clearMatrix();
  pinMode(YES_BTN_PIN, INPUT_PULLUP);
  pinMode(NO_BTN_PIN, INPUT_PULLUP);
}

void moduleReset() {
  char buf[16];
  state = SLEEP;
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Venting Gas");
  lcd.setCursor(0, 1);
  sprintf(buf, "HW %d.%d SW %d.%d \x01\x02", VERSION_HW_MAJOR, VERSION_HW_MINOR, VERSION_SW_MAJOR, VERSION_SW_MINOR);
  lcd.print(buf);
  lcd.backlight();
}

void moduleStartGame() {
  lcd.clear();
  lcd.noBacklight();
}

bool moduleHandleMessage(uint16_t messageId) {
  switch (messageId) {
  case MESSAGE_MODULE_SPECIFIC_0:
    question = (question_id) ((struct venting_question_data *) &canFrame.data)->text;
    return true;
  default:
    return false;
  }
}

void showQuestion() {
  lcd.clear();
  const char *text = texts[question];
  lcd.setCursor(8 - (strlen(text) + 1) / 2, 0);
  lcd.print(text);
  lcd.setCursor(4, 1);
  lcd.print("Y/N");
}

void moduleNeedyActivate() {
  if (question == NO_TEXT) return;
  state = QUESTION;
  lcd.backlight();
  showQuestion();
  needyStart = millis();
}

void moduleNeedyDeactivate() {
  if (state != COMPLETE) {
    state = SLEEP;
    lcd.clear();
    lcd.noBacklight();
  }
}

void moduleDefuse() {
  moduleNeedyDeactivate();
}

void moduleExplode() {
  moduleReset();
}

void moduleLoop() {
  bool yesDown = !digitalRead(YES_BTN_PIN);
  bool yes = !pressed[0] && yesDown;
  pressed[0] = yesDown;

  bool noDown = !digitalRead(NO_BTN_PIN);
  bool no = !pressed[1] && noDown;
  pressed[1] = noDown;

  if (state == SLEEP || state == COMPLETE) {
    clearMatrix();
  } else {
    unsigned long timeUsed = millis() - needyStart;
    if (timeUsed < NEEDY_TIME * 1000ul) {
      uint8_t timeLeft = (uint8_t) ((NEEDY_TIME * 1000ul - timeUsed) / 1000);
      showNumber(timeLeft);
    } else {
      yes = no = false;
      ((struct venting_answer_data *) &canFrame.data)->answer = OUT_OF_TIME;
      sendMessage(MESSAGE_MODULE_SPECIFIC_1, 1);
      state = SLEEP;
      clearMatrix();
    }
  }

  switch (state) {
    case QUESTION:
      if (yes || no) {
        answer = yes ? YES : NO;
        state = ANSWER;
        step = 0;
        nextStep = millis();
      }
      break;
    case ANSWER:
      if (millis() >= nextStep) {
        const char *text = answers[answer];
        uint8_t len = strlen(text);
        if (step == len + 1) {
          if (question == VENT_GAS && answer == NO) {
            state = PREVENTS;
            step = 0;
          } else {
            if (question == VENT_GAS && answer == YES) {
              state = COMPLETE;
              lcd.clear();
              lcd.setCursor(4, 0);
              lcd.print("VENTING");
              lcd.setCursor(4, 1);
              lcd.print("COMPLETE");
            } else {
              state = SLEEP;
              lcd.clear();
              lcd.noBacklight();
            }
            ((struct venting_answer_data *) &canFrame.data)->answer = answer;
            sendMessage(MESSAGE_MODULE_SPECIFIC_1, 1);
          }
        } else if (step == len) {
          step++;
          nextStep += 500;
        } else {
          lcd.setCursor(8 + step, 1);
          lcd.write(text[step]);
          step++;
          nextStep += 1500 / len;
        }
      }
      break;
    case PREVENTS:
      if (millis() >= nextStep) {
        if (step == 5) {
          state = QUESTION;
          showQuestion();
        } else if (step % 2 == 1) {
          lcd.clear();
          step++;
          nextStep += 400;
        } else {
          lcd.clear();
          lcd.setCursor(0, 0);
          lcd.print("VENTING PREVENTS");
          lcd.setCursor(3, 1);
          lcd.print("EXPLOSIONS");
          step++;
          nextStep += step == 4 ? 1000 : 750;
        }
      }
      break;
    default:
      break;
  }
}

#endif

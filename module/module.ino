#include <mcp2515.h>
#include <can.h>

#include "module.h"

#include "timer.h"
#include "wires.h"
#include "password.h"
#include "simon.h"

//////////////////////////// SANITY CHECKS ////////////////////////////

#ifndef MODULE_TYPE
#error "No module type set!"
#endif
#if MODULE_TYPE > MODULEID_TYPE_MAX
#error "Bad module id!"
#endif
#if MODULE_SERIAL > MODULEID_SERIAL_MAX
#error "Bad module serial!"
#endif
#if !defined(NO_STATUS_LED) && (!defined(STRIKE_LED_PIN) || !defined(SOLVE_LED_PIN))
#error "Either NO_STATUS_LED or STRIKE_LED_PIN and SOLVE_LED_PIN must be defined"
#endif

//////////////////////////// GLOBAL DATA ////////////////////////////

enum module_mode mode = RESET;
bool solved = false;
unsigned long strike_until = 0;
bool timer_started = false;
bool game_ended = false;
bool exploded = false;

//////////////////////////// CAN MESSAGING ////////////////////////////

MCP2515 canBus(MCP_CS_PIN);
struct can_frame canFrame;

bool incoming = false;

void messageReceived() {
  incoming = true;
}

void sendMessage(uint16_t message_id, uint8_t dlc) {
  canFrame.can_id = CAN_EFF_FLAG | CAN_TX_ID | (message_id << MESSAGE_ID_OFFSET);
  canFrame.can_dlc = dlc;
  if (canBus.sendMessage(&canFrame) != MCP2515::ERROR_OK) {
    DEBUG_PRINTLN("tx failed");
  }
}

void sendError(uint16_t message_id, uint8_t code) {
  ((struct error_data *) &canFrame.data)->code = code;
  sendMessage(message_id, 1);
}

//////////////////////////// DEFAULT EMPTY EVENT HANDLERS ////////////////////////////

__attribute__((weak)) void moduleReset() {}
__attribute__((weak)) void moduleStartGame() {}
__attribute__((weak)) void moduleStartTimer() {}
__attribute__((weak)) void moduleExplode() {}
__attribute__((weak)) void moduleDefuse() {}
__attribute__((weak)) void moduleSolve() {}
__attribute__((weak)) void moduleStrike() {}

//////////////////////////// MAIN FUNCTIONS ////////////////////////////

void initHardware() {
  pinMode(MODULE_ENABLE_PIN, INPUT);
#ifndef NO_STATUS_LED
  pinMode(STRIKE_LED_PIN, OUTPUT);
  digitalWrite(STRIKE_LED_PIN, LOW);
  pinMode(SOLVE_LED_PIN, OUTPUT);
  digitalWrite(SOLVE_LED_PIN, LOW);
#endif
  moduleInitHardware();
}

void resetModule() {
  mode = RESET;
  timer_started = false;
  game_ended = false;
  exploded = false;
  solved = false;
  strike_until = 0;
  moduleReset();
}

void handleMessage() {
#ifdef DEBUG
  char statusMsg[64];
  char hexNumber[4];
  sprintf(statusMsg, "rx id %08x dlc %hhx data", canFrame.can_id, canFrame.can_dlc);
  for (int i = 0; i < canFrame.can_dlc; i++) {
    sprintf(hexNumber, " %02x", canFrame.data[i]);
    strcat(statusMsg, hexNumber);
  }
  DEBUG_PRINTLN(statusMsg);
#endif

  uint16_t messageId = (uint16_t) ((canFrame.can_id & MESSAGE_ID_MASK) >> MESSAGE_ID_OFFSET);

  if (messageId == MESSAGE_RESET) {
    DEBUG_PRINTLN("resetting module");
    resetModule();
    return;
  }

  if (mode == RESET) return;
  
  switch (messageId) {
  case MESSAGE_PING:
    DEBUG_PRINT("responding to ping ");
    DEBUG_PRINTLN(((struct ping_data *) &canFrame.data)->number);
    sendMessage(MESSAGE_PING, 1);
    break;
  case MESSAGE_LAUNCH_GAME:
    if (mode != CONFIGURATION) {
      DEBUG_PRINTLN("MESSAGE_LAUNCH_GAME received in bad mode");
      sendError(MESSAGE_RECOVERED_ERROR, ERROR_INVALID_MESSAGE);
      return;
    }
    DEBUG_PRINTLN("game starting!");
    mode = GAME;
    moduleStartGame();
    break;
  case MESSAGE_START_TIMER:
    DEBUG_PRINTLN("timer starting!");
    timer_started = true;
    moduleStartTimer();
    break;
  case MESSAGE_EXPLODE:
    DEBUG_PRINTLN("bomb exploded!");
    game_ended = true;
    exploded = true;
    moduleExplode();
    break;
  case MESSAGE_DEFUSE:
    DEBUG_PRINTLN("bomb defused!");
    game_ended = true;
    moduleDefuse();
    break;
  case MESSAGE_STRIKE:
    strike_until = millis() + 1000;
    moduleStrike();
    break;
  case MESSAGE_SOLVE:
    strike_until = 0;
    solved = true;
    moduleSolve();
    break;
  case MESSAGE_MODULE_SPECIFIC_0:
  case MESSAGE_MODULE_SPECIFIC_1:
  case MESSAGE_MODULE_SPECIFIC_2:
  case MESSAGE_MODULE_SPECIFIC_3:
  case MESSAGE_MODULE_SPECIFIC_4:
  case MESSAGE_MODULE_SPECIFIC_5:
  case MESSAGE_MODULE_SPECIFIC_6:
  case MESSAGE_MODULE_SPECIFIC_7:
  case MESSAGE_MODULE_SPECIFIC_8:
  case MESSAGE_MODULE_SPECIFIC_9:
  case MESSAGE_MODULE_SPECIFIC_A:
  case MESSAGE_MODULE_SPECIFIC_B:
  case MESSAGE_MODULE_SPECIFIC_C:
  case MESSAGE_MODULE_SPECIFIC_D:
  case MESSAGE_MODULE_SPECIFIC_E:
  case MESSAGE_MODULE_SPECIFIC_F:
    if (moduleHandleMessage(messageId))
      break;
  default:
    DEBUG_PRINTLN("unknown message received");
    sendError(MESSAGE_RECOVERED_ERROR, ERROR_INVALID_MESSAGE);
    break;
  }
}

void setup() {
#ifdef DEBUG
  Serial.begin(9600);
#endif
  DEBUG_PRINTLN("can init");
  while (true) {
    if (canBus.reset() != MCP2515::ERROR_OK) goto can_init_fail;
    if (canBus.setBitrate(CAN_100KBPS, MCP_8MHZ) != MCP2515::ERROR_OK) goto can_init_fail;
    if (canBus.setFilterMask(MCP2515::MASK0, true, CAN_RX_MASK) != MCP2515::ERROR_OK) goto can_init_fail;
    if (canBus.setFilter(MCP2515::RXF0, true, CAN_UNICAST_FILTER) != MCP2515::ERROR_OK) goto can_init_fail;
    if (canBus.setFilter(MCP2515::RXF1, true, CAN_BROADCAST_FILTER) != MCP2515::ERROR_OK) goto can_init_fail;
    if (canBus.setNormalMode() != MCP2515::ERROR_OK) goto can_init_fail;
    break;
    can_init_fail:
    DEBUG_PRINTLN("can init failed, retrying");
    delay(100);
  }
  DEBUG_PRINTLN("can init success");
  moduleInitHardware();
  resetModule();
  attachInterrupt(digitalPinToInterrupt(MCP_INTERRUPT_PIN), messageReceived, FALLING);
}

void loop() {
  if (mode == RESET && !digitalRead(MODULE_ENABLE_PIN)) {
    DEBUG_PRINTLN("announcing module");
    *(struct announce_data *) &canFrame.data = {
      VERSION_HW_MAJOR, VERSION_HW_MINOR,
      VERSION_SW_MAJOR, VERSION_SW_MINOR,
      ANNOUNCE_FLAG_INIT_COMPLETE
    };
    sendMessage(MESSAGE_ANNOUNCE, 5);
    mode = CONFIGURATION;
  }
  
#ifndef NO_STATUS_LED
  if (mode == GAME && !exploded) {
    if (solved) {
      digitalWrite(STRIKE_LED_PIN, LOW);
      digitalWrite(SOLVE_LED_PIN, HIGH);
    } else if (millis() < strike_until) {
      digitalWrite(STRIKE_LED_PIN, HIGH);
      digitalWrite(SOLVE_LED_PIN, LOW);
    } else {
      digitalWrite(STRIKE_LED_PIN, LOW);
      digitalWrite(SOLVE_LED_PIN, LOW);
    }
  } else {
    digitalWrite(STRIKE_LED_PIN, LOW);
    digitalWrite(SOLVE_LED_PIN, LOW);
  }
#endif

  moduleLoop();
  
  if (incoming) {
    uint8_t intByte = canBus.getInterrupts();
    if (intByte & MCP2515::CANINTF_RX0IF) {
      if (canBus.readMessage(MCP2515::RXB0, &canFrame) == MCP2515::ERROR_OK) {
        handleMessage();
      } else {
        DEBUG_PRINTLN("rx RXB0 failed");
      }
    }
    if (intByte & MCP2515::CANINTF_RX1IF) {
      if (canBus.readMessage(MCP2515::RXB1, &canFrame) == MCP2515::ERROR_OK) {
        handleMessage();
      } else {
        DEBUG_PRINTLN("rx RXB1 failed");
      }
    }
    if (intByte & MCP2515::CANINTF_MERRF) {
      DEBUG_PRINTLN("message error");
      canBus.clearMERR();
    }
    if (intByte & MCP2515::CANINTF_ERRIF) {
      DEBUG_PRINT("error state ");
      DEBUG_PRINTLN2(canBus.getErrorFlags(), 2);
      canBus.clearRXnOVR();
    }
  }
}

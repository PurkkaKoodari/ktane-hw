#include <mcp2515.h>
#include <can.h>

#include "module.h"

#include "timer.h"
#include "wires.h"
#include "password.h"
#include "simon.h"
#include "ventinggas.h"
#include "button.h"
#include "keypad.h"

//////////////////////////// SANITY CHECKS ////////////////////////////

#ifndef MODULE_TYPE
#error "No module type set."
#endif
#if MODULE_TYPE <= 0
#error "Module id can't be zero or negative."
#endif
#if MODULE_TYPE > MODULEID_TYPE_MAX
#error "Too large module id."
#endif

#if MODULE_SERIAL < 0
#error "Module serial can't be negative."
#endif
#if MODULE_SERIAL > MODULEID_SERIAL_MAX
#error "Too large module serial."
#endif

#ifndef MODULE_NAME
#error "No module name set. New module and header not #included in module.ino?"
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

volatile bool incoming = false;

void messageReceived() {
  incoming = true;
}

void sendMessage(uint16_t message_id, uint8_t dlc) {
  canFrame.can_id = CAN_EFF_FLAG | CAN_TX_ID | (message_id << MESSAGE_ID_OFFSET);
  canFrame.can_dlc = dlc;
#ifdef DEBUG_CAN_MESSAGES
#ifdef DEBUG
  DEBUG_PRINT("TX id ");
  DEBUG_PRINT2(canFrame.can_id, 16);
  DEBUG_PRINT(" dlc ");
  DEBUG_PRINT2(canFrame.can_dlc, 16);
  DEBUG_PRINT(" data");
  for (int i = 0; i < canFrame.can_dlc; i++) {
    DEBUG_PRINT(" ");
    DEBUG_PRINT2(canFrame.data[i], 16);
  }
  DEBUG_PRINTLN("");
#endif
#endif
  if (canBus.sendMessage(&canFrame) != MCP2515::ERROR_OK) {
    DEBUG_PRINTLN("TX failed");
  } else {
    DEBUG_PRINTLN("TX succeeded");
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
__attribute__((weak)) void moduleNeedyActivate() {}
__attribute__((weak)) void moduleNeedyDeactivate() {}

//////////////////////////// MAIN FUNCTIONS ////////////////////////////

void initHardware() {
  pinMode(MODULE_READY_PIN, OUTPUT);
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
  DEBUG_PRINTLN("Resetting module");
  mode = RESET;
  digitalWrite(MODULE_READY_PIN, LOW);
  timer_started = false;
  game_ended = false;
  exploded = false;
  solved = false;
  strike_until = 0;
  moduleReset();
}

void handleMessage() {
#ifdef DEBUG_CAN_MESSAGES
#ifdef DEBUG
  DEBUG_PRINT("RX id ");
  DEBUG_PRINT2(canFrame.can_id, 16);
  DEBUG_PRINT(" dlc ");
  DEBUG_PRINT2(canFrame.can_dlc, 16);
  DEBUG_PRINT(" data");
  for (int i = 0; i < canFrame.can_dlc; i++) {
    DEBUG_PRINT(" ");
    DEBUG_PRINT2(canFrame.data[i], 16);
  }
  DEBUG_PRINTLN("");
#endif
#endif

  uint16_t messageId = (uint16_t) ((canFrame.can_id & MESSAGE_ID_MASK) >> MESSAGE_ID_OFFSET);

  if (messageId == MESSAGE_RESET) {
    resetModule();
    return;
  }

  if (mode == RESET) return;
  
  switch (messageId) {
  case MESSAGE_PING:
    DEBUG_PRINT("Responding to ping ");
    DEBUG_PRINTLN(((struct ping_data *) &canFrame.data)->number);
    sendMessage(MESSAGE_PING, 1);
    break;
  case MESSAGE_LAUNCH_GAME:
    if (mode != CONFIGURATION) {
      DEBUG_PRINTLN("MESSAGE_LAUNCH_GAME received in bad mode");
      sendError(MESSAGE_RECOVERED_ERROR, ERROR_INVALID_MESSAGE);
      return;
    }
    DEBUG_PRINTLN("Game starting!");
    mode = GAME;
    moduleStartGame();
    break;
  case MESSAGE_START_TIMER:
    DEBUG_PRINTLN("Timer starting!");
    timer_started = true;
    moduleStartTimer();
    break;
  case MESSAGE_EXPLODE:
    DEBUG_PRINTLN("Bomb exploded!");
    game_ended = true;
    exploded = true;
    moduleExplode();
    break;
  case MESSAGE_DEFUSE:
    DEBUG_PRINTLN("Bomb defused!");
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
  case MESSAGE_NEEDY_ACTIVATE:
    moduleNeedyActivate();
    break;
  case MESSAGE_NEEDY_DEACTIVATE:
    moduleNeedyDeactivate();
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
    [[fallthrough]];
  default:
    DEBUG_PRINTLN("Unknown message received");
    sendError(MESSAGE_RECOVERED_ERROR, ERROR_INVALID_MESSAGE);
    break;
  }
}

void setup() {
  Serial.begin(9600);
  Serial.println("BombGame module starting");
  Serial.println("Module: " MODULE_NAME " (id " QUOTE2(MODULE_TYPE) ")");
  Serial.println("Version: HW/" QUOTE2(VERSION_HW_MAJOR) "." QUOTE2(VERSION_HW_MINOR) " SW/" QUOTE2(VERSION_SW_MAJOR) "." QUOTE2(VERSION_SW_MINOR));
  DEBUG_PRINTLN("CAN init");
  while (true) {
    if (canBus.reset() != MCP2515::ERROR_OK) goto can_init_fail;
    if (canBus.setBitrate(CAN_100KBPS, MCP_8MHZ) != MCP2515::ERROR_OK) goto can_init_fail;
    if (canBus.setFilterMask(MCP2515::MASK0, true, CAN_RX_MASK) != MCP2515::ERROR_OK) goto can_init_fail;
    if (canBus.setFilter(MCP2515::RXF0, true, CAN_UNICAST_FILTER) != MCP2515::ERROR_OK) goto can_init_fail;
    if (canBus.setFilter(MCP2515::RXF1, true, CAN_BROADCAST_FILTER) != MCP2515::ERROR_OK) goto can_init_fail;
    if (canBus.setNormalMode() != MCP2515::ERROR_OK) goto can_init_fail;
    break;
    can_init_fail:
    Serial.println("CAN init failed, retrying");
    delay(100);
  }
  DEBUG_PRINTLN("CAN init success");
  initHardware();
  resetModule();
  attachInterrupt(digitalPinToInterrupt(MCP_INTERRUPT_PIN), messageReceived, FALLING);
  Serial.println("Module init success");
}

void loop() {
  if (mode == RESET && !digitalRead(MODULE_ENABLE_PIN)) {
    digitalWrite(MODULE_READY_PIN, HIGH);
    DEBUG_PRINTLN("Announcing module");
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
        DEBUG_PRINTLN("Read from RXB0 failed");
      }
    }
    if (intByte & MCP2515::CANINTF_RX1IF) {
      if (canBus.readMessage(MCP2515::RXB1, &canFrame) == MCP2515::ERROR_OK) {
        handleMessage();
      } else {
        DEBUG_PRINTLN("Read from RXB1 failed");
      }
    }
    if (intByte & MCP2515::CANINTF_MERRF) {
      DEBUG_PRINTLN("Message error");
      canBus.clearMERR();
    }
    if (intByte & MCP2515::CANINTF_ERRIF) {
      uint8_t errByte = canBus.getErrorFlags();
      canBus.clearRXnOVR();
      DEBUG_PRINTLN("MCP2515 error state:");
      if (errByte & MCP2515::EFLG_RX1OVR) {
        DEBUG_PRINTLN("RXB1 overflow");
      }
      if (errByte & MCP2515::EFLG_RX0OVR) {
        DEBUG_PRINTLN("RXB0 overflow");
      }
      if (errByte & MCP2515::EFLG_TXBO) {
        DEBUG_PRINTLN("Bus-Off mode");
      }
      if (errByte & MCP2515::EFLG_TXEP) {
        DEBUG_PRINTLN("TX Error-Passive");
      }
      if (errByte & MCP2515::EFLG_RXEP) {
        DEBUG_PRINTLN("RX Error-Passive");
      }
    }
  }
}

#ifndef BOMB_MODULE_H
#define BOMB_MODULE_H

#include <Arduino.h>
#include <can.h>

//////////////////////////// UTILITY MACROS ////////////////////////////
#define QUOTE(arg) #arg
#define QUOTE2(arg) QUOTE(arg)

//////////////////////////// MODULE TYPE CONSTANTS ////////////////////////////

#define MODULE_TYPE_TIMER 1
#define MODULE_TYPE_WIRES 2
#define MODULE_TYPE_BUTTON 3
#define MODULE_TYPE_KEYPAD 4
#define MODULE_TYPE_SIMON_SAYS 5
#define MODULE_TYPE_COMPLICATED_WIRES 9
#define MODULE_TYPE_PASSWORD 12
#define MODULE_TYPE_VENTING_GAS 13

//////////////////////////// INCLUDE CONFIG FILE ////////////////////////////
#include "module_config.h"

//////////////////////////// GLOBAL PIN DEFINITIONS ////////////////////////////

#define MCP_CS_PIN 8
#define MCP_INTERRUPT_PIN 2

#define MODULE_READY_PIN A2
#define MODULE_ENABLE_PIN A3

//////////////////////////// MESSAGE FORMAT CONSTANTS ////////////////////////////

#define MESSAGE_DIRECTION_BITS 1
#define MESSAGE_MODULE_TYPE_BITS 12
#define MESSAGE_MODULE_SERIAL_BITS 10
#define MESSAGE_ID_BITS 6

#define MESSAGE_DIRECTION_OFFSET 28
#define MESSAGE_MODULE_TYPE_OFFSET 16
#define MESSAGE_MODULE_SERIAL_OFFSET 6
#define MESSAGE_ID_OFFSET 0

#define MESSAGE_DIRECTION_MASK (((1L << MESSAGE_DIRECTION_BITS) - 1) << MESSAGE_DIRECTION_OFFSET)
#define MESSAGE_MODULE_TYPE_MASK (((1L << MESSAGE_MODULE_TYPE_BITS) - 1) << MESSAGE_MODULE_TYPE_OFFSET)
#define MESSAGE_MODULE_SERIAL_MASK (((1L << MESSAGE_MODULE_SERIAL_BITS) - 1) << MESSAGE_MODULE_SERIAL_OFFSET)
#define MESSAGE_ID_MASK (((1L << MESSAGE_ID_BITS) - 1) << MESSAGE_ID_OFFSET)

#define MODULEID_TYPE_MAX ((1L << MESSAGE_MODULE_TYPE_BITS) - 1)
#define MODULEID_SERIAL_MAX ((1L << MESSAGE_MODULE_SERIAL_BITS) - 1)

#define CAN_DIRECTION_OUT 0L
#define CAN_DIRECTION_IN 1L

#define CAN_RX_MASK (MESSAGE_DIRECTION_MASK | MESSAGE_MODULE_TYPE_MASK | MESSAGE_MODULE_SERIAL_MASK)
#define CAN_UNICAST_FILTER ((CAN_DIRECTION_OUT << MESSAGE_DIRECTION_OFFSET) | \
                            ((uint32_t) MODULE_TYPE << MESSAGE_MODULE_TYPE_OFFSET) | \
                            ((uint32_t) MODULE_SERIAL << MESSAGE_MODULE_SERIAL_OFFSET))
#define CAN_BROADCAST_FILTER ((CAN_DIRECTION_OUT << MESSAGE_DIRECTION_OFFSET) | \
                              (0L << MESSAGE_MODULE_TYPE_OFFSET) | \
                              (0L << MESSAGE_MODULE_SERIAL_OFFSET))
#define CAN_TX_ID ((CAN_DIRECTION_IN << MESSAGE_DIRECTION_OFFSET) | \
                   ((uint32_t) MODULE_TYPE << MESSAGE_MODULE_TYPE_OFFSET) | \
                   ((uint32_t) MODULE_SERIAL << MESSAGE_MODULE_SERIAL_OFFSET))

//////////////////////////// MESSAGE CONSTANTS AND FORMATS ////////////////////////////

#define MESSAGE_RESET 0x00
#define MESSAGE_ANNOUNCE 0x01
#define MESSAGE_INIT_COMPLETE 0x02
#define MESSAGE_PING 0x03
#define MESSAGE_LAUNCH_GAME 0x10
#define MESSAGE_START_TIMER 0x11
#define MESSAGE_EXPLODE 0x12
#define MESSAGE_DEFUSE 0x13
#define MESSAGE_STRIKE 0x14
#define MESSAGE_SOLVE 0x15
#define MESSAGE_NEEDY_ACTIVATE 0x16
#define MESSAGE_NEEDY_DEACTIVATE 0x17
#define MESSAGE_RECOVERABLE_ERROR 0x20
#define MESSAGE_RECOVERED_ERROR 0x21
#define MESSAGE_MINOR_UNRECOVERABLE_ERROR 0x22
#define MESSAGE_MAJOR_UNRECOVERABLE_ERROR 0x23
#define MESSAGE_MODULE_SPECIFIC_0 0x30
#define MESSAGE_MODULE_SPECIFIC_1 0x31
#define MESSAGE_MODULE_SPECIFIC_2 0x32
#define MESSAGE_MODULE_SPECIFIC_3 0x33
#define MESSAGE_MODULE_SPECIFIC_4 0x34
#define MESSAGE_MODULE_SPECIFIC_5 0x35
#define MESSAGE_MODULE_SPECIFIC_6 0x36
#define MESSAGE_MODULE_SPECIFIC_7 0x37
#define MESSAGE_MODULE_SPECIFIC_8 0x38
#define MESSAGE_MODULE_SPECIFIC_9 0x39
#define MESSAGE_MODULE_SPECIFIC_A 0x3A
#define MESSAGE_MODULE_SPECIFIC_B 0x3B
#define MESSAGE_MODULE_SPECIFIC_C 0x3C
#define MESSAGE_MODULE_SPECIFIC_D 0x3D
#define MESSAGE_MODULE_SPECIFIC_E 0x3E
#define MESSAGE_MODULE_SPECIFIC_F 0x3F

#define ERROR_INVALID_MESSAGE 0x00
#define ERROR_HARDWARE 0x01
#define ERROR_SOFTWARE 0x02

struct announce_data {
  uint8_t hw_major;
  uint8_t hw_minor;
  uint8_t sw_major;
  uint8_t sw_minor;
  uint8_t flags;
};

struct ping_data {
  uint8_t number;
};

struct error_data {
  uint8_t code;
  uint8_t details[7];
};

#define ANNOUNCE_FLAG_INIT_COMPLETE 0x01

//////////////////////////// DEBUG MACROS ////////////////////////////

#ifdef DEBUG
#define DEBUG_PRINT(x) Serial.print(x)
#define DEBUG_PRINT2(x, y) Serial.print(x, y)
#define DEBUG_PRINTLN(x) Serial.println(x)
#define DEBUG_PRINTLN2(x, y) Serial.println(x, y)
#else
#define DEBUG_PRINT(x)
#define DEBUG_PRINT2(x, y)
#define DEBUG_PRINTLN(x)
#define DEBUG_PRINTLN2(x, y)
#endif

//////////////////////////// GLOBAL DATA ////////////////////////////

enum module_mode {
  RESET, INITIALIZATION, CONFIGURATION, GAME
};

extern enum module_mode mode;
extern bool solved;
extern bool timer_started;
extern bool game_ended;
extern bool exploded;

extern can_frame canFrame;

void sendMessage(uint16_t message_id, uint8_t data_length);

void sendError(uint16_t message_id, uint8_t code);

//////////////////////////// MODULE SPECIFIC FUNCTIONS ////////////////////////////

void moduleInitHardware();

void moduleReset();
void moduleStartGame();
void moduleStartTimer();
void moduleExplode();
void moduleDefuse();
void moduleSolve();
void moduleStrike();

bool moduleHandleMessage(uint16_t message_id);

void moduleLoop();

#endif

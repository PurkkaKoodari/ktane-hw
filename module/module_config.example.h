// Define DEBUG to enable serial output.
#define DEBUG

// Define DEBUG_CAN_MESSAGES to also dump all CAN messages to serial.
//#define DEBUG_CAN_MESSAGES

// Module type, chooses which module's code to build. Choose one from module.h.
#define MODULE_TYPE MODULE_TYPE_KEYPAD

// Serial number, must be unique among copies of the same module used in the same bomb.
#define MODULE_SERIAL 1

// Hardware version. Can be used by the module code to support hardware revisions.
#define VERSION_HW_MAJOR 1
#define VERSION_HW_MINOR 0

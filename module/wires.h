#include "module.h"

#if MODULE_TYPE == MODULE_TYPE_WIRES

#if VERSION_HW_MAJOR != 1 || VERSION_HW_MINOR != 0
#error This version of the module software does not support the configured hardware version.
#endif

#define VERSION_SW_MAJOR 1
#define VERSION_SW_MINOR 0

#define WIRE_PINS 8, 7, 6, 5, 4, 3

#define STRIKE_LED_PIN A0
#define SOLVE_LED_PIN A1

#define ERROR_WIRE_NOT_CONNECTED 16

#endif

#include "module.h"

#if MODULE_TYPE == MODULE_TYPE_WIRES || MODULE_TYPE == MODULE_TYPE_COMPLICATED_WIRES

#if VERSION_HW_MAJOR != 1 || VERSION_HW_MINOR != 0
#error This version of the module software does not support the configured hardware version.
#endif

#if MODULE_TYPE == MODULE_TYPE_WIRES
#define MODULE_NAME "Wires"
#else
#define MODULE_NAME "Complicated Wires"
#endif

#define VERSION_SW_MAJOR 1
#define VERSION_SW_MINOR 0

#if MODULE_TYPE == MODULE_TYPE_COMPLICATED_WIRES
#define WIRE_PINS A7, A6, A5, A4, A1, A0
#define LED_ROW_PINS 7, 4
#define LED_COLUMN_PINS 6, 5, 3
#else
#define WIRE_PINS A0, A1, A4, A5, A6, A7
#endif

#define STRIKE_LED_PIN 9
#define SOLVE_LED_PIN 10

#endif

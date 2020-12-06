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

#define OUTPUT_PINS A1, A4
#define INPUT_PINS A5, A6, A7

#if MODULE_TYPE == MODULE_TYPE_COMPLICATED_WIRES
#define LED_PINS 9, 6, 5, 3, 7, 4
#endif

#define STRIKE_LED_PIN A0
#define SOLVE_LED_PIN 10

#endif

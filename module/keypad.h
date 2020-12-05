#include "module.h"

#if MODULE_TYPE == MODULE_TYPE_KEYPAD

#if VERSION_HW_MAJOR != 1 || VERSION_HW_MINOR != 0
#error This version of the module software does not support the configured hardware version.
#endif

#define MODULE_NAME "Keypad"

#define VERSION_SW_MAJOR 1
#define VERSION_SW_MINOR 0

#define BUTTON_PINS 7, 9, A4, A5
#define LED_PINS 3, 4, 5, 6

#define STRIKE_LED_PIN A0
#define SOLVE_LED_PIN A1

#endif

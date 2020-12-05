#include "module.h"

#if MODULE_TYPE == MODULE_TYPE_BUTTON

#if VERSION_HW_MAJOR != 1 || VERSION_HW_MINOR != 0
#error This version of the module software does not support the configured hardware version.
#endif

#define MODULE_NAME "Button"

#define VERSION_SW_MAJOR 1
#define VERSION_SW_MINOR 0

#define BUTTON_PIN 4

#define LED_RED_PIN 3
#define LED_GREEN_PIN 5
#define LED_BLUE_PIN 6

#define STRIKE_LED_PIN A0
#define SOLVE_LED_PIN A1

#endif

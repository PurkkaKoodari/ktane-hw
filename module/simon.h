#include "module.h"

#if MODULE_TYPE == MODULE_TYPE_SIMON_SAYS

#if VERSION_HW_MAJOR != 1 || VERSION_HW_MINOR != 0
#error This version of the module software does not support the configured hardware version.
#endif

#define VERSION_SW_MAJOR 1
#define VERSION_SW_MINOR 0

#define MODULE_NAME "Simon Says"

#define LED_BLUE_PIN A0
#define LED_YELLOW_PIN 4
#define LED_GREEN_PIN A1
#define LED_RED_PIN A2
#define BUTTON_BLUE_PIN 7
#define BUTTON_YELLOW_PIN 6
#define BUTTON_GREEN_PIN 5
#define BUTTON_RED_PIN 8

#define STRIKE_LED_PIN A5
#define SOLVE_LED_PIN A4

#endif

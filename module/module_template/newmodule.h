#include "module.h"

// Change this to check for your module ID.
#if MODULE_TYPE == MODULE_TYPE_???


// Check that the hardware version is supported by this version of the module software.
#if VERSION_HW_MAJOR != 1 || VERSION_HW_MINOR != 0
#error This version of the module software does not support the configured hardware version.
#endif


// Define the version of your software here.
#define VERSION_SW_MAJOR 1
#define VERSION_SW_MINOR 0


// Include any necessary libraries for your module here.
// #include <somelibrary.h>


// Uncomment and edit one of the following:

// For non-needy modules: declare the "strike" (red) and "solve" (green) pins of the RGB LED.
// These are the defaults.
// #define STRIKE_LED_PIN A0
// #define SOLVE_LED_PIN A1

// For needy, timer or other special modules: declare that you have no RGB LED.
// #define NO_STATUS_LED

#endif

// Change this to use your new header file.
#include "newmodule.h"

// Change this to check for your module ID.
#if MODULE_TYPE == MODULE_TYPE_???

// Place here whatever definitions or functions you need for your module.

// The following three functions are required for all modules:

void moduleInitHardware() {
  // Called once from setup().
  // Initialize any pins, peripherals or memory here.
}

bool moduleHandleMessage(uint16_t messageId) {
  switch (messageId) {
  // Add a case for each MESSAGE_MODULE_SPECIFIC_X you will handle.
  case MESSAGE_MODULE_SPECIFIC_?:
    // Do whatever the message needs you to do and respond if necessary.
    // Return true to indicate that you successfully processed the message.
    // If you return an error yourself, return true as well.
    return true;
  default:
    // Return false to indicate that the message ID was invalid.
    return false;
  }
}

void moduleLoop() {
  // Code to run continuously, called from loop().
  // Don't take too long or it can cause CAN messages to be backed up in the MCP2515.
}

// Implement any number of the following methods.
// Don't take too long in them, prefer to check up on long-running operations in moduleLoop() instead.

// void moduleReset() {
//   // Called when the module is requested to reset, including on power-up after moduleInitHardware().
// }

// void moduleStartGame() {
//   // Called when the game starts (i.e. settings are dialed in but the timer has not started).
// }

// void moduleStartTimer() {
//   // Called when the timer starts.
// }

// void moduleExplode() {
//   // Called when the bomb explodes.
// }

// void moduleDefuse() {
//   // Called when the bomb is defused.
// }

// void moduleSolve() {
//   // Called when this module is solved.
// }

// void moduleStrike() {
//   // Called when this module receives a strike.
// }

#endif

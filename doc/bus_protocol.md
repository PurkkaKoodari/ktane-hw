# Bus protocol

This document specifies the protocol used for communication over the CAN bus between modules and the main controller.

This specification is version `1.0-alpha5`.

## Definitions

In this document, the following terms and abbreviations are used:

- **MC** = **main controller** = the device that stores the states of all modules
- **module** = the swappable modules that are visible to the user

## Message types

Both the MC and modules can initiate messages.

The MC can send _request_ messages to modules. Some _requests_ require _responses_ from the modules. Responses SHOULD use the same message ID as the request.

Only the MC can send _broadcast_ messages to all modules. Broadcast messages SHOULD NOT require responses.

Modules can send _event_ messages to the MC. Event messages MUST NOT require responses from the MC. After sending an event message, a module MUST be ready to receive any unrelated message; state changes caused by event messages are to be handled asynchronously.

## Module states

When a module is powered up, it is in _power-on mode_. Modules in this mode MUST NOT react to any message except for the Reset (0x00) message.

When a module receives a Reset (0x00) message, it enters _reset mode_. Modules in this mode MUST set the MODULE_READY signal low, MUST NOT respond to Ping (0x03) messages and SHOULD NOT send any messages before they receive an Initialize (0x02) message.

When a module in _reset mode_ receives an Initialize (0x02) message, it enters _configuration mode_. This mode is used to send game settings to modules using module-specific messages.

When a module in _configuration mode_ receives an Launch game (0x10) message, it enters _game mode_. In this mode, messages 0x11-0x17 are used to control the in-game state of the module.

_Game mode_ is only exited by a Reset (0x00) message.

## Errors

If a module detects an error state, it SHOULD attempt to send a suitable error message (message IDs 0x20-0x23).

If an unrecoverable error occurs in relation to a message from the MC that requires a response, a module MAY respond with only an error message.

If a module in _reset mode_ detects an error state, it SHOULD delay reporting it until it receives the Initialize (0x02) message.

## Message format

All messages MUST have a 29-bit extended identifier. The identifier value is constructed as follows (in big-endian bit order):

| Bits | Length | Field | Description |
|------|--------|-------|-------------|
| 0 | 1 | direction | 0 = MC to module, 1 = module to MC |
| 1-12 | 12 | module type | Identifies the physical type of module. Different modules that are physically identical SHOULD use the same type. See the module types in the appendix. |
| 13-22 | 10 | module serial | Identifies modules of the same type. MUST be unique between modules of the same type in the same bomb. |
| 23-28 | 6 | message ID | Identifies the type of message. MUST be one of the message IDs listed below. |

If `module type` is zero, `module serial` and `direction` MUST also be zero, and the message is a _broadcast message_.

A message MAY have 0-8 bytes of data, specified by the message ID.

## Message routing

Messages MUST only be passed between the modules and MC, not between individual modules. This means all state is kept on the MC. This way modules do not need to identify other modules or check the time or details from other modules, which allows for much less communication on the bus.

The MC MUST listen to all messages with `direction = 1`.

All modules MUST have a constant `module type` and `module serial` that do not change while the module is powered on.

All modules MUST listen to all messages with `direction = 0` where `module type = 0` OR `module type` and `module serial` match the module's values. Modules MUST only send messages with `direction = 1` and `module type` and `module serial` matching the module's values.

## Message IDs

The following message IDs are defined:

| Number | Name | Type | Data length | Valid in modes |
|--------|------|------|-------------|----------------|
| 0x00 | Reset | broadcast | 0 | all |
| 0x01 | Announce | event | 4 | reset |
| 0x02 | Initialize | request | 4 | reset |
| 0x03 | Ping | request, response | 0 | configuration, game |
| 0x10 | Launch game | broadcast | 0 | configuration |
| 0x11 | Start timer | broadcast | 0 | game |
| 0x12 | Explode | broadcast | 0 | game |
| 0x13 | Defuse | broadcast | 0 | game |
| 0x14 | Strike | request | 0 | game |
| 0x15 | Solve | request | 0 | game |
| 0x16 | Needy activate | request | 0 | game |
| 0x17 | Needy deactivate | request | 0 | game |
| 0x20 | Recoverable error | event | 1-8 | all |
| 0x21 | Recovered error | event | 1-8 | all |
| 0x22 | Minor unrecoverable error | event | 1-8 | all |
| 0x23 | Major unrecoverable error | event | 1-8 | all |
| 0x3* | Module-specific | defined by module | 0-8 | configuration, game |

Each message ID is described in detail below.

### ID 0x00: Reset

This message is sent by the MC as a broadcast message. The message contains no data.

Upon receiving it, a module MUST perform a soft reset:

- Stop all processing of previous messages and user actions
- Set the MODULE_READY signal low
- Reset all state variables to their initial state
- Restore user interface elements to their initial state

After performing the reset, the module MUST wait between 200ms and 300ms to allow all modules to reset. The wait duration SHOULD be random in order to avoid bus collisions; a hardcoded value that varies for each module suffices.

After this the module MUST send an Announce (0x01) message.

### ID 0x01: Announce

This message is sent by a module. It is only valid for modules in _reset mode_. The message contains the following data:

| Bits | Length | Field | Description |
|------|--------|-------|-------------|
| 0-7 | 8 | major HW version | The major version number of the module hardware. |
| 8-15 | 8 | minor HW version | The minor version number of the module hardware. |
| 16-23 | 8 | major SW version | The major version number of the module software. |
| 24-31 | 8 | minor SW version | The minor version number of the module software. |

This message MUST be sent exactly once after receiving a Reset (0x00) message; see above.

After sending the message, the module SHOULD perform minimal actions while waiting for an Initialize (0x02) message.

### ID 0x02: Initialize

This message is sent by the MC. It is only valid for modules in _reset mode_. The message contains the following data:

| Bits | Length | Field | Description |
|------|--------|-------|-------------|
| 0-7 | 8 | major HW version | The major version number of the hardware of the MC and constant bomb hardware. |
| 8-15 | 8 | minor HW version | The minor version number of the hardware of the MC and constant bomb hardware. |
| 16-23 | 8 | major SW version | The major version number of the software of the MC and constant bomb hardware. |
| 24-31 | 8 | minor SW version | The minor version number of the software of the MC and constant bomb hardware. |

Upon receiving the message, a module MUST set the MODULE_READY signal high and enter _configuration mode_.

If the module detects an unrecoverable error before or during this message, the module MAY keep the MODULE_READY signal low in addition to sending an error message.

The version numbers can be used by both ends of the communication to update a module's protocol while keeping it compatible with older versions, or by the MC to detect outdated or unsupported module revisions.

### ID 0x03: Ping

This message is sent by the MC. It is only valid for modules in _configuration mode_ and _game mode_. The message contains no data.

Upon receiving the message, a module MUST respond with a Pong (0x03) message with no data.

However, a module that is in _reset mode_ MUST NOT respond to a Ping (0x03) message.

### ID 0x10: Launch game

This message is sent by the MC as a broadcast message. It is only valid for modules in _configuration mode_. The message contains no data.

This message marks the start of the game. Upon receiving the message, modules MUST enter _game mode_ and set their user interface to the pre-game state. Input events MAY be sent after this message is received.

The MC MUST send any game configuration data to all modules prior to this message.

### ID 0x11: Start timer

This message is sent by the MC as a broadcast message. It is only valid for modules in _game mode_. The message contains no data.

This message marks the time when the timer starts and the lights turn on. Upon receiving this message, modules MUST set their user interface to the in-game state.

### ID 0x12/0x13: Explode/Defuse

These messages are sent by the MC as broadcast messages. They are only valid for modules in _game mode_. The messages contain no data.

These messages mark the bomb exploding or being defused. Upon receiving these messages, modules MUST set their user interface to the post-game state. This state will last until a Reset (0x00) message from the MC.

### ID 0x14/0x15: Strike/Solve

These message are sent by the MC. They are only valid for modules in _game mode_. The messages contain no data.

Upon receiving this message, a module MUST indicate visually that a strike occurred or the module was solved, if such an indicator is present on the module, and MAY stop sending input events if the module was solved.

If a modded module uses the strike or solve indicator in a way that does not actually count as a strike or solved module, it MUST use a module-specific message to indicate these states. These messages are reserved for real strikes and solved modules.

### ID 0x16/0x17: Needy activate/deactivate

These messages are sent by the MC. They are only valid for needy modules in _game mode_. The messages contain no data.

Upon receiving this message, a module MUST activate or deactivate their module-specific needy task.

### ID 0x20-0x23: Module errors

These messages are sent by a module. They are valid for modules in all modes. The messages contain the following data:

| Bits | Length | Field | Description |
|------|--------|-------|-------------|
| 0-7 | 8 | error type | The error type. See the error types in the appendix. |
| 8- | 0-56 | details | Error type specific diagnostic data. |

The Recoverable error (0x20) message indicates a recoverable error, i.e. an error the module reasonably believes it will recover from.

The Recovered error (0x21) message indicates an error that was recovered from.

The Minor unrecoverable error (0x22) message indicates an unrecoverable error that does not significantly affect gameplay.

The Major unrecoverable error (0x23) message indicates an unrecoverable error that significantly affects gameplay, to the point where a running game should be stopped.

If an error condition is detected and immediately recovered from, only a Recovered error (0x21) message should be sent. If the recovery from an error will take an unknown or extended amount of time, a Recoverable error (0x20) message should be sent immediately and a Recovered error (0x21) message when the error is recovered.

### ID 0x30-0x3f: Module-specific commands

These messages are defined for each module separately. They can be sent by the MC or by a module. They are only valid for modules in _configuration mode_ and _game mode_. They are used to query and update module state by the MC and to indicate input events by the modules.

## Appendix: Module type identifiers

The following table contains the defined module types:

| Type | Name | Description |
|------|------|-------------|
| 0 | _reserved_ | Reserved for broadcast. |
| 1 | Timer | The vanilla timer. |
| 2 | Wires | The vanilla Wires module. |
| 3 | Button | The vanilla Button module. |
| 4 | Keypad | The vanilla Keypad module. |
| 5 | Simon Says | The vanilla Simon Says module. |
| 6 | Who's on First | The vanilla Who's on First module. |
| 7 | Memory | The vanilla Memory module. |
| 8 | Morse Code | The vanilla Morse Code module. |
| 9 | Complicated Wires | The vanilla Complicated Wires module. |
| 10 | Wire Sequence | The vanilla Wire Sequence module. |
| 11 | Maze | The vanilla Maze module. |
| 12 | Password | The vanilla Password module. |
| 13 | Needy Venting Gas | The vanilla Needy Venting Gas module. |
| 14 | Needy Capacitor Discharge | The vanilla Needy Capacitor Discharge module. |
| 15 | Needy Knob | The vanilla Needy Knob module. |
| 16-63 | _reserved_ | Reserved for future vanilla modules. |
| 64-4095 | _unused_ | To be allocated for modded modules. |

## Appendix: Error codes

| Code | Name | Description |
|------|------|-------------|
| 0 | invalid message | The module received a message it could not understand or that was invalid for the module's current state. |
| 1 | hardware error | The module encountered an unknown hardware error. |
| 2 | software error | The module encountered an unknown software error. |
| 3-15 | _reserved_ | Reserved for future standard errors. |
| 16-255 | _module-specific_ | Defined for each module separately. |

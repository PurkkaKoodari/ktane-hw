# Bus protocol

This document specifies the protocol used for communication over the CAN bus
between modules and the main controller.

## Definitions

In this document, the following terms and abbreviations are used:

- **MC** = **main controller** = the device that stores the states of all modules
- **module** = the swappable modules that are visible to the user

## Message format

All messages MUST have a 29-bit extended identifier. The identifier value is constructed as follows (in big-endian bit order):

| Bits | Length | Field | Description |
|------|--------|-------|-------------|
| 0 | 1 | direction | 0 = MC to module<br>1 = module to MC<br>This ensures that messages from the MC have priority. <!-- TODO: is this what we want? --> |
| 1-12 | 12 | module type | Identifies the physical type of module. Different modules that are physically identical SHOULD use the same type. See the module types in the appendix. |
| 13-22 | 10 | module serial | Identifies modules of the same type. MUST be unique between modules of the same type in the same bomb. |
| 23-28 | 6 | message type | Identifies the type of message. MUST be one of the message types listed below. |

If `module type` is zero, `module serial` MUST also be zero, and the message is a broadcast message to all modules on the bomb.

A message may have 0-8 bytes of data, depending on the message type.

## Message routing

Messages MUST only be passed between the modules and MC, not between individual modules. This means all state is kept on the MC. This way modules do not need to identify other modules or check the time or details from other modules, which allows for much less communication on the bus.

The MC MUST listen to all messages with `direction = 1`.

All modules MUST have a constant `module type` and `module serial` that do not change while the module is powered on.

All modules MUST listen to all messages with `direction = 0` where `module type = 0` OR `module type` and `module serial` match the module's values. Modules MUST only send messages with `direction = 1` and `module type` and `module serial` matching the module's values.

## Requests and responses

Both the MC and modules can initiate messages.

Some messages sent by the MC require responses from the modules. With the exception of Reset (0x00), the responses SHOULD use the same message ID as the request.

Messages sent by the modules MUST NOT require responses from the MC. After sending a message, a module MUST be ready to receive any unrelated message; state changes caused by input events are handled asynchronously.

## Errors

If a module detects an error state, it SHOULD attempt to send a suitable error message (message types 0x20-0x23).

If an unrecoverable error occurs in relation to a message from the MC that requires a response, a module MAY respond with only an error message.

## Message types

The following message types are defined:

| Number | Name | Direction | Data length |
|--------|------|-----------|-------------|
| 0x00 | Reset | MC&rarr;module | 0 |
| 0x01 | Initialize | MC&rarr;module | 4 |
| 0x01 | Initialize | module&rarr;MC | 4 |
| 0x02 | Ping | MC&rarr;module | 0 |
| 0x02 | Pong | module&rarr;MC | 0 |
| 0x10 | Launch game | MC&rarr;module | 0 |
| 0x11 | Start timer | MC&rarr;module | 0 |
| 0x12 | Strike | MC&rarr;module | 0 |
| 0x13 | Solve | MC&rarr;module | 0 |
| 0x14 | Needy activate | MC&rarr;module | 0 |
| 0x15 | Needy deactivate | MC&rarr;module | 0 |
| 0x20 | Recoverable error | module&rarr;MC | 1-8 |
| 0x21 | Recovered error | module&rarr;MC | 1-8 |
| 0x22 | Minor unrecoverable error | module&rarr;MC | 1-8 |
| 0x23 | Major unrecoverable error | module&rarr;MC | 1-8 |
| 0x3* | Module-specific | MC&rarr;module | 0-8 |
| 0x3* | Module-specific | module&rarr;MC | 0-8 |

Each message type is described in detail below.

### ID 0x00: Reset

This message is sent by the MC as a broadcast message. The message contains no data.

Upon receiving it, a module MUST perform a soft reset:

- Stop all processing of previous messages and user actions
- Set the MODULE_READY signal low
- Reset all state variables to their initial state
- Restore user interface elements to their initial state

After performing the reset, the module SHOULD wait for a random amount of time (between 0ms and 100ms) in order to avoid bus collisions. After waiting, the module MUST respond with a Initialize (0x01) message with the following data:

| Bits | Length | Field | Description |
|------|--------|-------|-------------|
| 0-7 | 8 | major hardware version | The major version number of the module hardware. |
| 8-15 | 8 | minor hardware version | The minor version number of the module hardware. |
| 16-23 | 8 | major software version | The major version number of the module software. |
| 24-31 | 8 | minor software version | The minor version number of the module software. |

After sending the response, the module MUST stay in stand-by mode waiting for the Initialize (0x01) message, perfoming minimal other actions.

If a module in reset stand-by mode detects an error state, it SHOULD delay reporting it until it receives the Initialize (0x01) message.

### ID 0x01: Initialize

This message is sent by the MC. The message contains the following data:

| Bits | Length | Field | Description |
|------|--------|-------|-------------|
| 0-7 | 8 | major hardware version | The major version number of the hardware of the MC and constant bomb hardware. |
| 8-15 | 8 | minor hardware version | The minor version number of the hardware of the MC and constant bomb hardware. |
| 16-23 | 8 | major software version | The major version number of the software of the MC and constant bomb hardware. |
| 24-31 | 8 | minor software version | The minor version number of the software of the MC and constant bomb hardware. |

Upon receiving the message, a module MUST set the MODULE_READY signal high.

If the module detects an unrecoverable error before or during this message, the module MAY keep the MODULE_READY signal low in addition to sending an error message.

The version numbers can be used by both ends of the communication to update a module's protocol while keeping it compatible with older versions, or by the MC to detect outdated or unsupported module revisions.

### ID 0x02: Ping

This message is sent by the MC. The message contains no data.

Upon receiving the message, a module MUST respond with a Pong (0x02) message with no data.

### ID 0x10: Launch game

This message is sent by the MC as a broadcast message. The message contains no data.

This message marks the start of the game. Upon receiving the message, modules MUST set their user interface to the pre-start state.

The MC MUST give any data relevant

### ID 0x11: Start timer

This message is sent by the MC as a broadcast message. The message contains no data.

This message marks the time when the timer starts and the lights turn on. Upon receiving this message, modules MUST set their user interface to their in-game state.

### ID 0x12: Strike

This message is sent by the MC. The message contains no data.

Upon receiving this message, a module MUST indicate visually that a strike occurred if such an indicator is present on the module.

Note that with some modded modules this may not mean the strike counter was incremented.

### ID 0x13: Solve

This message is sent by the MC. The message contains no data. This message is only valid for solvable modules.

Upon receiving this message, a module MUST indicate visually that it was solved if such an indicator is present on the module.

### ID 0x14/0x15: Needy activate/deactivate

These messages are sent by the MC. The messages contains no data. These messages are only valid for needy modules.

Upon receiving this message, a module MUST activate or deactivate their module-specific needy task.

### ID 0x20-0x23: Module errors

This message is sent by a module. The message contains the following data:

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

These messages are defined for each module separately. They are used to query and update module state by the MC and to indicate input events by the modules.

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
| 0 | _TODO_ | _TODO_ |

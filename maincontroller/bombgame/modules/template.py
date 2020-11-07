from __future__ import annotations

import struct
from logging import getLogger

from bombgame.bus.messages import BusMessage, BusMessageId, ModuleId, BusMessageDirection
from bombgame.modules.base import Module
from bombgame.modules.registry import MODULE_ID_REGISTRY, MODULE_MESSAGE_ID_REGISTRY

# Change the logger name to ensure readable logs.
LOGGER = getLogger("YourModule")

# Declare any constants or data classes you need here.


@MODULE_ID_REGISTRY.register
# Change the class name. Naming convention is "XxxModule".
class YourModule(Module):
    # Place your module ID here.
    module_id = ...

    def __init__(self, bomb, bus_id, location, hw_version, sw_version):
        super().__init__(bomb, bus_id, location, hw_version, sw_version)
        # Initialize any state you need here and add listeners.

    def generate(self):
        # Generate a solution and store it in the class state.
        pass

    async def send_state(self):
        # Send the generated state to the module using self._bomb.send().
        # This is done at game start (before the timer starts).
        pass

    def ui_state(self):
        # Return a JSON-able dict that will be sent to the frontend.
        return {}

    async def handle_message(self, message: BusMessage):
        # Handle your custom messages and errors here.
        if isinstance(message, YourModuleCustomMessage):
            # Return true to indicate you successfully handled the message.
            return True
        # Pass unrecognized messages, or messages for which the module state is invalid, on to the parent class.
        return await super().handle_message(message)

    # You may also override most methods from Module, see their docstrings for details.

    # If you need to run periodic or long-running tasks, use self._bomb.create_task and self._bomb.cancel_task.
    # This will ensure the tasks are properly cleaned up when the bomb resets.

    # Whenever you make a change that will change ui_state, call self._bomb.trigger(ModuleStateChanged(self)).
    # Indicate error conditions with self._trigger_error(level, description).
    # Indicate strikes and defusal with self.strike() and self.defuse() - this will trigger the state change event.


# Declare any number of custom messages.

@MODULE_MESSAGE_ID_REGISTRY.register
# Change the class name. Naming convention is "XxxYyyMessage" (where Xxx is the module name).
class YourModuleCustomMessage(BusMessage):
    # Set the message ID. Use one of the MODULE_SPECIFIC_X IDs.
    message_id = (YourModule, BusMessageId.MODULE_SPECIFIC_0)

    # Add any custom args for the data of the module.
    def __init__(self, module: ModuleId, direction: BusMessageDirection = BusMessageDirection.OUT, *,
                 custom_arg: ...):
        super().__init__(self.__class__.message_id[1], module, direction)
        # Save your custom state here.
        self.custom_arg = custom_arg

    @classmethod
    def _parse_data(cls, module: ModuleId, direction: BusMessageDirection, data: bytes):
        # Check the length of the serialized data. It may be 0.
        if len(data) != ...:
            raise ValueError(f"{cls.__name__} must have ??? bytes of data")
        # Parse the custom args from the data.
        custom_arg, = struct.unpack("<B", data)
        # Pass the custom args on to the constructor.
        return cls(module, direction, custom_arg=custom_arg)

    def _serialize_data(self):
        # Serialize the custom args in the format used by _parse_data.
        return struct.pack("<B", self.custom_arg)

    def _data_repr(self):
        # Return a string representation of the custom args, or "" if none exist.
        return str(self.custom_arg)

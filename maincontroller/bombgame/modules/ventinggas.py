import struct
from enum import IntEnum
from logging import getLogger
from random import random

from bombgame.bus.messages import BusMessage, ModuleId, BusMessageDirection, BusMessageId
from bombgame.modules.base import ModuleState
from bombgame.modules.needy import NeedyModule, NeedyState
from bombgame.modules.registry import MODULE_ID_REGISTRY, MODULE_MESSAGE_ID_REGISTRY

LOGGER = getLogger("VentingGas")


class VentingGasQuestion(IntEnum):
    VENT_GAS = 0
    DETONATE = 1


class VentingGasAnswer(IntEnum):
    YES = 0
    NO = 1
    OUT_OF_TIME = 0xff


CORRECT_ANSWERS = {
    VentingGasQuestion.VENT_GAS: VentingGasAnswer.YES,
    VentingGasQuestion.DETONATE: VentingGasAnswer.NO,
}


@MODULE_ID_REGISTRY.register
class VentingGasModule(NeedyModule):
    module_id = 13

    def __init__(self, bomb, bus_id, location, hw_version, sw_version):
        super().__init__(bomb, bus_id, location, hw_version, sw_version)
        self._question = None

    def generate(self):
        pass

    async def send_state(self):
        pass

    async def activate(self):
        self._question = VentingGasQuestion.DETONATE if random() < 0.1 else VentingGasQuestion.VENT_GAS
        await self._bomb.send(VentingGasSetQuestionMessage(self.bus_id, question=self._question))
        await super().activate()

    async def handle_message(self, message: BusMessage):
        if isinstance(message, VentingGasAnswerMessage) and self.state == ModuleState.GAME and self.needy_state == NeedyState.ACTIVE:
            if message.answer == CORRECT_ANSWERS[self._question]:
                await self.deactivate()
            else:
                await self.needy_strike()
            return True
        return await super().handle_message(message)

    def ui_state(self):
        return {
            "needy_state": self.needy_state.name,
            "question": self._question.name if self._question is not None else "",
        }


@MODULE_MESSAGE_ID_REGISTRY.register
class VentingGasSetQuestionMessage(BusMessage):
    message_id = (VentingGasModule, BusMessageId.MODULE_SPECIFIC_0)

    def __init__(self, module: ModuleId, direction: BusMessageDirection = BusMessageDirection.OUT, *,
                 question: VentingGasQuestion):
        super().__init__(self.__class__.message_id[1], module, direction)
        self.question = question

    @classmethod
    def _parse_data(cls, module: ModuleId, direction: BusMessageDirection, data: bytes):
        if len(data) != 1:
            raise ValueError(f"{cls.__name__} must have 1 byte of data")
        question, = struct.unpack("<B", data)
        return cls(module, direction, question=VentingGasQuestion(question))

    def _serialize_data(self) -> bytes:
        return struct.pack("<B", self.question)

    def _data_repr(self) -> str:
        return self.question.name


@MODULE_MESSAGE_ID_REGISTRY.register
class VentingGasAnswerMessage(BusMessage):
    message_id = (VentingGasModule, BusMessageId.MODULE_SPECIFIC_1)

    def __init__(self, module: ModuleId, direction: BusMessageDirection = BusMessageDirection.OUT, *,
                 answer: VentingGasAnswer):
        super().__init__(self.__class__.message_id[1], module, direction)
        self.answer = answer

    @classmethod
    def _parse_data(cls, module: ModuleId, direction: BusMessageDirection, data: bytes):
        if len(data) != 1:
            raise ValueError(f"{cls.__name__} must have 1 byte of data")
        answer, = struct.unpack("<B", data)
        return cls(module, direction, answer=VentingGasAnswer(answer))

    def _serialize_data(self) -> bytes:
        return struct.pack("<B", self.answer)

    def _data_repr(self) -> str:
        return self.answer.name

from __future__ import annotations

from abc import ABC, abstractmethod
from asyncio import wrap_future, get_running_loop, AbstractEventLoop, run_coroutine_threadsafe
from concurrent.futures import Future
from enum import Enum
from logging import getLogger
from os.path import dirname, realpath, join, exists
from threading import current_thread, Thread
from time import monotonic
from typing import NamedTuple, Dict, List, Optional, TYPE_CHECKING, Collection

import pygame

from bombgame.config import AUDIO_CHANNELS
from bombgame.roomserver.common import RoomServerChannel
from bombgame.websocket import InvalidMessage

if TYPE_CHECKING:
    from bombgame.roomserver.server import RoomServer
    from bombgame.roomserver.client import RoomServerClient

SOUND_REGISTRY: Dict[type, List[SoundSpec]] = {}

SOUND_FOLDER = join(dirname(dirname(dirname(realpath(__file__)))), "sounds")

AUDIO_LOAD_EVENT = pygame.USEREVENT
AUDIO_PLAY_EVENT = pygame.USEREVENT + 1
AUDIO_STOP_EVENT = pygame.USEREVENT + 2
AUDIO_STOP_ALL_EVENT = pygame.USEREVENT + 3
AUDIO_END_EVENT = pygame.USEREVENT + 4

# how many seconds to wait before forgetting room audio that hasn't been marked as playing
UNACKED_ROOM_AUDIO_LIFETIME = 10

LOGGER = getLogger("Audio")


class PlayingSound(ABC):
    @abstractmethod
    def stop(self):
        """Stops the playing audio."""


class LocalPlayingSound(PlayingSound):
    _pygame_thread: Thread
    channel: Optional[PlaybackChannel]
    filename: str
    priority: int
    remote_id: Optional[int]

    def __init__(self, filename: str, priority: int):
        self._pygame_thread = current_thread()
        self.filename = filename
        self.priority = priority
        self.remote_id = None
        self.channel = None

    def stop(self):
        pygame.fastevent.post(pygame.fastevent.Event(AUDIO_STOP_EVENT, {
            "sound": self,
        }))


class RemotePlayingSound(PlayingSound):
    _room_server: RoomServerClient
    _remote_id: int
    filename: str
    priority: int
    created: float
    playing: bool

    def __init__(self, filename: str, priority: int, room_server: RoomServerClient, remote_id: int):
        self.filename = filename
        self.priority = priority
        self._room_server = room_server
        self._remote_id = remote_id
        self.created = monotonic()
        self.playing = False

    def stop(self):
        self._room_server.send_async(RoomServerChannel.AUDIO, {
            "stop": self._remote_id,
        })


class PlaybackChannel:
    channel: pygame.mixer.Channel
    end: float
    current_sound: Optional[LocalPlayingSound]

    def __init__(self, channel: pygame.mixer.ChannelType):
        self.channel = channel
        self.end = monotonic()
        self.current_sound = None

    def play(self, sound: pygame.mixer.Sound, playing: LocalPlayingSound):
        self.channel.play(sound)
        self.end = monotonic() + sound.get_length()
        self.current_sound = playing
        playing.channel = self

    @property
    def priority(self):
        return self.current_sound.priority if self.current_sound is not None else -1


class AudioLocation(Enum):
    BOMB_ONLY = "bomb_only"
    PREFER_ROOM = "prefer_room"
    ROOM_ONLY = "room_only"


class SoundSpec(NamedTuple):
    filename: str
    location: AudioLocation


def register_sound(owner_class: type, filename: str, location: AudioLocation) -> SoundSpec:
    path = join(SOUND_FOLDER, filename)
    if not exists(path):
        raise FileNotFoundError(f"sound file missing: {filename}")
    module_sounds = SOUND_REGISTRY.setdefault(owner_class, [])
    sound = SoundSpec(filename, location)
    module_sounds.append(sound)
    return sound


class SoundSystem(ABC):
    _loaded_sounds: Dict[str, pygame.mixer.Sound]
    _playback_channels: List[PlaybackChannel]
    _pygame_thread: Optional[Thread]
    _pygame_init: Future[None]
    _loop: AbstractEventLoop

    def __init__(self):
        self._loaded_sounds = {}
        self._playback_channels = []
        self._pygame_thread = None
        self._pygame_init = Future()
        self._loop = get_running_loop()

    def load_sounds(self, classes: Collection[type]):
        LOGGER.info("Loading sounds for %d classes", len(classes))
        for module_class in classes:
            for sound in SOUND_REGISTRY.get(module_class, []):
                self._load_sound_in_location(sound)
        # TODO: add method of waiting for this to complete

    def _load_sound_in_location(self, sound: SoundSpec):
        self._load_sound_locally(sound.filename)

    def _load_sound_locally(self, filename: str):
        LOGGER.debug("Requesting load for sound %s", filename)
        pygame.fastevent.post(pygame.fastevent.Event(AUDIO_LOAD_EVENT, {
            "filename": filename,
        }))

    async def start(self):
        if self._pygame_thread is not None:
            raise RuntimeError("local playback already initialized")
        LOGGER.info("Initializing local audio playback")
        self._pygame_thread = Thread(target=self._pygame_event_thread, name="Pygame thread")
        self._pygame_thread.start()
        await wrap_future(self._pygame_init)

    def stop(self):
        LOGGER.info("Stopping local audio playback")
        if self._pygame_thread is not None:
            pygame.fastevent.post(pygame.fastevent.Event(pygame.QUIT, {}))
            self._pygame_thread.join()

    def play_sound_locally(self, filename: str, priority: int) -> LocalPlayingSound:
        LOGGER.debug("Requesting playback for priority %s sound %s", priority, filename)
        playing = LocalPlayingSound(filename, priority)
        pygame.fastevent.post(pygame.fastevent.Event(AUDIO_PLAY_EVENT, {
            "sound": playing,
        }))
        return playing

    def stop_all_sounds(self):
        pygame.fastevent.post(pygame.fastevent.Event(AUDIO_STOP_ALL_EVENT, {}))

    def _sound_stopped(self, sound: LocalPlayingSound):
        LOGGER.debug("Sound %s ended", sound.filename)

    def _pygame_event_thread(self):
        try:
            pygame.display.init()
            pygame.fastevent.init()
            pygame.mixer.init(44100, -16, 2, 512)
            pygame.mixer.set_num_channels(AUDIO_CHANNELS)
            self._playback_channels.clear()
            for num in range(AUDIO_CHANNELS):
                channel = pygame.mixer.Channel(num)
                self._playback_channels.append(PlaybackChannel(channel))
                channel.set_endevent(AUDIO_END_EVENT)
            self._pygame_init.set_result(None)
        except BaseException as ex:
            self._pygame_init.set_exception(ex)
            pygame.quit()
            return

        try:
            while True:
                event = pygame.fastevent.wait()

                if event.type == pygame.QUIT:
                    pygame.fastevent.get()
                    return

                elif event.type == AUDIO_LOAD_EVENT:
                    LOGGER.debug("Loading sound %s", event.filename)
                    path = join(SOUND_FOLDER, event.filename)
                    sound_obj = pygame.mixer.Sound(path)
                    # avoid sound distortion by capping volume
                    # doing this here ensures that no clipping occurs in pygame/SDL mixer and allows us to ignore system volume
                    sound_obj.set_volume(0.25)
                    self._loaded_sounds[event.filename] = sound_obj

                elif event.type == AUDIO_PLAY_EVENT:
                    sound: LocalPlayingSound = event.sound
                    # try to find a free channel
                    channel = next((channel for channel in self._playback_channels if not channel.channel.get_busy()), None)
                    if not channel:
                        # find a channel to override: find the lowest-priority channel, with the sound ending soonest
                        channel = min(self._playback_channels, key=lambda ch: (ch.priority, ch.end))
                        if channel.priority > sound.priority:
                            LOGGER.warning("Out of channels, not playing priority %d audio %s", sound.priority, sound.filename)
                            continue
                        to_stop = channel.current_sound
                        if to_stop is not None:
                            LOGGER.warning("Out of channels, stopping priority %d audio %s with %s seconds left",
                                           channel.priority, to_stop.filename, channel.end - monotonic())
                    # play the sound
                    LOGGER.debug("Playing priority %d audio %s", sound.priority, sound.filename)
                    try:
                        clip = self._loaded_sounds[sound.filename]
                    except KeyError:
                        LOGGER.error(f"sound file not loaded: {sound.filename}")
                        continue
                    channel.play(clip, sound)

                elif event.type == AUDIO_STOP_EVENT:
                    sound: LocalPlayingSound = event.sound
                    if sound.channel is not None and sound.channel.current_sound is sound:
                        sound.channel.channel.stop()

                elif event.type == AUDIO_STOP_ALL_EVENT:
                    for channel in self._playback_channels:
                        channel.channel.stop()

                elif event.type == AUDIO_END_EVENT:
                    channel = self._playback_channels[event.code]
                    if channel.current_sound is not None:
                        self._sound_stopped(channel.current_sound)

        except Exception:
            LOGGER.error("Error in pygame audio thread", exc_info=True)
        finally:
            pygame.quit()


class BombSoundSystem(SoundSystem):
    _remote_playing_sounds: Dict[int, RemotePlayingSound]
    _remote_client: Optional[RoomServerClient]
    _next_remote_id: int

    def __init__(self, room_server_client: Optional[RoomServerClient] = None):
        super().__init__()
        self._remote_client = room_server_client
        self._remote_playing_sounds = {}
        self._next_remote_id = 0
        if room_server_client is not None:
            room_server_client.add_handler(RoomServerChannel.AUDIO, self._handle_message_from_room_server)

    async def _handle_message_from_room_server(self, data: dict):
        if "playing" in data:
            remote_id = data["playing"]
            if not isinstance(remote_id, int):
                raise InvalidMessage("play id must be an int")
            sound = self._remote_playing_sounds.get(remote_id)
            if sound is not None:
                sound.playing = True
                LOGGER.debug("Sound %s started playing", sound.filename)
        elif "stopped" in data:
            remote_id = data["stopped"]
            if not isinstance(remote_id, int):
                raise InvalidMessage("play id must be an int")
            sound = self._remote_playing_sounds.pop(remote_id, None)
            if sound is not None:
                LOGGER.debug("Sound %s ended", sound.filename)
        else:
            raise InvalidMessage("unknown audio action from room server")

    def _load_sound_in_location(self, sound: SoundSpec):
        if sound.location in (AudioLocation.ROOM_ONLY, AudioLocation.PREFER_ROOM) and self._remote_client is not None:
            # sound can and should be played via room server
            LOGGER.debug("Requesting room server to load sound %s", sound.filename)
            self._remote_client.send_async(RoomServerChannel.AUDIO, {
                "load": sound.filename
            })
        elif sound.location == AudioLocation.ROOM_ONLY:
            # sound should be played via room server but can't
            LOGGER.debug("Skipping load of room-mode sound %s", sound.filename)
        else:
            # sound should be played locally
            self._load_sound_locally(sound.filename)

    def play_sound(self, sound: SoundSpec, priority: int = 0) -> Optional[PlayingSound]:
        if sound.location in (AudioLocation.ROOM_ONLY, AudioLocation.PREFER_ROOM) and self._remote_client is not None:
            self._next_remote_id += 1
            self._remote_client.send_async(RoomServerChannel.AUDIO, {
                "play": sound.filename,
                "id": self._next_remote_id,
                "priority": priority,
            })
            playing = RemotePlayingSound(sound.filename, priority, self._remote_client, self._next_remote_id)
            self._remote_playing_sounds[self._next_remote_id] = playing
            return playing

        if sound.location == AudioLocation.ROOM_ONLY:
            LOGGER.debug("Room audio unavailable, skipping room-only sound %s", sound.filename)
            return None

        return self.play_sound_locally(sound.filename, priority)

    # TODO: call this periodically
    def _clean_up_remote_sounds(self):
        for remote_id, sound in list(self._remote_playing_sounds.items()):
            if not sound.playing and sound.created < monotonic() - UNACKED_ROOM_AUDIO_LIFETIME:
                LOGGER.debug("Sound %s was never marked as played", sound.filename)
                self._remote_playing_sounds.pop(remote_id, None)

    def stop_all_sounds(self):
        super().stop_all_sounds()
        self._clean_up_remote_sounds()
        for sound in self._remote_playing_sounds.values():
            sound.stop()


class RoomServerSoundSystem(SoundSystem):
    _room_server: Optional[RoomServer]
    _playing_sounds: Dict[int, LocalPlayingSound]

    def __init__(self, room_server: RoomServer):
        super().__init__()
        self._room_server = room_server
        self._playing_sounds = {}
        room_server.add_handler(RoomServerChannel.AUDIO, self._handle_message_from_client)

    async def _handle_message_from_client(self, data: dict):
        if "load" in data:
            filename = data["load"]
            if not isinstance(filename, str):
                raise InvalidMessage("filename must be a string")
            self._load_sound_locally(filename)
        elif "play" in data:
            filename = data["play"]
            remote_id = data.get("id")
            priority = data.get("priority")
            if not isinstance(remote_id, int):
                raise InvalidMessage("play id must be an int")
            if not isinstance(priority, int):
                raise InvalidMessage("priority must be an int")
            await self.play_sound_for_client(filename, priority, remote_id)
        elif "stop" in data:
            remote_id = data["stop"]
            if not isinstance(remote_id, int):
                raise InvalidMessage("play id must be an int")
            # stop the sound if the play id exists
            playing = self._playing_sounds.get(remote_id)
            if playing is not None:
                playing.stop()
        else:
            raise InvalidMessage("unknown audio action")

    async def play_sound_for_client(self, filename: str, priority: int, remote_id: int):
        playing = self.play_sound_locally(filename, priority)
        playing.remote_id = remote_id
        self._playing_sounds[remote_id] = playing
        await self._room_server.send(RoomServerChannel.AUDIO, {
            "playing": remote_id
        })

    def _sound_stopped(self, sound: LocalPlayingSound):
        super()._sound_stopped(sound)
        if self._room_server is not None:
            run_coroutine_threadsafe(self._room_server.send(RoomServerChannel.AUDIO, {
                "stopped": sound.remote_id,
            }), self._loop)

# TODO: music system

from __future__ import annotations

from enum import Enum
from logging import getLogger
from os.path import dirname, realpath, join, exists
from threading import current_thread
from time import monotonic
from typing import NamedTuple, Dict, List, Optional

import pygame

from bombgame.config import ROOM_SERVER, ROOM_AUDIO_ENABLED, AUDIO_CHANNELS

SOUND_REGISTRY: Dict[type, List[SoundSpec]] = {}
LOADED_SOUNDS: Dict[str, pygame.mixer.Sound] = {}
PLAYBACK_CHANNELS: List[PlaybackChannel] = []

SOUND_FOLDER = join(dirname(dirname(dirname(realpath(__file__)))), "sounds")

ROOM_AUDIO_AVAILABLE = ROOM_SERVER is not None and ROOM_AUDIO_ENABLED

LOGGER = getLogger("Audio")

_pygame_thread = None


def _check_pygame_thread():
    if current_thread() != _pygame_thread:
        raise RuntimeError("attempting to call audio subsystem from wrong thread")


class PlayingSound:
    def __init__(self, channel: PlaybackChannel, play_id: int):
        self._channel = channel
        self._play_id = play_id

    def stop(self):
        _check_pygame_thread()
        if self._channel.play_id == self._play_id:
            self._channel.channel.stop()


class PlaybackChannel:
    def __init__(self, channel: pygame.mixer.ChannelType):
        self.channel = channel
        self.priority = -1
        self.end = 0
        self.play_id = 0
        self.filename = None

    def play(self, filename: str, priority: int) -> PlayingSound:
        try:
            sound = LOADED_SOUNDS[filename]
        except KeyError:
            raise ValueError(f"sound file not loaded: {filename}") from None
        self.channel.play(sound)
        self.filename = filename
        self.end = monotonic() + sound.get_length()
        self.priority = priority
        self.play_id += 1
        return PlayingSound(self, self.play_id)


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


def load_sounds(classes):
    _check_pygame_thread()
    LOGGER.info("Loading sounds for %d classes", len(classes))
    for module_class in classes:
        for sound in SOUND_REGISTRY.get(module_class, []):
            if sound in LOADED_SOUNDS:
                continue
            if sound.location == AudioLocation.ROOM_ONLY or sound.location == AudioLocation.PREFER_ROOM and ROOM_AUDIO_AVAILABLE:
                LOGGER.debug("Skipping load of room-mode sound %s", sound.filename)
                continue
            LOGGER.debug("Loading sound %s", sound.filename)
            path = join(SOUND_FOLDER, sound.filename)
            LOADED_SOUNDS[sound.filename] = pygame.mixer.Sound(path)
    LOGGER.info("%d sounds now loaded", len(LOADED_SOUNDS))


def initialize_local_playback():
    global _pygame_thread
    if PLAYBACK_CHANNELS:
        raise RuntimeError("local playback already initialized")
    _pygame_thread = current_thread()
    LOGGER.info("Initializing local audio playback")
    pygame.mixer.init(44100, -16, 2, 512)
    pygame.mixer.set_num_channels(AUDIO_CHANNELS)
    PLAYBACK_CHANNELS.clear()
    for ch in range(AUDIO_CHANNELS):
        PLAYBACK_CHANNELS.append(PlaybackChannel(pygame.mixer.Channel(ch)))


def play_sound(sound: SoundSpec, priority: int = 0) -> Optional[PlayingSound]:
    _check_pygame_thread()
    # check if we should play as room audio
    if sound.location in (AudioLocation.ROOM_ONLY, AudioLocation.PREFER_ROOM):
        if ROOM_AUDIO_AVAILABLE:
            # TODO play room audio here and return a stop handler
            return None
        if sound.location == AudioLocation.ROOM_ONLY:
            LOGGER.debug("Room audio unavailable, skipping room-only sound %s", sound.filename)
            return None
    # try to find a free channel
    channel = next((channel for channel in PLAYBACK_CHANNELS if not channel.channel.get_busy()), None)
    if not channel:
        # find a channel to override: find the lowest-priority channel, with the sound ending soonest
        channel = min(PLAYBACK_CHANNELS, key=lambda ch: (ch.priority, ch.end))
        if channel.priority > priority:
            LOGGER.warning("Out of channels, not playing priority %d audio %s", priority, sound.filename)
            return None
        LOGGER.warning("Out of channels, stopping priority %d audio %s with %s seconds left",
                       channel.priority, channel.filename, channel.end - monotonic())
    # play the sound
    LOGGER.debug("Playing priority %d audio %s", priority, sound.filename)
    return channel.play(sound.filename, priority)


def stop_all_sounds():
    for channel in PLAYBACK_CHANNELS:
        channel.channel.stop()


def get_channel_configuration():
    raise NotImplementedError

# TODO: music system

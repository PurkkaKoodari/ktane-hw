from __future__ import annotations

from enum import Enum
from logging import getLogger
from os.path import dirname, realpath, join, exists
from threading import current_thread
from time import monotonic
from typing import NamedTuple, Dict, List, Callable

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


class PlaybackChannel:
    def __init__(self, channel):
        self.channel = channel
        self.priority = -1
        self.end = 0
        self.play_id = 0
        self.filename = None

    def play(self, filename: str, priority: int):
        try:
            sound = LOADED_SOUNDS[filename]
        except KeyError:
            raise ValueError(f"sound file not loaded: {filename}") from None
        self.channel.play(sound)
        self.filename = filename
        self.end = monotonic() + sound.get_length()
        self.priority = priority
        self.play_id += 1
        play_id = self.play_id

        def stopper():
            _check_pygame_thread()
            if self.play_id == play_id:
                self.channel.stop()
        return stopper


class AudioLocation(Enum):
    BOMB_ONLY = "bomb_only"
    PREFER_ROOM = "prefer_room"
    ROOM_ONLY = "room_only"


class SoundSpec(NamedTuple):
    filename: str
    location: AudioLocation


def register_sound(module_class: type, filename: str, location: AudioLocation) -> SoundSpec:
    path = join(SOUND_FOLDER, filename)
    if not exists(path):
        raise FileNotFoundError(f"sound file missing: {filename}")
    module_sounds = SOUND_REGISTRY.setdefault(module_class, [])
    sound = SoundSpec(filename, location)
    module_sounds.append(sound)
    return sound


def load_sounds(module_classes):
    LOGGER.info("Loading sounds for %d module classes", len(module_classes))
    for module_class in module_classes:
        for sound in SOUND_REGISTRY[module_class]:
            if sound in LOADED_SOUNDS:
                continue
            if sound.location == AudioLocation.ROOM_ONLY or sound.location == AudioLocation.PREFER_ROOM and ROOM_AUDIO_ENABLED:
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
    pygame.mixer.init()
    pygame.mixer.set_num_channels(AUDIO_CHANNELS)
    PLAYBACK_CHANNELS.clear()
    for ch in range(AUDIO_CHANNELS):
        PLAYBACK_CHANNELS.append(PlaybackChannel(pygame.mixer.Channel(ch)))


def play_sound(sound: SoundSpec, priority: int = 0) -> Callable[[], None]:
    _check_pygame_thread()
    # check if we should play as room audio
    if sound.location in (AudioLocation.ROOM_ONLY, AudioLocation.PREFER_ROOM):
        if ROOM_AUDIO_AVAILABLE:
            # TODO play room audio here and return a stop handler
            return lambda: None
        if sound.location == AudioLocation.ROOM_ONLY:
            LOGGER.debug("Room audio unavailable, skipping room-only sound %s", sound.filename)
            return lambda: None
    # try to find a free channel
    channel = next((channel for channel in PLAYBACK_CHANNELS if not channel.channel.get_busy()), None)
    if not channel:
        # find a channel to override: find the lowest-priority channel, with the sound ending soonest
        channel = min(PLAYBACK_CHANNELS, key=lambda ch: (ch.priority, ch.end))
        if channel.priority > priority:
            LOGGER.warning("Out of channels, not playing priority %d audio %s", priority, sound.filename)
            return lambda: None
        LOGGER.warning("Out of channels, stopping priority %d audio %s with %s seconds left",
                       channel.priority, channel.filename, channel.end - monotonic())
    # play the sound
    LOGGER.debug("Playing priority %d audio %s", priority, sound.filename)
    return channel.play(sound.filename, priority)


def get_channel_configuration():
    raise NotImplementedError

# TODO: music system

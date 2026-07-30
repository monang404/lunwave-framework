"""
Module: music.domain.commands

Purpose:
    Defines all command constants used by the CommandBus.
    Separated to allow importing without pulling in the entire CommandBus.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless.
"""

CMD_PLAY_TRACK = "cmd.play.track"  # data: TrackInfo
CMD_TOGGLE_PAUSE = "cmd.toggle.pause"
CMD_NEXT = "cmd.next"
CMD_PREV = "cmd.prev"
CMD_STOP = "cmd.stop"
CMD_SEEK = "cmd.seek"  # data: float
CMD_VOLUME_UP = "cmd.volume.up"
CMD_VOLUME_DOWN = "cmd.volume.down"
CMD_VOLUME_SET = "cmd.volume.set"  # data: dict with 'volume'
CMD_DOWNLOAD = "cmd.download"  # data: TrackInfo | None
CMD_CANCEL_DOWNLOAD = "cmd.cancel_download"
CMD_SET_MODE = "cmd.set.mode"  # data: PlaybackMode
CMD_SET_OUTPUT = "cmd.set.output"  # data: AudioOutput
CMD_SET_SPONSORBLOCK = "cmd.set.sponsorblock"  # data: bool
CMD_SET_LOUDNESS_NORMALIZATION = "cmd.set.loudness_normalization"  # data: bool
CMD_SET_CROSSFADE = "cmd.set.crossfade"  # data: float
CMD_QUEUE_SELECT = "cmd.queue.select"  # data: int (index)
CMD_QUEUE_ADD = "cmd.queue.add"  # data: TrackInfo
CMD_QUEUE_REPLACE = "cmd.queue.replace"  # data: list[TrackInfo]
CMD_QUEUE_REMOVE = "cmd.queue.remove"  # data: int (index)
CMD_QUEUE_REORDER = "cmd.queue.reorder"  # data: {"from_index": int, "to_index": int}
CMD_RADIO_RANDOMIZE = "cmd.radio.randomize"
CMD_LYRICS_OFFSET = "cmd.lyrics.offset"  # data: {"offset": float}
CMD_SET_SLEEP_TIMER = "cmd.set.sleep_timer"  # data: {"minutes": int}
CMD_SET_SPEED = "cmd.set.speed"  # data: {"speed": float}
CMD_SET_LOOP = "cmd.set.loop"  # data: {"mode": str}
CMD_QUIT = "cmd.quit"

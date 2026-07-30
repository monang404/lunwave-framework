"""
Module: adapters.mpv.connection

Purpose:
    Manages the raw socket connection to the MPV media player.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - core.exceptions

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import asyncio
import os

import structlog

from config import MPV_SOCKET
from core.exceptions import MpvConnectionError
from core.log_categories import LC_EXTERNAL

logger = structlog.get_logger(component="mpv.connection")


async def _open_pipe_connection(pipe_name: str):
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader(limit=2**16, loop=loop)
    protocol = asyncio.StreamReaderProtocol(reader, loop=loop)
    # create_pipe_connection exists on Windows' ProactorEventLoop for named-pipe
    # IPC, but isn't part of the generic AbstractEventLoop typeshed that
    # asyncio.get_running_loop() returns, so mypy can't see it.
    transport, _ = await loop.create_pipe_connection(  # type: ignore[attr-defined]
        lambda: protocol, pipe_name
    )
    writer = asyncio.StreamWriter(transport, protocol, reader, loop)
    return reader, writer


class MpvConnection:
    """Handle buka/tutup/reconnect socket ke MPV. Tidak tahu tentang playback."""

    def __init__(self, socket_path: str = None, tcp_port: str = None):  # type: ignore
        self.socket_path = socket_path or MPV_SOCKET
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self.is_connected = False
        self._reconnect_lock = asyncio.Lock()
        self._mpv_process = None
        self.shutting_down = False

    @property
    def reader(self):
        return self._reader

    @property
    def writer(self):
        return self._writer

    async def connect(self) -> bool:
        """Connect ke MPV socket. Return True jika sukses."""
        async with self._reconnect_lock:
            if self.is_connected:
                return True
            return await self._do_connect()

    async def _do_connect(self) -> bool:
        common_args = [
            "--no-video",
            "--idle",
            "--ytdl=no",  # M-1: App always passes resolved CDN URLs, never youtube:// — ytdl_hook is dead code and a dangerous uncontrolled fallback.
            "--audio-pitch-correction=yes",
            "--cache=yes",
            "--demuxer-readahead-secs=20",
            "--demuxer-max-bytes=30MiB",
            "--cache-pause=yes",
            "--network-timeout=15",
            "--gapless-audio=weak",  # M-3: Reduce gap/click between tracks (safe, no downside).
        ]

        if os.name != "nt":
            os.makedirs(os.path.dirname(self.socket_path), exist_ok=True)
            if os.path.exists(self.socket_path):
                try:
                    os.remove(self.socket_path)
                except OSError:
                    pass

        cmd = ["mpv"] + common_args + [f"--input-ipc-server={self.socket_path}"]

        try:
            self._mpv_process = await asyncio.create_subprocess_exec(  # type: ignore
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                stdin=asyncio.subprocess.DEVNULL,
            )
            if os.name != "nt":
                # Poll sampai socket tersedia, max 5 detik
                for _ in range(50):
                    await asyncio.sleep(0.1)
                    if os.path.exists(self.socket_path):
                        break
            else:
                for _ in range(50):
                    await asyncio.sleep(0.1)
                    try:
                        _tmp_r, _tmp_w = await asyncio.wait_for(
                            _open_pipe_connection(self.socket_path), timeout=1.0
                        )
                        _tmp_w.close()
                        try:
                            await _tmp_w.wait_closed()
                        except OSError:
                            pass
                        break  # MPV sudah siap, keluar dari polling
                    except (TimeoutError, ConnectionRefusedError, OSError, FileNotFoundError):
                        continue  # belum siap, tunggu lagi
        except OSError as e:
            logger.error(
                "mpv_spawn_failed",
                category=LC_EXTERNAL,
                error_type=type(e).__name__,
                error=str(e),
            )

        for attempt in range(10):
            try:
                if os.name == "nt":
                    self._reader, self._writer = await asyncio.wait_for(
                        _open_pipe_connection(self.socket_path), timeout=1.0
                    )
                else:
                    self._reader, self._writer = await asyncio.wait_for(
                        asyncio.open_unix_connection(self.socket_path),  # type: ignore[attr-defined]
                        timeout=1.0,
                    )

                self.is_connected = True
                self.shutting_down = False
                if os.name != "nt":
                    try:
                        import stat

                        os.chmod(self.socket_path, stat.S_IRUSR | stat.S_IWUSR)
                    except OSError:
                        pass
                logger.info(
                    "mpv_connected",
                    category=LC_EXTERNAL,
                    attempt=attempt + 1,
                )
                return True
            except MpvConnectionError:
                raise
            except (TimeoutError, ConnectionError, OSError, FileNotFoundError):
                await asyncio.sleep(0.5)
        raise MpvConnectionError(
            f"Cannot connect to mpv socket after 10 attempts (Unix/Pipe: {self.socket_path})"
        )

    async def disconnect(self):
        self.shutting_down = True
        self.is_connected = False

        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except OSError:
                pass

        if self._mpv_process:
            try:
                self._mpv_process.terminate()
                try:
                    await asyncio.wait_for(self._mpv_process.wait(), timeout=1.0)
                except TimeoutError:
                    self._mpv_process.kill()
            except OSError:
                pass

    async def reconnect(self) -> bool:
        async with self._reconnect_lock:
            if self.is_connected:
                return True

            self.is_connected = False
            if self._writer:
                try:
                    self._writer.close()
                    await self._writer.wait_closed()
                except OSError:
                    pass

            if self._mpv_process:
                try:
                    self._mpv_process.terminate()
                    try:
                        await asyncio.wait_for(self._mpv_process.wait(), timeout=1.0)
                    except TimeoutError:
                        self._mpv_process.kill()
                except OSError:
                    pass

            return await self._do_connect()

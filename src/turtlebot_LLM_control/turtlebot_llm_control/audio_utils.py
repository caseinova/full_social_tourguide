import ctypes
import os
import shutil
import subprocess
from contextlib import contextmanager
from typing import Iterator, Optional


_ALSA_LIB = None
_ALSA_HANDLER = None


def _silence_alsa_errors(enable: bool) -> bool:
    global _ALSA_LIB
    global _ALSA_HANDLER

    if _ALSA_LIB is None:
        try:
            _ALSA_LIB = ctypes.cdll.LoadLibrary("libasound.so")
            _ALSA_LIB.snd_lib_error_set_handler.argtypes = [ctypes.c_void_p]
        except OSError:
            _ALSA_LIB = False

    if not _ALSA_LIB:
        return False

    if _ALSA_HANDLER is None:
        handler_type = ctypes.CFUNCTYPE(
            None,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
        )

        def quiet_alsa_handler(_filename, _line, _function, _err, _fmt):
            return None

        _ALSA_HANDLER = handler_type(quiet_alsa_handler)

    try:
        if enable:
            _ALSA_LIB.snd_lib_error_set_handler(ctypes.cast(_ALSA_HANDLER, ctypes.c_void_p))
        else:
            _ALSA_LIB.snd_lib_error_set_handler(None)
        return True
    except Exception:
        return False


@contextmanager
def suppress_stderr() -> Iterator[None]:
    alsa_handler_set = _silence_alsa_errors(True)
    try:
        devnull_fd = os.open(os.devnull, os.O_WRONLY)
    except OSError:
        try:
            yield
        finally:
            if alsa_handler_set:
                _silence_alsa_errors(False)
        return

    try:
        saved_stderr_fd = os.dup(2)
    except OSError:
        os.close(devnull_fd)
        try:
            yield
        finally:
            if alsa_handler_set:
                _silence_alsa_errors(False)
        return

    try:
        os.dup2(devnull_fd, 2)
        yield
    finally:
        os.dup2(saved_stderr_fd, 2)
        os.close(saved_stderr_fd)
        os.close(devnull_fd)
        if alsa_handler_set:
            _silence_alsa_errors(False)


def choose_tts_command() -> Optional[list[str]]:
    if shutil.which("spd-say"):
        return ["spd-say", "-w"]
    if shutil.which("espeak"):
        return ["espeak"]
    if shutil.which("say"):
        return ["say"]
    return None


def speak_text(text: str) -> bool:
    if not text:
        return False
    command = choose_tts_command()
    if command is None:
        return False
    try:
        subprocess.run([*command, text], check=False)
        return True
    except OSError:
        return False

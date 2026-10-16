import winsound

from overlay.sound import play_goal_sound


class Recorder:
    def __init__(self):
        self.calls = []

    def play(self, *args):
        self.calls.append(("play", args))

    def beep(self, *args):
        self.calls.append(("beep", args))


def test_plays_configured_file_async(tmp_path):
    wav = tmp_path / "goal.wav"
    wav.write_bytes(b"RIFF")
    r = Recorder()
    play_goal_sound(str(wav), play=r.play, beep=r.beep)
    flags = winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT
    assert r.calls == [("play", (str(wav), flags))]


def test_missing_file_falls_back_to_system_sound(tmp_path):
    r = Recorder()
    play_goal_sound(str(tmp_path / "missing.wav"), play=r.play, beep=r.beep)
    assert r.calls == [("beep", (winsound.MB_ICONASTERISK,))]


def test_no_file_configured_falls_back_to_system_sound():
    r = Recorder()
    play_goal_sound(None, play=r.play, beep=r.beep)
    assert r.calls == [("beep", (winsound.MB_ICONASTERISK,))]

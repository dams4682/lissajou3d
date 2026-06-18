from __future__ import annotations

from xy_audio.engine import export_wav
from xy_audio_3d.render import Render3DConfig, build_3d_xy_audio


def main() -> int:
    config = Render3DConfig(shape="cube", duration=5.0, sample_rate=48_000, scan_rate_hz=40.0)
    audio = build_3d_xy_audio(config)
    export_wav(audio, "examples/cube_3d_auto.wav", config.sample_rate)
    print("Wrote examples/cube_3d_auto.wav")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

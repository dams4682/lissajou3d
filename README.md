# Lissajou3D

Lissajou3D converts animated 3D wireframe shapes into stereo audio that can be displayed on an XY oscilloscope or in Bespoke Synth's `lissajous` module.


<img width="1595" height="841" alt="Capture d’écran 2026-06-19 005354" src="https://github.com/user-attachments/assets/48531ccc-ccf7-4892-8d8c-be5dc9958b02" />
The exported WAV uses this mapping:

```text
left channel  = X coordinate
right channel = Y coordinate
```

The 3D scene is projected to 2D before export:

```text
animated 3D wireframe -> 2D XY projection -> stereo WAV
```

This means the WAV is still a normal stereo audio file, but when routed to an XY visualizer it draws a moving 3D-looking object.

<img width="1588" height="834" alt="bespoke" src="https://github.com/user-attachments/assets/9f303fbd-4725-4dbe-b3f8-7f86c8a03a49" />

## Features

- Standalone PyQt6 GUI.
- Interactive 3D wireframe viewer.
- Built-in shapes: cube, pyramid, sphere.
- Record mouse-driven movement.
- Export stereo XY WAV.
- Automatic rotating fallback when no motion is recorded.
- Bespoke Synth workflow: `sampleplayer -> lissajous`.
- Scan frequency in Hz or musical note names such as `C2`, `F2`, `A2`.
- Stable camera scale to avoid unnatural per-frame auto-zoom.

## Installation

Guide en français: [docs/GUIDE_FR.md](docs/GUIDE_FR.md).

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run from source:

```powershell
.\.venv\Scripts\python.exe app_3d.py
```

## Build The Executable

```powershell
.\build.ps1
```

The executable is created at:

```text
dist\Lissajou3D\Lissajou3D.exe
```

## GUI Workflow

1. Launch `Lissajou3D.exe` or run `python app_3d.py`.
2. Choose a shape: `cube`, `pyramid`, or `sphere`.
3. Choose projection:
   - `orthographic`: stable technical view.
   - `perspective`: stronger 3D depth.
4. Adjust `Camera scale` if the object is too large or too small.
5. Click `Record Movement`.
6. Manipulate the object:
   - left mouse drag: rotate
   - right mouse drag: move
   - mouse wheel: zoom
7. Click `Stop Recording`.
8. Click `Render Preview`.
9. Click `Play XY` to preview the audio signal.
10. Click `Export WAV`.

If no movement is recorded, Lissajou3D exports an automatic slow rotation. This is useful for quick testing.

## Audio Settings

- `Duration`: final WAV duration. If a movement was recorded, duration follows the recording.
- `Sample rate`: WAV sample rate, usually `48000`.
- `Scan rate Hz`: how many times the wireframe is redrawn per second.
- `Scan note`: optional musical note used as scan frequency, for example `C2` or `F2`.
- `Scale`: final XY amplitude.
- `Trace mode`:
  - `wire_walk`: follows connected wire edges to avoid diagonal retrace lines.
  - `fast_jumps`: draws each edge in order with direct travel between edges.
- `Smoothing`: light moving-average smoothing.
- `Normalize`: prevents clipping.
- `Invert X` / `Invert Y`: axis correction for different display chains. `Invert Y` is enabled by default for Bespoke-style display.

`Scan note` overrides `Scan rate Hz` when filled.

The GUI accepts experimental high scan rates such as `8000`, `12000`, or `16000` Hz. Use a high sample rate such as `96000` or `192000` for those tests; very high scan rates can take longer to render and may look rough if there are too few samples per scan cycle.

## Bespoke Synth

In Bespoke Synth:

```text
sampleplayer -> lissajous
```

Load the exported WAV in `sampleplayer`. The `lissajous` module will use left/right audio as XY coordinates.

Suggested starting settings:

```text
sample rate: 48000
scan rate: 40 Hz
scale: 0.9
camera scale: 2.4 to 3.2
projection: orthographic
```

## Generate The Example WAV

```powershell
.\.venv\Scripts\python.exe generate_example.py
```

This writes:

```text
examples\cube_3d_auto.wav
```

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Current Limitations

- V1 supports simple wireframe shapes only.
- STL import is not included yet.
- Hidden-line removal is not implemented.
- The output is a 2D projection of 3D motion, because normal stereo WAV only has X and Y channels.

## License

MIT. See [LICENSE](LICENSE).

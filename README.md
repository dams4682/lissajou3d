# Lissajou3D

Lissajou3D converts animated 3D wireframe shapes into stereo audio that can be displayed on an XY oscilloscope or in Bespoke Synth's `lissajous` module.

To use in Bespoke Synth you need to patch the .exe or just modify your .bsk to lissajous autocorrelation" : false

I aslo creat a patch for BespokeSynth 1.3.0 https://github.com/dams4682/bespoke-lissajous-autocorrelation-default-off  , to separate xy channel 



https://github.com/user-attachments/assets/e799bb34-5140-45ae-90e8-51e8f552fd18



Current release: `v1.2.0`

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
- STL wireframe import, ASCII or binary.
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

Lissajou3D starts in simple mode. Common import, movement, render, and export controls are visible. Enable `Advanced mode` at the top of the panel to show technical controls such as feature angle, max STL edges, projection, camera scale, duration, sample rate, scan note, scale, and smoothing.

1. Launch `Lissajou3D.exe` or run `python app_3d.py`.
2. Choose a shape: `cube`, `pyramid`, or `sphere`.
3. Click `Use Shape` to return to the selected built-in shape after using an STL.
4. Or click `Import STL` to load a custom 3D model as a wireframe.
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

Long STL renders run in the background. The action buttons are disabled during calculation, then playback/export continues when the audio is ready.

## STL Import

`Import STL` accepts ASCII STL and binary STL files. The triangles are converted to unique wireframe edges, then centered and normalized so the object fits the viewer and audio range.

For oscilloscope/Lissajous use, simple low-poly STL files work best. Very dense meshes create many edges, which can render slowly and may look noisy because the beam has to draw too much geometry every scan.

STL reduction settings affect both the viewer and the exported WAV:

- `STL edge mode`:
  - `silhouette_feature`: keeps the view-dependent outline plus hard-angle edges. Best first choice for dense STL files.
  - `silhouette_edges`: keeps only the view-dependent outline for the current object orientation.
  - `feature_edges`: keeps boundary edges and hard-angle edges, while removing flat triangulation lines.
  - `all_edges`: keeps every triangle edge from the STL.
- `Feature angle`: minimum angle between neighboring triangle faces before their shared edge is kept.
- `Max STL edges`: maximum number of edges kept after filtering. `0` means no limit.
- `Apply STL Settings`: reloads the current STL with the selected reduction settings.

For dense rounded objects such as chess pieces, start with:

```text
STL edge mode: silhouette_feature
Feature angle: 20 to 35
Max STL edges: 3000 to 8000
```

For very dense organic/rounded meshes, try `silhouette_feature` first. It changes the line set as the model rotates, which is closer to line-art rendering and avoids drawing the whole STL triangulation.

## GPU Preview

The source version uses the OpenGL/GPU preview by default. The packaged Windows executable currently starts with the stable CPU preview by default, because OpenGL behavior can vary across packaged Windows environments.

To test the GPU preview from PowerShell:

```powershell
$env:LISS3D_GPU_PREVIEW="1"
.\dist\Lissajou3D\Lissajou3D.exe
```

A small test model is included:

```text
examples\tetrahedron_ascii.stl
```

## Audio Settings

- `Duration`: final WAV duration. If a movement was recorded, duration follows the recording.
- `Sample rate`: WAV sample rate, usually `48000`.
- `Scan rate Hz`: how many times the wireframe is redrawn per second.
- `Geometry FPS`: how often the 3D pose and STL silhouette are recalculated. Lower values make dense STL exports much faster while keeping the same scan rate.
- `Scan note`: optional musical note used as scan frequency, for example `C2` or `F2`.
- `Scale`: final XY amplitude.
- `Trace mode`:
  - `wire_walk`: follows connected wire edges to avoid diagonal retrace lines.
  - `silhouette_loops`: assembles connected STL silhouette fragments into loops before ordering them. Best test mode for view-dependent silhouettes.
  - `nearest_fragments`: orders disconnected projected fragments by nearest endpoint. Useful for STL silhouettes.
  - `fast_jumps`: draws each edge in order with direct travel between edges.
- `Smoothing`: light moving-average smoothing.
- `Normalize`: prevents clipping.
- `Invert X` / `Invert Y`: axis correction for different display chains. `Invert Y` is enabled by default for Bespoke-style display.

`Scan note` overrides `Scan rate Hz` when filled.

The GUI accepts experimental high scan rates such as `8000`, `12000`, or `16000` Hz. Use a high sample rate such as `96000` or `192000` for those tests; very high scan rates can take longer to render and may look rough if there are too few samples per scan cycle.

For dense STL models, keep `Scan rate Hz` around `40` to `60` for the visual refresh, then reduce `Geometry FPS` to `4` to `8` if export feels frozen. This redraws the same projected line-art several times before recalculating the next 3D pose, which is usually enough for oscilloscope persistence and much faster than recalculating the STL silhouette every scan.

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

- STL import uses the triangle edges as a wireframe; it does not simplify dense meshes automatically.
- Hidden-line removal is not implemented.
- The output is a 2D projection of 3D motion, because normal stereo WAV only has X and Y channels.

## License

MIT. See [LICENSE](LICENSE).

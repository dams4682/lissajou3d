# Bespoke Synth Workflow

1. Open Bespoke Synth.
2. Add `sampleplayer`.
3. Add `lissajous`.
4. Connect:

```text
sampleplayer -> lissajous
```

5. Load a WAV exported by Lissajou3D.
6. Start playback.

The WAV is normal stereo audio, but the channels represent position:

```text
left channel  = X position
right channel = Y position
```

## Recommended First Test

Use the included example:

```text
examples\cube_3d_auto.wav
```

Or regenerate it:

```powershell
.\.venv\Scripts\python.exe generate_example.py
```

## If The Object Looks Flipped

Use `Invert X` or `Invert Y` in the GUI and export again.

For the current Bespoke setup, `Invert Y` is enabled by default.

## If The Object Is Too Large

Increase `Camera scale`, for example:

```text
2.4 -> 3.0
```

## If The Object Flickers

Increase `Scan rate Hz`, for example:

```text
40 -> 60
```

Or choose a higher scan note such as `C2`, `F2`, or `A2`.

## If STL Export Feels Frozen

Keep the visual redraw frequency reasonable and lower only the 3D recalculation rate:

```text
Scan rate Hz: 40 to 60
Geometry FPS: 4 to 8
```

`Scan rate Hz` controls how often the oscilloscope beam redraws the shape. `Geometry FPS` controls how often Lissajou3D recalculates the 3D pose and STL silhouette during export.

## If You See Diagonal Lines Inside The Shape

Use:

```text
Trace mode: wire_walk
```

This makes the beam travel along existing wire edges instead of jumping directly from one disconnected edge to another.

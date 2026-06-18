# Architecture

Lissajou3D is intentionally small and split into three layers.

## 3D Geometry

`xy_audio_3d.geometry`

- creates wireframe primitives
- applies rotation, translation and zoom
- projects 3D vertices to 2D XY coordinates

The projection uses a stable camera scale. It does not auto-fit every frame, because auto-fitting makes a rotating cube appear to grow and shrink unnaturally.

## Motion

`xy_audio_3d.motion`

- stores timestamped transforms
- interpolates transforms during export
- lets the GUI record mouse movement as animation data

If there is no recorded motion, the renderer creates an automatic rotation.

## Audio Render

`xy_audio_3d.render`

- samples the motion over the requested duration
- projects the wireframe to XY for each scan cycle
- uses `wire_walk` by default so the beam follows connected edges instead of drawing diagonal retrace lines
- resamples the line path into audio samples
- normalizes and exports stereo XY data

The final WAV mapping is:

```text
left  = X
right = Y
```

`xy_audio.engine` contains only the small shared helpers needed by Lissajou3D: WAV export and musical note to frequency conversion.

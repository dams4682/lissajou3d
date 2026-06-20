# Changelog

## Unreleased

- Add beginner-friendly simple mode with an `Advanced mode` toggle for technical controls.
- Document current Windows-only support.

## v1.2.0

- Add `silhouette_loops` trace mode to assemble connected STL silhouette fragments before drawing.
- Add a GUI progress bar for background WAV rendering.
- Add `Geometry FPS` to cache expensive 3D/STL silhouette frames during WAV export.
- Optimize `nearest_fragments` trace ordering for dense STL silhouettes.
- Render audio in a background Qt thread so long STL exports do not freeze the GUI.
- Add view-dependent STL silhouette modes for dense meshes.
- Replace the STL/shape preview renderer with an OpenGL GPU line renderer.
- Add STL feature-edge filtering to remove flat triangulation lines.
- Add `Max STL edges` so dense STL models can be reduced for both preview and WAV export.
- Add GUI controls to reload the current STL with the selected reduction settings.

## v1.1.0

- Add STL wireframe import for ASCII STL and binary STL files.
- Convert STL triangle edges to unique wireframe edges.
- Center and normalize imported STL meshes automatically.
- Use imported STL meshes in the viewer, movement recorder, audio preview, and WAV export.
- Keep built-in cube, pyramid, and sphere workflows unchanged.

## v1.0.0

- Initial Lissajou3D release with built-in 3D wireframe shapes.
- Export animated XY wireframes as stereo WAV for oscilloscope and Bespoke Synth `lissajous`.

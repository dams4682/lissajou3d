# Contributing

Contributions are welcome.

## Development Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run tests:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Run the GUI:

```powershell
.\.venv\Scripts\python.exe app_3d.py
```

## Code Style

- Keep rendering logic testable outside the GUI.
- Keep generated files out of Git unless they are small curated examples.
- Avoid adding heavy dependencies for V1 features.
- Prefer wireframe geometry for oscilloscope-friendly output.

## Good First Improvements

- STL import and simplification.
- Hidden-line removal.
- More primitives.
- Timeline/keyframe editor.
- Export presets for Bespoke Synth.

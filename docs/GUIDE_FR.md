# Guide Français

Lissajou3D transforme une forme 3D filaire animée en fichier WAV stéréo.

Dans le WAV:

```text
canal gauche = coordonnée X
canal droit  = coordonnée Y
```

Dans Bespoke Synth, ce signal peut être affiché avec:

```text
sampleplayer -> lissajous
```

## Installation

Dans PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Lancer le programme:

```powershell
.\.venv\Scripts\python.exe app_3d.py
```

## Créer l'exécutable

```powershell
.\build.ps1
```

L'exécutable sera ici:

```text
dist\Lissajou3D\Lissajou3D.exe
```

## Utilisation

1. Choisir une forme: `cube`, `pyramid`, `sphere`.
2. Cliquer sur `Record Movement`.
3. Manipuler l'objet:
   - clic gauche + mouvement: rotation
   - clic droit + mouvement: déplacement
   - molette: zoom
4. Cliquer sur `Stop Recording`.
5. Cliquer sur `Render Preview`.
6. Cliquer sur `Export WAV`.
7. Charger le WAV dans Bespoke Synth.

Si aucun mouvement n'est enregistré, le logiciel génère automatiquement une rotation lente.

## Réglages importants

- `Scan rate Hz`: nombre de redessins par seconde.
- `Scan note`: utilise une note musicale comme fréquence de balayage, par exemple `C2` ou `F2`.
- `Camera scale`: cadrage de la caméra. Plus la valeur est grande, plus l'objet paraît petit.
- `Trace mode`:
  - `wire_walk`: suit les arêtes connectées pour éviter les diagonales parasites.
  - `fast_jumps`: dessine les arêtes dans l'ordre avec des déplacements directs entre elles.
- `Projection`: `orthographic` est plus stable; `perspective` donne plus de profondeur.
- `Invert Y`: activé par défaut pour un affichage cohérent dans Bespoke.

Les champs acceptent des valeurs expérimentales élevées, par exemple `8000`, `12000` ou `16000` Hz pour `Scan rate Hz`. Pour ces essais, utilisez plutôt `96000` ou `192000` en `Sample rate`; si le balayage est trop haut avec trop peu d'échantillons par cycle, la forme devient moins propre et le rendu peut être plus long à calculer.

## Exemple

Un exemple est inclus:

```text
examples\cube_3d_auto.wav
```

Il peut être recréé avec:

```powershell
.\.venv\Scripts\python.exe generate_example.py
```

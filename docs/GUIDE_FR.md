# Guide Français

Lissajou3D transforme une forme 3D filaire animée en fichier WAV stéréo.

Version actuelle: `v1.1.0`

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
2. Cliquer sur `Use Shape` pour revenir à la forme intégrée sélectionnée après avoir utilisé un STL.
3. Ou cliquer sur `Import STL` pour charger un modèle 3D personnel en fil de fer.
4. Cliquer sur `Record Movement`.
5. Manipuler l'objet:
   - clic gauche + mouvement: rotation
   - clic droit + mouvement: déplacement
   - molette: zoom
6. Cliquer sur `Stop Recording`.
7. Cliquer sur `Render Preview`.
8. Cliquer sur `Export WAV`.
9. Charger le WAV dans Bespoke Synth.

Si aucun mouvement n'est enregistré, le logiciel génère automatiquement une rotation lente.

## Import STL

Le bouton `Import STL` accepte les fichiers STL ASCII et STL binaires. Le logiciel transforme les triangles du STL en arêtes filaires uniques, puis recentre et normalise automatiquement le modèle pour qu'il rentre dans la preview et dans la plage audio XY.

Pour un affichage oscilloscope/Lissajous, les STL simples et peu détaillés donnent les meilleurs résultats. Un maillage très dense contient beaucoup d'arêtes: le rendu peut devenir lent et le dessin peut paraître brouillon, car le faisceau doit parcourir trop de traits à chaque balayage.

Les réglages STL réduisent le modèle pour la preview et pour le WAV exporté:

- `STL edge mode`:
  - `feature_edges`: garde les bords et les arêtes anguleuses, mais retire les lignes plates de triangulation.
  - `all_edges`: garde toutes les arêtes des triangles du STL.
- `Feature angle`: angle minimum entre deux faces voisines pour garder leur arête commune.
- `Max STL edges`: nombre maximum d'arêtes gardées après filtrage. `0` veut dire sans limite.
- `Apply STL Settings`: recharge le STL courant avec les réglages choisis.

Pour un objet rond très maillé, par exemple une pièce d'échecs, essayez:

```text
STL edge mode: feature_edges
Feature angle: 20 à 35
Max STL edges: 3000 à 8000
```

Un petit STL de test est inclus:

```text
examples\tetrahedron_ascii.stl
```

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

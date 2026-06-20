# Guide Français

Lissajou3D transforme une forme 3D filaire animée en fichier WAV stéréo.

Version actuelle: `v1.2.0`

## Plateforme supportée

Lissajou3D est actuellement prévu et testé pour Windows uniquement.

La release publique fournit un exécutable Windows, et la lecture audio locale utilise l'API audio Windows. Linux et macOS ne sont pas encore supportés.

Depuis le code source Python, la preview 3D peut utiliser OpenGL/GPU pour afficher les fils de fer plus rapidement. L'exécutable Windows démarre par défaut avec la preview CPU stable tant que le mode GPU packagé reste expérimental. L'export WAV reste calculé par le moteur audio CPU.

Pour tester la preview GPU dans l'exécutable:

```powershell
$env:LISS3D_GPU_PREVIEW="1"
.\dist\Lissajou3D\Lissajou3D.exe
```

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

Lissajou3D démarre en mode simple. Les contrôles courants pour choisir/importer une forme, enregistrer un mouvement, prévisualiser et exporter sont visibles. Cochez `Advanced mode` en haut du panneau pour afficher les réglages techniques: angle de feature, limite d'arêtes STL, projection, camera scale, durée, sample rate, scan note, scale et smoothing.

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

Les rendus STL longs se lancent en arrière-plan. Les boutons d'action sont désactivés pendant le calcul, puis la lecture ou l'export reprend automatiquement quand l'audio est prêt.

## Import STL

Le bouton `Import STL` accepte les fichiers STL ASCII et STL binaires. Le logiciel transforme les triangles du STL en arêtes filaires uniques, puis recentre et normalise automatiquement le modèle pour qu'il rentre dans la preview et dans la plage audio XY.

Pour un affichage oscilloscope/Lissajous, les STL simples et peu détaillés donnent les meilleurs résultats. Un maillage très dense contient beaucoup d'arêtes: le rendu peut devenir lent et le dessin peut paraître brouillon, car le faisceau doit parcourir trop de traits à chaque balayage.

Les réglages STL réduisent le modèle pour la preview et pour le WAV exporté:

- `STL edge mode`:
  - `silhouette_feature`: garde le contour dépendant de la vue plus les arêtes anguleuses. C'est le meilleur premier choix pour les STL très denses.
  - `silhouette_edges`: garde seulement le contour dépendant de la vue selon l'orientation actuelle de l'objet.
  - `feature_edges`: garde les bords et les arêtes anguleuses, mais retire les lignes plates de triangulation.
  - `all_edges`: garde toutes les arêtes des triangles du STL.
- `Feature angle`: angle minimum entre deux faces voisines pour garder leur arête commune.
- `Max STL edges`: nombre maximum d'arêtes gardées après filtrage. `0` veut dire sans limite.
- `Apply STL Settings`: recharge le STL courant avec les réglages choisis.

Pour un objet rond très maillé, par exemple une pièce d'échecs, essayez:

```text
STL edge mode: silhouette_feature
Feature angle: 20 à 35
Max STL edges: 3000 à 8000
```

Pour un STL organique ou très arrondi, essayez d'abord `silhouette_feature`. Les lignes changent quand le modèle tourne, ce qui ressemble plus à un rendu line-art et évite de dessiner toute la triangulation du STL.

Un petit STL de test est inclus:

```text
examples\tetrahedron_ascii.stl
```

## Réglages importants

- `Scan rate Hz`: nombre de redessins par seconde.
- `Geometry FPS`: nombre de vraies positions 3D recalculées par seconde. Une valeur basse accélère beaucoup l'export des STL denses sans changer la fréquence de balayage audio.
- `Scan note`: utilise une note musicale comme fréquence de balayage, par exemple `C2` ou `F2`.
- `Camera scale`: cadrage de la caméra. Plus la valeur est grande, plus l'objet paraît petit.
- `Trace mode`:
  - `wire_walk`: suit les arêtes connectées pour éviter les diagonales parasites.
  - `silhouette_loops`: assemble les fragments de silhouette STL connectés en contours/boucles avant de les ordonner. Mode à essayer en priorité avec les silhouettes.
  - `nearest_fragments`: ordonne les fragments projetés par point le plus proche. Utile pour les silhouettes STL.
  - `fast_jumps`: dessine les arêtes dans l'ordre avec des déplacements directs entre elles.
- `Projection`: `orthographic` est plus stable; `perspective` donne plus de profondeur.
- `Invert Y`: activé par défaut pour un affichage cohérent dans Bespoke.

Les champs acceptent des valeurs expérimentales élevées, par exemple `8000`, `12000` ou `16000` Hz pour `Scan rate Hz`. Pour ces essais, utilisez plutôt `96000` ou `192000` en `Sample rate`; si le balayage est trop haut avec trop peu d'échantillons par cycle, la forme devient moins propre et le rendu peut être plus long à calculer.

Pour un STL dense, gardez par exemple `Scan rate Hz` entre `40` et `60`, puis mettez `Geometry FPS` entre `4` et `8` si l'export est trop lent. Le logiciel redessine alors plusieurs fois la meme projection avant de recalculer la position 3D suivante. Visuellement, le mouvement reste lisible, mais le calcul est beaucoup plus léger.

## Exemple

Un exemple est inclus:

```text
examples\cube_3d_auto.wav
```

Il peut être recréé avec:

```powershell
.\.venv\Scripts\python.exe generate_example.py
```

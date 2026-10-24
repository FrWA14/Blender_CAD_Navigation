# FrWA CAD Navigation pour Blender

Add-on Blender (4.2+) qui reproduit la navigation souris de FreeCAD / CATIA dans la vue 3D.

## Gestes

Pendant que la **molette est maintenue enfoncée** :

| Geste | Action |
|---|---|
| molette + déplacement | Pan |
| molette + clic droit maintenu + déplacement | Orbite |
| molette + clic droit court | Bascule en mode zoom (souris avant/arrière = zoom lisse) |
| clic molette court (sans bouger) | Recentre le pivot sous le curseur |
| relâcher la molette | Fin du geste |

Le clic droit seul garde le menu contextuel de Blender, le clic gauche + glisser reste la sélection, et la molette de défilement garde le zoom par défaut.

## Installation

1. Télécharger `frwa_blender_cad_navigation_v0.1.py`.
2. Dans Blender : *Edit > Preferences > Add-ons > Install from Disk…* et choisir le fichier.
3. Activer **FrWA CAD Navigation**.

Les sensibilités (pan, orbite, zoom) et l'inversion des axes se règlent dans les préférences de l'add-on.

## Licence

MIT, voir [LICENSE](LICENSE).

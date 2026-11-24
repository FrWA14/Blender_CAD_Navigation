# FrWA CAD Navigation pour Blender

Add-on Blender (4.2+, testé sur 5.2 et 5.3) qui reproduit la navigation souris de FreeCAD / CATIA dans la vue 3D. Il fonctionne avec la carte de raccourcis Blender par défaut et avec **Industry Compatible**.

## Gestes

### Hors outil (la molette est le bouton du milieu)

| Geste | Action |
|---|---|
| molette maintenue + déplacement | Pan : l'objet suit le curseur 1:1 |
| molette + clic droit maintenu + déplacement | Orbite |
| molette + clic droit court | Bascule zoom ↔ pan (souris avant/arrière = zoom lisse) |
| clic molette court (sans bouger) | Recentre le pivot sous le curseur |
| Shift + molette | Orbite (sans clic droit) |
| Ctrl + molette | Zoom |
| roulette | Zoom Blender |

### Pendant un outil en cours (déplacement, extrusion, mise à l'échelle, gizmo, couteau…)

| Geste | Action |
|---|---|
| molette | Pan |
| Shift + molette | Orbite |
| Ctrl + molette | Zoom |

Le clic droit reste « annuler » dans les outils Blender : il ne sert donc pas à orbiter pendant un outil.

Le clic droit seul garde le menu contextuel, et le clic gauche reste la sélection.

**Limite de Blender :** Bevel, Inset et Loop Cut ne permettent aucune navigation pendant leur réglage, même sans l'add-on. Valide l'outil, puis ajuste dans le panneau « Ajuster la dernière opération ».

## Installation

1. Télécharger `frwa_cad_navigation.py`.
2. Dans Blender : *Édition > Préférences > Add-ons > Installer depuis le disque…* et choisir le fichier.
3. Activer **FrWA CAD Navigation**.

### Options (préférences de l'add-on)

* **La molette navigue même quand un outil est actif** : désactive les raccourcis molette des outils de la barre d'outils. En Industry Compatible, la molette y lance l'outil (Move, Extrude, Knife…) au lieu de naviguer. Les raccourcis d'origine sont rétablis si l'option est décochée ou l'add-on désactivé.
* **Naviguer à la molette pendant une transformation / le couteau** : la contrainte d'axe à la molette est alors désactivée (utiliser X / Y / Z).
* Vitesse du pan, sensibilité d'orbite (multiplie celle de Blender) et de zoom, inversions d'axes.
* Bouton **Réappliquer les corrections de raccourcis**, à utiliser après un changement de carte de raccourcis.

L'add-on respecte les préférences de navigation de Blender : *Orbit Around Selection*, *Zoom to Mouse Position*, *Auto Depth*, *Auto Perspective*, Turntable / Trackball et sensibilité d'orbite. Il gère aussi la vue caméra (y compris *Camera to View*) et la quad view.

## Réglages recommandés (CAO / impression 3D)

`reglages/appliquer_reglages_recommandes.py` applique en une fois, Blender fermé :

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --python reglages\appliquer_reglages_recommandes.py
```

* *Zoom to Mouse Position* et *Auto Depth* activés : zoom vers le curseur, orbite autour du point visé. Si l'objet sort de l'écran, **A** (Industry) ou *View All* recadre.
* Add-on activé, avec ses deux options cochées.
* Fichier de démarrage : scène vide en **millimètres** (Unit Scale 0.001), clipping de 0,1 mm à 10 m.

Pour revenir en arrière : *Fichier > Défauts > Charger les réglages d'usine*.

## Tests

Les tests pilotent un vrai Blender avec des événements simulés : clics, touches, gestes de navigation.

| Fichier | Contenu |
|---|---|
| `tests/test_navigation_blender.py` | gestes, outils de la barre d'outils, blocages, options (`HARNESS_IC=1` pour Industry Compatible) |
| `tests/test_mesures_navigation.py` | mesures comparées à la navigation native : pan 1:1, préférences, vue caméra, quad view |
| `tests/test_tuto_fantome.py` | rejoue un tutoriel complet de modélisation, avec navigation entre chaque étape |

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --enable-event-simulate --python tests\test_tuto_fantome.py
```

Utilise une **copie** de ton dossier de configuration Blender (variable `BLENDER_USER_CONFIG`) pour ne pas modifier tes préférences. Résultats de la v0.3 : [docs/rapport_tests_v0.3.md](docs/rapport_tests_v0.3.md).

## Historique

* **0.3.0** : corrections trouvées en rejouant un tutoriel complet
  * pan exact 1:1 (avant : 2,5× trop rapide) ;
  * orbite depuis une vue Face/Dessus : retour en perspective ;
  * prise en compte des préférences Blender de navigation ;
  * geste juste après F / clic molette : plus annulé par l'animation ;
  * vue caméra et quad view gérées.
* **0.2.0** : compatibilité Industry Compatible (la molette des outils ne vole plus la navigation), navigation pendant les transformations et le couteau, plus de geste « collé » après Alt+Tab, re-clic droit court zoom → pan.
* **0.1.0** : première version.

## Licence

MIT, voir [LICENSE](LICENSE).

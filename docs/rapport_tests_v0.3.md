# Fantôme tirelire, étape 1 : tutoriel rejoué avec l'extension CAD

*Test automatique du 25/11/2026 · Blender 5.2 LTS · copie de tes préférences (carte Industry Compatible)*

## 1. Méthode

Blender a été piloté comme par un utilisateur, avec des événements simulés : touches, clics sur les faces, saisie des valeurs dans le panneau « Add Cylinder », menus. Entre chaque étape, une série de gestes de navigation (pan, orbite, zoom, Shift+molette, roulette, clic molette) vérifie que naviguer **ne modifie rien d'autre** : maillage, sélection, mode, outil actif et panneau « Ajuster la dernière opération ».

Ce que Blender ne sait pas simuler a été remplacé par l'opération équivalente :

| Étape du tuto | Remplacé par |
|---|---|
| 1.2 Unités (panneau Scene) | réglage par script + étape d'annulation, comme dans l'interface |
| 2.3 Renommer (double-clic Outliner) | renommage par script |
| 3.2 / 3.3 Glisser la poignée `+` ou le cercle | même opération que le gizmo, puis vraie souris, saisie de 25 / 0.85, navigation et validation |
| 4.2 Double-clic sur une arête | `loop_select` appelé à la position de la souris |

## 2. Résultats par configuration

| Configuration | Contrôles réussis | Fantôme obtenu |
|---|---|---|
| Industry Compatible + **CAD v0.3** (installée) | **67 / 67** | 104 × 104 × 147 mm, **identique** à `fantome_etape01.blend` (120 sommets, 97 faces) |
| Industry Compatible + CAD v0.2 | 67 / 67 | 104 × 104 × 147 mm |
| Industry Compatible sans extension (Alt + souris) | 62 / 67 | 104 × 104 × **122** mm : extrusion perdue |
| Industry Compatible + CAD v0.1 (ancienne) | 33 / 67 | **133 × 123 × 142 mm** : maillage déformé |

* **v0.1** : avec l'outil Extrude actif, la molette **extrudait** le maillage au lieu de naviguer et remplaçait le panneau de réglages. Ce sont les problèmes que tu avais signalés.
* **Sans extension** : orbiter avec Alt+clic gauche pendant une extrusion **valide** l'opération (le clic gauche confirme), donc l'extrusion de 25 mm est perdue.
* **v0.3** : toutes les étapes passent, avec navigation pendant les extrusions et mises à l'échelle (molette = pan, Shift+molette = orbite).

Autres suites de tests de la v0.3 : 153/153 (Industry Compatible), 84/84 (carte Blender par défaut), 23/23 (mesures ci-dessous).

## 3. Bugs de l'outil CAD trouvés et corrigés (v0.3.0)

Chaque point est mesuré, puis comparé à la navigation native de Blender.

| # | Bug v0.2 | Mesure avant | Après |
|---|---|---|---|
| 1 | Le pan ne suit pas le curseur | objet +246 px pour 100 px de souris | +100,0 px (1:1) |
| 2 | Orbite depuis une vue Face/Dessus (F1, F3) : reste en orthographique | reste ORTHO | repasse en perspective |
| 3 | Préférence « Orbit Around Selection » ignorée | la sélection dérive de 74 px | 0 px |
| 4 | Préférence « Zoom to Mouse Position » ignorée (zoom par clic droit court) | dérive de 195 px | 6 px |
| 5 | Geste juste après F ou après un clic molette en partie annulé par l'animation de cadrage | pan perdu | pan conservé |
| 6 | Vue caméra : orbite et pan sans effet | rien ne bouge | l'orbite quitte la vue caméra, le pan décale le cadrage ; avec « Camera to View », c'est la caméra qui bouge |
| 7 | Quad view : les vues verrouillées (Dessus/Face/Droite) tournaient | tourne | fixe (pan/zoom synchronisés si « Sync ») |
| + | Préférence « Auto Depth » et mode Trackball ignorés ; orbite plus lente que Blender | — | pris en compte, même sens et même vitesse que Blender |

Les versions précédentes sont dans l'historique git.

## 4. Configuration Blender recommandée

> **Appliquée le 25/11/2026** avec `reglages/appliquer_reglages_recommandes.py`. Avec ces réglages, le tuto passe toujours (67/67) et la suite Industry Compatible aussi (153/153).
>
> Avec **Auto Depth**, l'orbite tourne autour du point de surface **sous la souris**. Si l'objet sort de l'écran, appuie sur **A** (tout voir) ou fais un **clic molette** sur l'objet pour recentrer.

**À garder :**
* Carte **Industry Compatible** : le tutoriel est écrit pour elle.
* Extension **FrWA CAD Navigation v0.3**, avec ses deux options cochées : « La molette navigue même quand un outil est actif » et « Naviguer à la molette pendant une transformation ».
* *Navigation > Auto Perspective* : activé (déjà le cas).

**Recommandé pour un usage type CAO** (*Édition > Préférences > Navigation*) :

| Réglage | Valeur | Effet avec l'extension |
|---|---|---|
| Zoom to Mouse Position | **activé** | la roulette et le zoom par clic droit court zooment vers le curseur, comme FreeCAD / CATIA |
| Auto Depth | **activé** | l'orbite tourne autour du point sous la souris, et le pan « attrape » la surface visée |
| Orbit Around Selection | désactivé (au choix) | si activé, l'orbite tourne autour de la sélection, prioritaire sur Auto Depth ; pratique pour tourner autour d'une face |

**Pour l'impression 3D en mm :** le fichier de démarrage est maintenant une scène vide en millimètres (Unit Scale 0.001, Length = Millimeters, clipping de 0,1 mm à 10 m). Les étapes 1.1 et 1.2 du tuto sont donc déjà faites à l'ouverture. Pour revenir au cube d'origine : *Fichier > Défauts > Charger les réglages d'usine*.

## 5. Remarques sur le tutoriel

* **Q, comme R** : si l'outil Sélection est déjà actif, Q passe à « Select Circle », puis « Lasso ». Le tuto signale ce piège pour R et Ctrl+E, pas pour Q (étape 4.3 : « Q puis R » après le double-clic).
* **Étape 4.1** : la navigation de l'encadré du haut peut maintenant ajouter « Shift + molette = tourner, utilisable aussi pendant une extrusion ou une mise à l'échelle ».
* Un menu (Delete, clic droit) ouvert près du bas de l'écran est décalé par Blender : vérifier la ligne surlignée avant de cliquer.

## 6. Relancer les tests

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --enable-event-simulate --python tests\test_tuto_fantome.py
```

À lancer avec la variable `BLENDER_USER_CONFIG` pointant vers une **copie** de ton dossier `config`, pour ne pas toucher à tes préférences. Les captures de l'exécution v0.3 sont dans [`captures/`](captures/).

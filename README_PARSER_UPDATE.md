# 🔧 Mise à Jour du Parser de Programme IA

## 📋 Résumé des Modifications

Le système de parsing a été complètement refondu pour supporter **DEUX formats** de réponses IA :

### 1️⃣ Ancien Format (toujours supporté)
Avec blocs `[PARSE_START]` et `[PARSE_END]` :
```
SEANCE 1: Push

- Développé couché : ...
- Squat : ...

[PARSE_START]
EXERCICE: Développé couché | SERIES: 4 | REPS: 6-8 | NOTES: RIR 2-3
EXERCICE: Squat | SERIES: 3 | REPS: 8-10 | NOTES: RIR 2-3
[PARSE_END]
```

### 2️⃣ Nouveau Format (détection automatique) ✨
Sans blocs, avec séparateurs visuels :
```
──────────────────────────────────────── SEANCE 1: Push / Legs A

Développé couché (Barre) : 4 x 6-8 reps @ RIR 2-3, 2.5 min repos
Squat (Barre) : 3 x 8-10 reps @ RIR 2-3, 2 min repos

──────────────────────────────────────── SEANCE 2: Pull / Legs B

Tractions : 4 x 6-8 reps @ RIR 2-3, 2.5 min repos
```

---

## 🎯 Fonctionnalités du Nouveau Parser

### ✅ Détection Automatique du Format
Le parser détecte automatiquement quel format est utilisé :
- Cherche les blocs `[PARSE_START]`/`[PARSE_END]`
- Si absents, utilise la détection par pattern regex

### ✅ Pattern d'Exercice Robuste
Détecte les exercices au format :
```
Nom de l'exercice (Matériel) : X x Y reps @ RIR Z, T min repos
```

**Exemples supportés :**
- `Développé couché (Barre) : 4 x 6-8 reps @ RIR 2-3, 2.5 min repos` ✅
- `Tractions : 4 x 8-10 reps @ RIR 2-3, 2 min repos` ✅
- `Squat (Barre) : 3 x 8-10 reps @ RIR 2-3, 2 min repos` ✅

### ✅ Détection Flexible des Séances
Supporte plusieurs formats de titre :
- Avec séparateurs : `──────────────────────────────────────── SEANCE 1: Nom`
- Sans séparateurs : `SEANCE 1: Nom`

---

## 📁 Fichiers Modifiés

### 1. `app.py`
**Ajouts :**
- `parse_programme_ia_robuste()` : Fonction principale qui détecte le format
- `parse_avec_blocs()` : Parser pour l'ancien format
- `parse_sans_blocs()` : Parser pour le nouveau format

**Modifications :**
- Route `/programme/save-from-ai` : Utilise maintenant le nouveau parser robuste

### 2. `test_parser.py`
**Refonte complète :**
- Intégration des 3 nouvelles fonctions de parsing
- Support des deux formats
- Messages de debug améliorés

### 3. Fichiers de Test Créés
- `REPONSE_IA_NOUVELLE.txt` : Exemple de réponse au nouveau format
- `test_quick.py` : Tests rapides des regex et patterns

---

## 🧪 Comment Tester

### Test 1 : Ancien Format (avec blocs)
```bash
python test_parser.py EXEMPLE_REPONSE_IA.txt
```
**Résultat attendu :** ✅ Parsing réussi avec blocs `[PARSE_START]`

### Test 2 : Nouveau Format (sans blocs)
```bash
python test_parser.py REPONSE_IA_NOUVELLE.txt
```
**Résultat attendu :** ✅ Parsing réussi par détection automatique

### Test 3 : Vérification des Patterns
```bash
python test_quick.py
```
**Résultat attendu :** ✅ Les regex matchent correctement

---

## 📊 Pattern Regex du Nouveau Format

### Pattern d'Exercice
```regex
^-?\s*(.+?)\s*:\s*(\d+)\s*x\s*([0-9\-]+)\s*reps?\s*@\s*RIR\s*([0-9\-]+)\s*,?\s*(.+?)(?:min|minutes)?\s*repos
```

**Groupes de capture :**
1. Nom de l'exercice (avec matériel éventuel)
2. Nombre de séries
3. Fourchette de répétitions (ex: `6-8` ou `10`)
4. RIR (ex: `2-3`)
5. Temps de repos (ex: `2.5`)

### Pattern de Séance
```regex
SEANCE\s*(\d+)\s*[:：]\s*(.+)
```

**Groupes de capture :**
1. Numéro de la séance
2. Nom de la séance

---

## ⚙️ Configuration du Prompt IA

Le prompt dans `app.py` peut être simplifié car le parser est maintenant plus robuste.

### Format Recommandé pour l'IA
```
──────────────────────────────────────── SEANCE X: Nom de la séance

Exercice (Matériel) : X x Y reps @ RIR Z, T min repos
...
```

**Points clés :**
- 40 tirets `─` avant `SEANCE`
- Format strict : `Nom : X x Y reps @ RIR Z, T min repos`
- Espaces obligatoires autour du `x`
- Toujours écrire `reps`, `@ RIR`, `min repos`

---

## 🐛 Debugging

### Messages de Debug
Le parser affiche des messages détaillés :
- 📌 Détection du format utilisé
- 🆕 Chaque séance détectée
- ✅ Chaque exercice parsé
- ⚠️ Lignes ignorées
- 📊 Résumé final

### En Cas de Problème

**Aucune séance détectée :**
- Vérifier que les lignes commencent par `SEANCE X:`
- Vérifier les deux-points `:` après le numéro

**Aucun exercice détecté :**
- Vérifier le format : `Nom : X x Y reps @ RIR Z, T min repos`
- Vérifier les espaces autour du `x`
- Vérifier la présence de `reps`, `@ RIR`, `min repos`

---

## ✨ Avantages du Nouveau Système

1. **Rétrocompatibilité** : L'ancien format fonctionne toujours
2. **Simplicité pour l'IA** : Pas besoin de dupliquer les exercices
3. **Parsing automatique** : Détection intelligente du format
4. **Meilleur debugging** : Messages détaillés pour identifier les problèmes
5. **Flexibilité** : Supporte plusieurs variations de format

---

## 📝 Prochaines Étapes (Optionnel)

Si vous souhaitez simplifier davantage le prompt, vous pouvez :

1. **Retirer complètement les blocs** `[PARSE_START]`/`[PARSE_END]` du prompt
2. **Ajouter plus de variantes** au pattern regex si besoin
3. **Gérer d'autres formats** d'exercices (sans RIR, sans repos, etc.)

---

## 🎉 Conclusion

Le parsing est maintenant **robuste** et **flexible**. Vous pouvez utiliser la réponse actuelle de votre IA sans modification !

**Testez avec :**
```bash
python test_parser.py REPONSE_IA_NOUVELLE.txt
```

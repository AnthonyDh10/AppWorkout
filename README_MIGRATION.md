# 🔄 Migration vers séries individuelles

## 📋 Résumé des changements

Votre application a été modifiée pour permettre des **séries individuelles avec des répétitions et poids différents** pour chaque série.

### Avant :
```
Développé couché : 3 séries × 8 reps @ 80kg
(toutes les séries identiques)
```

### Après :
```
Développé couché : 3 séries
  - Série 1 : 8 reps × 80kg
  - Série 2 : 7 reps × 75kg
  - Série 3 : 6 reps × 70kg
(chaque série peut être différente)
```

---

## 🚀 Étapes de migration

### 1️⃣ Exécuter le script de migration

**⚠️ IMPORTANT : Cette opération va SUPPRIMER toutes vos données existantes !**

```powershell
cd c:\Users\DINH\AppWorkout\AppWorkout
python migrate_db.py
```

Le script va :
- ✅ Créer une sauvegarde de votre base de données actuelle
- ✅ Supprimer les anciennes données (comme convenu - Option C)
- ✅ Créer la nouvelle structure avec 3 tables :
  - `sessions` : id, name, date
  - `exercises` : id, session_id, exercise_name
  - `sets` : id, exercise_id, set_number, reps, weight

### 2️⃣ Lancer l'application

```powershell
python app.py
```

---

## 🎯 Nouvelles fonctionnalités

### Interface de saisie dynamique

- **Bouton "+ Ajouter une série"** : Ajoutez autant de séries que vous voulez
- **Champs individuels** : Reps et Poids pour chaque série
- **Suppression facile** : Bouton 🗑️ pour supprimer une série

### Calculs automatiques

1. **1RM (One Rep Max)** : Calculé automatiquement en prenant la série avec le 1RM **le plus élevé** parmi toutes vos séries
   - Formule d'Epley : `1RM = poids × (1 + reps/30)`

2. **Volume** : Somme de toutes les séries
   - `Volume total = Σ(reps × poids)` pour chaque série

3. **Statistiques** :
   - Poids maximum utilisé
   - Meilleur volume d'une série
   - Total de séries effectuées

### Templates de séances

Lorsque vous démarrez une séance depuis la page d'accueil :
- ✅ Toutes les séries de la dernière séance sont pré-remplies
- ✅ Vous pouvez modifier les valeurs individuellement
- ✅ Ajouter ou supprimer des séries

---

## 📊 Structure de la base de données

```sql
-- Table des séances
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table des exercices
CREATE TABLE exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    exercise_name TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
);

-- Table des séries individuelles (NOUVELLE)
CREATE TABLE sets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exercise_id INTEGER NOT NULL,
    set_number INTEGER NOT NULL,
    reps INTEGER NOT NULL,
    weight REAL NOT NULL,
    FOREIGN KEY (exercise_id) REFERENCES exercises (id) ON DELETE CASCADE
);
```

---

## 🔧 Modifications techniques

### Fichiers modifiés :

1. **`app.py`** :
   - ✅ `init_db()` : Nouvelle structure de tables
   - ✅ `/track` (POST) : Reçoit données JSON avec séries individuelles
   - ✅ `/session/<id>` : Affiche toutes les séries de chaque exercice
   - ✅ `/progress` : Calcule 1RM sur toutes les séries
   - ✅ `/start-session` : Charge les séries individuelles du template

2. **`templates/track.html`** :
   - ✅ Interface dynamique avec bouton "+ Ajouter une série"
   - ✅ Envoi des données en JSON
   - ✅ Pré-remplissage des templates avec séries

3. **`templates/session_detail.html`** :
   - ✅ Affichage détaillé de chaque série
   - ✅ Calcul du volume par série et total

4. **`templates/progress.html`** :
   - ✅ Affichage du 1RM calculé sur la meilleure série
   - ✅ Statistiques par série

### Nouveau fichier :

- **`migrate_db.py`** : Script de migration de la base de données

---

## 🎓 Exemple d'utilisation

### Créer une nouvelle séance :

1. Cliquez sur "📝 Nouvelle Séance"
2. Entrez le nom de la séance (ex: "Push Day")
3. Cliquez sur "➕ Ajouter un exercice"
4. Entrez le nom de l'exercice (ex: "Développé couché")
5. Pour chaque série :
   - Cliquez sur "➕ Ajouter une série"
   - Entrez les reps (ex: 8)
   - Entrez le poids (ex: 80)
6. Répétez pour toutes vos séries
7. Cliquez sur "✅ Valider la séance"

### Exemple avec progression pyramidale :

```
Développé couché
  Série 1 : 12 reps × 60kg  (échauffement)
  Série 2 : 10 reps × 70kg
  Série 3 : 8 reps × 80kg   (série de travail)
  Série 4 : 6 reps × 85kg   (série lourde)
  Série 5 : 15 reps × 50kg  (série de congestion)
```

---

## 💾 Sauvegarde

Le script de migration crée automatiquement une sauvegarde :
- 📁 Fichier : `database_backup_YYYYMMDD_HHMMSS.db`
- 📍 Emplacement : Même dossier que `database.db`

Si vous voulez revenir en arrière :
```powershell
# Remplacer database.db par la sauvegarde
copy database_backup_YYYYMMDD_HHMMSS.db database.db
```

---

## ❓ Questions fréquentes

**Q : Mes anciennes données seront-elles conservées ?**  
R : Non, conformément à votre choix (Option C), toutes les données existantes sont supprimées. Une sauvegarde est créée avant la migration.

**Q : Puis-je avoir des séries identiques ?**  
R : Oui ! Vous pouvez entrer les mêmes valeurs pour chaque série si vous le souhaitez.

**Q : Comment est calculé le 1RM ?**  
R : Le système calcule le 1RM pour chaque série (formule d'Epley) et garde le plus élevé.

**Q : Le volume est-il calculé différemment ?**  
R : Oui, maintenant c'est la somme de toutes les séries : `Σ(reps_i × poids_i)`

---

## 🐛 En cas de problème

Si vous rencontrez un problème :

1. Vérifiez que la migration a bien été effectuée
2. Vérifiez que les 3 tables existent :
   ```powershell
   python check_models.py
   ```
3. Consultez les messages d'erreur dans la console

---

## 📞 Support

Pour toute question ou problème, n'hésitez pas à me contacter !

**Bonne continuation avec votre nouveau système de suivi ! 💪🏋️**

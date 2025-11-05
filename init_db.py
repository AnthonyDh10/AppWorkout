#!/usr/bin/env python3
"""
Script pour initialiser la base de données avec les nouvelles tables pour les séances.
"""

import sqlite3
import os

def init_database():
    """Initialise la base de données avec toutes les tables nécessaires."""
    
    # Chemin vers le fichier de base de données
    db_path = 'database.db'
    
    print("🔧 Initialisation de la base de données...")
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Créer la table des séances
            print("📋 Création de la table 'sessions'...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Créer la table des exercices (sans sets, reps, weight)
            print("🏋️ Création de la table 'exercises'...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS exercises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    exercise_name TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
                )
            ''')
            
            # Créer la table des séries individuelles
            print("📊 Création de la table 'sets'...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exercise_id INTEGER NOT NULL,
                    set_number INTEGER NOT NULL,
                    reps INTEGER NOT NULL,
                    weight REAL NOT NULL,
                    FOREIGN KEY (exercise_id) REFERENCES exercises (id) ON DELETE CASCADE
                )
            ''')
            
            # Créer la table des programmes
            print("📅 Création de la table 'programmes'...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS programmes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nom TEXT NOT NULL,
                    description TEXT,
                    actif INTEGER DEFAULT 0,
                    archive INTEGER DEFAULT 0,
                    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Créer la table des séances de programmes
            print("📋 Création de la table 'programme_seances'...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS programme_seances (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    programme_id INTEGER NOT NULL,
                    ordre INTEGER NOT NULL,
                    nom_seance TEXT NOT NULL,
                    description TEXT,
                    completee INTEGER DEFAULT 0,
                    date_completion TIMESTAMP,
                    FOREIGN KEY (programme_id) REFERENCES programmes (id) ON DELETE CASCADE
                )
            ''')
            
            # Garder l'ancienne table pour compatibilité (deprecated)
            print("📊 Vérification de la table 'performance' (legacy)...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exercise TEXT NOT NULL,
                    sets INTEGER NOT NULL,
                    reps INTEGER NOT NULL,
                    weight REAL NOT NULL,
                    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Vérifier que les tables ont été créées
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            print("\n📋 Tables présentes dans la base de données :")
            for table in tables:
                print(f"  ✅ {table[0]}")
            
            conn.commit()
            print("\n✅ Base de données initialisée avec succès !")
            
    except sqlite3.Error as e:
        print(f"❌ Erreur lors de l'initialisation de la base de données : {e}")
        return False
    
    return True

def add_sample_data():
    """Ajoute des données d'exemple pour tester l'application."""
    
    print("\n🧪 Ajout de données d'exemple...")
    
    try:
        with sqlite3.connect('database.db') as conn:
            cursor = conn.cursor()
            
            # Ajouter une séance d'exemple
            cursor.execute(
                "INSERT INTO sessions (name) VALUES (?)",
                ("Séance Pectoraux/Triceps",)
            )
            session_id = cursor.lastrowid
            
            # Ajouter quelques exercices avec leurs séries
            sample_exercises = [
                ("Développé couché", [
                    (1, 8, 80.0),
                    (2, 7, 75.0),
                    (3, 6, 70.0),
                ]),
                ("Développé incliné", [
                    (1, 10, 60.0),
                    (2, 9, 60.0),
                    (3, 8, 55.0),
                ]),
                ("Dips", [
                    (1, 12, 0.0),
                    (2, 10, 0.0),
                    (3, 8, 0.0),
                ]),
            ]
            
            for exercise_name, sets_data in sample_exercises:
                # Créer l'exercice
                cursor.execute(
                    "INSERT INTO exercises (session_id, exercise_name) VALUES (?, ?)",
                    (session_id, exercise_name)
                )
                exercise_id = cursor.lastrowid
                
                # Ajouter les séries
                for set_number, reps, weight in sets_data:
                    cursor.execute(
                        "INSERT INTO sets (exercise_id, set_number, reps, weight) VALUES (?, ?, ?, ?)",
                        (exercise_id, set_number, reps, weight)
                    )
            
            # Ajouter un programme d'exemple
            cursor.execute(
                "INSERT INTO programmes (nom, description, actif) VALUES (?, ?, ?)",
                ("Programme PPL 6 jours", "Push/Pull/Legs 2x par semaine", 1)
            )
            programme_id = cursor.lastrowid
            
            # Ajouter les séances du programme
            programme_seances = [
                (1, "Push - Pectoraux/Épaules/Triceps", "4 exercices de développés, 3 exercices d'isolation"),
                (2, "Pull - Dos/Biceps", "Tractions, rowings, curls"),
                (3, "Legs - Jambes", "Squat, presse, leg curl, mollets"),
                (4, "Push - Focus Épaules", "Développé militaire, élévations latérales"),
                (5, "Pull - Focus Dos", "Soulevé de terre, rowing barre"),
                (6, "Legs - Focus Quadriceps", "Front squat, leg extension"),
            ]
            
            for ordre, nom_seance, description in programme_seances:
                cursor.execute(
                    "INSERT INTO programme_seances (programme_id, ordre, nom_seance, description) VALUES (?, ?, ?, ?)",
                    (programme_id, ordre, nom_seance, description)
                )
            
            conn.commit()
            print("✅ Données d'exemple ajoutées avec succès !")
            print("   - 1 séance avec 3 exercices et séries détaillées")
            print("   - 1 programme PPL avec 6 séances")
            
    except sqlite3.Error as e:
        print(f"❌ Erreur lors de l'ajout des données d'exemple : {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("🚀 Initialisation de l'application AppWorkout")
    print("=" * 50)
    
    # Initialiser la base de données
    if init_database():
        # Demander si on veut ajouter des données d'exemple
        response = input("\n📝 Voulez-vous ajouter des données d'exemple ? (o/n) : ").lower().strip()
        if response in ['o', 'oui', 'y', 'yes']:
            add_sample_data()
    
    print("\n🎉 Initialisation terminée ! Vous pouvez maintenant lancer l'application avec : python app.py")

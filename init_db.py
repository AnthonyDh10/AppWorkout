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
            
            # Créer la table des exercices
            print("🏋️ Création de la table 'exercises'...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS exercises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    exercise_name TEXT NOT NULL,
                    sets INTEGER NOT NULL,
                    reps INTEGER NOT NULL,
                    weight REAL NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions (id)
                )
            ''')
            
            # Garder l'ancienne table pour compatibilité
            print("📊 Vérification de la table 'performance'...")
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
            
            # Ajouter quelques exercices d'exemple
            sample_exercises = [
                ("Développé couché", 4, 10, 70.0),
                ("Développé incliné", 3, 12, 60.0),
                ("Dips", 3, 15, 0.0),
                ("Extension triceps", 3, 12, 30.0)
            ]
            
            for exercise_name, sets, reps, weight in sample_exercises:
                cursor.execute(
                    "INSERT INTO exercises (session_id, exercise_name, sets, reps, weight) VALUES (?, ?, ?, ?, ?)",
                    (session_id, exercise_name, sets, reps, weight)
                )
            
            conn.commit()
            print("✅ Données d'exemple ajoutées avec succès !")
            
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

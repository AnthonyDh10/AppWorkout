#!/usr/bin/env python3
"""
Script de migration pour corriger le schéma de la base de données
Corrige l'erreur "NOT NULL constraint failed: exercises.sets"
"""

import sqlite3
import os
from datetime import datetime

def backup_database():
    """Créer une sauvegarde de la base de données"""
    if os.path.exists('database.db'):
        backup_name = f'database_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
        import shutil
        shutil.copy2('database.db', backup_name)
        print(f"✅ Sauvegarde créée: {backup_name}")
        return backup_name
    return None

def check_current_schema():
    """Vérifier le schéma actuel de la table exercises"""
    try:
        with sqlite3.connect('database.db') as conn:
            cur = conn.cursor()
            
            # Vérifier si la table exercises existe et obtenir sa structure
            cur.execute("PRAGMA table_info(exercises)")
            columns = cur.fetchall()
            
            print("\n🔍 Structure actuelle de la table 'exercises':")
            for col in columns:
                print(f"   {col[1]} {col[2]} {'NOT NULL' if col[3] else 'NULL'} {'DEFAULT ' + str(col[4]) if col[4] else ''}")
            
            return columns
    except sqlite3.Error as e:
        print(f"❌ Erreur lors de la vérification du schéma: {e}")
        return None

def migrate_exercises_table():
    """Migrer la table exercises vers le nouveau schéma"""
    try:
        with sqlite3.connect('database.db') as conn:
            cur = conn.cursor()
            
            print("\n🔧 Migration de la table exercises...")
            
            # Étape 1: Vérifier si la table exercises a des colonnes problématiques
            cur.execute("PRAGMA table_info(exercises)")
            columns = cur.fetchall()
            column_names = [col[1] for col in columns]
            
            has_sets_column = 'sets' in column_names
            has_reps_column = 'reps' in column_names
            has_weight_column = 'weight' in column_names
            
            if has_sets_column or has_reps_column or has_weight_column:
                print("   ⚠️ Anciennes colonnes détectées, migration nécessaire...")
                
                # Étape 2: Sauvegarder les données existantes
                cur.execute("SELECT * FROM exercises")
                existing_data = cur.fetchall()
                print(f"   📊 {len(existing_data)} enregistrements à migrer")
                
                # Étape 3: Renommer l'ancienne table
                cur.execute("ALTER TABLE exercises RENAME TO exercises_old")
                print("   ✅ Ancienne table renommée")
                
                # Étape 4: Créer la nouvelle table avec le bon schéma
                cur.execute('''
                    CREATE TABLE exercises (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id INTEGER NOT NULL,
                        exercise_name TEXT NOT NULL,
                        FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
                    )
                ''')
                print("   ✅ Nouvelle table créée")
                
                # Étape 5: Migrer les données (uniquement session_id et exercise_name)
                for row in existing_data:
                    # L'ancienne structure était probablement: id, session_id, exercise_name, sets, reps, weight
                    old_id = row[0]
                    session_id = row[1] 
                    exercise_name = row[2]
                    
                    # Insérer dans la nouvelle table
                    cur.execute(
                        "INSERT INTO exercises (session_id, exercise_name) VALUES (?, ?)",
                        (session_id, exercise_name)
                    )
                    new_exercise_id = cur.lastrowid
                    
                    # Si on avait des données de sets/reps/weight, les migrer vers la table sets
                    if len(row) >= 6 and row[3] and row[4] and row[5]:  # sets, reps, weight
                        sets_count = row[3]
                        reps = row[4]
                        weight = row[5]
                        
                        # Créer les entrées dans la table sets
                        for set_num in range(1, sets_count + 1):
                            cur.execute(
                                "INSERT INTO sets (exercise_id, set_number, reps, weight) VALUES (?, ?, ?, ?)",
                                (new_exercise_id, set_num, reps, weight)
                            )
                
                print(f"   ✅ Données migrées pour {len(existing_data)} exercices")
                
                # Étape 6: Supprimer l'ancienne table
                cur.execute("DROP TABLE exercises_old")
                print("   ✅ Ancienne table supprimée")
                
            else:
                print("   ✅ Table exercises déjà au bon format")
            
            # Vérifier que la table sets existe
            cur.execute("PRAGMA table_info(sets)")
            sets_columns = cur.fetchall()
            
            if not sets_columns:
                print("   🔧 Création de la table sets...")
                cur.execute('''
                    CREATE TABLE sets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        exercise_id INTEGER NOT NULL,
                        set_number INTEGER NOT NULL,
                        reps INTEGER NOT NULL,
                        weight REAL NOT NULL,
                        FOREIGN KEY (exercise_id) REFERENCES exercises (id) ON DELETE CASCADE
                    )
                ''')
                print("   ✅ Table sets créée")
            
            conn.commit()
            print("✅ Migration terminée avec succès!")
            
    except sqlite3.Error as e:
        print(f"❌ Erreur lors de la migration: {e}")
        return False
    except Exception as e:
        print(f"❌ Erreur inattendue: {e}")
        return False
    
    return True

def verify_migration():
    """Vérifier que la migration s'est bien passée"""
    try:
        with sqlite3.connect('database.db') as conn:
            cur = conn.cursor()
            
            print("\n🔍 Vérification post-migration:")
            
            # Vérifier la structure de exercises
            cur.execute("PRAGMA table_info(exercises)")
            exercises_columns = cur.fetchall()
            print(f"   📋 Table exercises: {len(exercises_columns)} colonnes")
            for col in exercises_columns:
                print(f"      - {col[1]} {col[2]}")
            
            # Vérifier la structure de sets
            cur.execute("PRAGMA table_info(sets)")
            sets_columns = cur.fetchall()
            print(f"   📋 Table sets: {len(sets_columns)} colonnes")
            for col in sets_columns:
                print(f"      - {col[1]} {col[2]}")
            
            # Compter les enregistrements
            cur.execute("SELECT COUNT(*) FROM exercises")
            exercises_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM sets")
            sets_count = cur.fetchone()[0]
            
            print(f"   📊 {exercises_count} exercices dans la base")
            print(f"   📊 {sets_count} séries dans la base")
            
            return True
            
    except sqlite3.Error as e:
        print(f"❌ Erreur lors de la vérification: {e}")
        return False

def main():
    print("🔧 Script de migration de la base de données")
    print("=" * 50)
    
    if not os.path.exists('database.db'):
        print("❌ Fichier database.db introuvable")
        return
    
    # 1. Créer une sauvegarde
    backup_file = backup_database()
    
    # 2. Vérifier le schéma actuel
    current_schema = check_current_schema()
    
    if current_schema is None:
        print("❌ Impossible de vérifier le schéma actuel")
        return
    
    # 3. Effectuer la migration
    if migrate_exercises_table():
        # 4. Vérifier le résultat
        if verify_migration():
            print("\n✅ Migration réussie!")
            print("Vous pouvez maintenant redémarrer votre application Flask.")
            if backup_file:
                print(f"💾 Sauvegarde disponible: {backup_file}")
        else:
            print("\n⚠️ Migration terminée mais vérification échouée")
    else:
        print("\n❌ Migration échouée")
        if backup_file:
            print(f"💾 Restaurez la sauvegarde si nécessaire: {backup_file}")

if __name__ == "__main__":
    main()
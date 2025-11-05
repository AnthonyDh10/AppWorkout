"""
Script de migration de la base de données
- Supprime les anciennes données (Option C)
- Crée la nouvelle structure avec table 'sets' pour séries individuelles
"""

import sqlite3
import os
from datetime import datetime

def migrate_database():
    """Migre la base de données vers la nouvelle structure"""
    
    db_path = 'database.db'
    backup_path = f'database_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
    
    # 1. Créer une sauvegarde de la base de données existante
    if os.path.exists(db_path):
        print(f"📦 Création de la sauvegarde : {backup_path}")
        import shutil
        shutil.copy2(db_path, backup_path)
        print(f"✅ Sauvegarde créée avec succès")
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 2. Supprimer les anciennes tables (Option C)
            print("\n🗑️  Suppression des anciennes données...")
            cursor.execute("DROP TABLE IF EXISTS exercises")
            cursor.execute("DROP TABLE IF EXISTS sessions")
            cursor.execute("DROP TABLE IF EXISTS performance")
            print("✅ Anciennes données supprimées")
            
            # 3. Créer la nouvelle table sessions
            print("\n🔨 Création de la nouvelle table 'sessions'...")
            cursor.execute('''
                CREATE TABLE sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            print("✅ Table 'sessions' créée")
            
            # 4. Créer la nouvelle table exercises (sans sets, reps, weight)
            print("\n🔨 Création de la nouvelle table 'exercises'...")
            cursor.execute('''
                CREATE TABLE exercises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    exercise_name TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
                )
            ''')
            print("✅ Table 'exercises' créée")
            
            # 5. Créer la nouvelle table sets (séries individuelles)
            print("\n🔨 Création de la nouvelle table 'sets'...")
            cursor.execute('''
                CREATE TABLE sets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exercise_id INTEGER NOT NULL,
                    set_number INTEGER NOT NULL,
                    reps INTEGER NOT NULL,
                    weight REAL NOT NULL,
                    FOREIGN KEY (exercise_id) REFERENCES exercises (id) ON DELETE CASCADE
                )
            ''')
            print("✅ Table 'sets' créée")
            
            conn.commit()
            
            print("\n" + "="*60)
            print("✅ MIGRATION RÉUSSIE !")
            print("="*60)
            print(f"📊 Nouvelle structure :")
            print(f"   - sessions : id, name, date")
            print(f"   - exercises : id, session_id, exercise_name")
            print(f"   - sets : id, exercise_id, set_number, reps, weight")
            print(f"\n💾 Sauvegarde disponible : {backup_path}")
            print("="*60)
            
    except sqlite3.Error as e:
        print(f"\n❌ Erreur lors de la migration : {e}")
        print(f"💡 La sauvegarde est disponible : {backup_path}")
        raise
    except Exception as e:
        print(f"\n❌ Erreur inattendue : {e}")
        raise

if __name__ == "__main__":
    print("="*60)
    print("🚀 MIGRATION DE LA BASE DE DONNÉES")
    print("="*60)
    print("\n⚠️  ATTENTION : Cette opération va :")
    print("   1. Créer une sauvegarde de votre base actuelle")
    print("   2. SUPPRIMER toutes les données existantes")
    print("   3. Créer la nouvelle structure")
    print("\n" + "="*60)
    
    response = input("\nContinuer ? (oui/non) : ").strip().lower()
    
    if response in ['oui', 'o', 'yes', 'y']:
        migrate_database()
    else:
        print("\n❌ Migration annulée")

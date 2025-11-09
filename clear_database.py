#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script pour vider complètement la base de données AppWorkout
Supprime toutes les données mais conserve la structure des tables
"""

import sqlite3
import os
from datetime import datetime

def clear_database():
    """Vide toutes les tables de la base de données"""
    
    # Vérifier que nous sommes dans le bon répertoire
    db_path = 'database.db'
    if not os.path.exists(db_path):
        print("❌ Fichier database.db non trouvé dans le répertoire courant")
        print(f"📂 Répertoire courant: {os.getcwd()}")
        return False
    
    try:
        # Créer une sauvegarde avant suppression
        backup_name = f"database_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        print(f"💾 Création d'une sauvegarde: {backup_name}")
        
        # Copier la base de données
        import shutil
        shutil.copy2(db_path, backup_name)
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            print("🔍 Analyse de la base de données...")
            
            # Lister toutes les tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [table[0] for table in cursor.fetchall()]
            
            if not tables:
                print("ℹ️  Aucune table trouvée dans la base de données")
                return True
            
            print(f"📋 Tables trouvées: {', '.join(tables)}")
            
            # Compter les enregistrements avant suppression
            total_records = 0
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                if count > 0:
                    print(f"  📊 {table}: {count} enregistrements")
                    total_records += count
            
            if total_records == 0:
                print("ℹ️  La base de données est déjà vide")
                return True
            
            print(f"\n🗑️  Suppression de {total_records} enregistrements...")
            
            # Désactiver les contraintes de clé étrangère temporairement
            cursor.execute("PRAGMA foreign_keys = OFF")
            
            # Vider chaque table dans l'ordre inverse des dépendances
            # (pour éviter les erreurs de clé étrangère)
            deletion_order = [
                'sets',                    # Dépend de exercises
                'programme_exercices',     # Dépend de programme_seances
                'programme_seances',       # Dépend de programmes
                'exercises',               # Dépend de sessions
                'performance',             # Table de performance
                'sessions',                # Table principale
                'programmes'               # Table indépendante
            ]
            
            deleted_tables = []
            for table in deletion_order:
                if table in tables:
                    cursor.execute(f"DELETE FROM {table}")
                    affected = cursor.rowcount
                    if affected > 0:
                        print(f"  ✅ {table}: {affected} enregistrements supprimés")
                        deleted_tables.append(table)
            
            # Supprimer les tables restantes (au cas où il y en aurait d'autres)
            for table in tables:
                if table not in deleted_tables:
                    cursor.execute(f"DELETE FROM {table}")
                    affected = cursor.rowcount
                    if affected > 0:
                        print(f"  ✅ {table}: {affected} enregistrements supprimés")
            
            # Remettre les contraintes de clé étrangère
            cursor.execute("PRAGMA foreign_keys = ON")
            
            # Réinitialiser les compteurs d'auto-increment
            for table in tables:
                cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")
            
            conn.commit()
            
        # Optimiser la base de données (récupérer l'espace) - en dehors de la transaction
        print("🗜️  Optimisation de la base de données...")
        with sqlite3.connect(db_path) as conn:
            conn.execute("VACUUM")
            
        print("\n✅ Base de données vidée avec succès!")
        print(f"💾 Sauvegarde disponible: {backup_name}")
        
        # Vérification finale
        print("\n🔍 Vérification finale...")
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                if count > 0:
                    print(f"  ⚠️  {table}: {count} enregistrements restants")
                else:
                    print(f"  ✅ {table}: vide")
            
            return True
            
    except sqlite3.Error as e:
        print(f"❌ Erreur SQLite: {e}")
        return False
    except Exception as e:
        print(f"❌ Erreur inattendue: {e}")
        return False

def confirm_deletion():
    """Demande confirmation avant suppression"""
    print("⚠️  ATTENTION: Cette opération va supprimer TOUTES les données de la base!")
    print("📋 Cela inclut:")
    print("   - Toutes les séances d'entraînement")
    print("   - Tous les exercices et séries")
    print("   - Tous les programmes d'entraînement")
    print("   - Toutes les statistiques de progression")
    print()
    
    response = input("Voulez-vous continuer? (tapez 'OUI' en majuscules pour confirmer): ")
    return response == "OUI"

def main():
    """Fonction principale"""
    print("🗑️  Script de nettoyage de la base de données AppWorkout")
    print("=" * 50)
    
    if not confirm_deletion():
        print("❌ Opération annulée par l'utilisateur")
        return
    
    success = clear_database()
    
    if success:
        print("\n🎉 Nettoyage terminé avec succès!")
        print("💡 Vous pouvez maintenant relancer l'application pour créer de nouvelles données")
    else:
        print("\n❌ Échec du nettoyage de la base de données")
        print("💡 Vérifiez les messages d'erreur ci-dessus")

if __name__ == "__main__":
    main()
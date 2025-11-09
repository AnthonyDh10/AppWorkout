#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de test pour vérifier la copie des programmes
"""

import sqlite3
import os

def test_program_copy():
    """Teste la fonction de copie de programme"""
    
    # S'assurer d'être dans le bon répertoire
    os.chdir(r'c:\Users\antho\Documents\GitHub\AppWorkout')
    
    try:
        with sqlite3.connect('database.db') as conn:
            cur = conn.cursor()
            
            print("🔍 Test de la fonction de copie de programme")
            print("=" * 50)
            
            # Lister les programmes existants
            cur.execute("SELECT id, nom, description FROM programmes WHERE archive = 0")
            programmes = cur.fetchall()
            
            if not programmes:
                print("❌ Aucun programme trouvé pour le test")
                return
            
            print("📋 Programmes disponibles:")
            for prog in programmes:
                print(f"  ID {prog[0]}: {prog[1]}")
                
                # Compter les séances
                cur.execute("SELECT COUNT(*) FROM programme_seances WHERE programme_id = ?", (prog[0],))
                nb_seances = cur.fetchone()[0]
                
                # Compter les exercices
                cur.execute("""
                    SELECT COUNT(*) FROM programme_exercices pe
                    JOIN programme_seances ps ON pe.seance_id = ps.id
                    WHERE ps.programme_id = ?
                """, (prog[0],))
                nb_exercices = cur.fetchone()[0]
                
                print(f"    → {nb_seances} séances, {nb_exercices} exercices")
            
            # Prendre le premier programme pour le test
            programme_id = programmes[0][0]
            programme_nom = programmes[0][1]
            
            print(f"\n🔄 Test de copie du programme '{programme_nom}' (ID: {programme_id})")
            
            # Compter les éléments avant copie
            cur.execute("SELECT COUNT(*) FROM programmes")
            nb_programmes_avant = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM programme_seances")
            nb_seances_avant = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM programme_exercices")
            nb_exercices_avant = cur.fetchone()[0]
            
            print(f"📊 Avant copie: {nb_programmes_avant} programmes, {nb_seances_avant} séances, {nb_exercices_avant} exercices")
            
            # Effectuer la copie (simulation de la fonction de l'app)
            # Récupérer le programme original
            cur.execute("SELECT nom, description FROM programmes WHERE id = ?", (programme_id,))
            programme = cur.fetchone()
            
            if programme:
                # Créer la copie
                nouveau_nom = f"{programme[0]} (Copie Test)"
                nouvelle_description = programme[1] if programme[1] else None
                cur.execute("INSERT INTO programmes (nom, description) VALUES (?, ?)", (nouveau_nom, nouvelle_description))
                nouveau_programme_id = cur.lastrowid
                
                print(f"✅ Programme copié avec l'ID {nouveau_programme_id}")
                
                # Copier les séances
                cur.execute("""
                    SELECT id, ordre, nom_seance, description
                    FROM programme_seances 
                    WHERE programme_id = ? 
                    ORDER BY ordre
                """, (programme_id,))
                seances = cur.fetchall()
                
                print(f"🔄 Copie de {len(seances)} séances...")
                
                for seance in seances:
                    ancien_seance_id, ordre, nom_seance, description = seance
                    
                    # Créer la nouvelle séance
                    cur.execute("""
                        INSERT INTO programme_seances (programme_id, ordre, nom_seance, description)
                        VALUES (?, ?, ?, ?)
                    """, (nouveau_programme_id, ordre, nom_seance, description))
                    nouveau_seance_id = cur.lastrowid
                    
                    # Copier tous les exercices de cette séance
                    cur.execute("""
                        SELECT ordre, nom_exercice, series, repetitions, notes
                        FROM programme_exercices 
                        WHERE seance_id = ?
                        ORDER BY ordre
                    """, (ancien_seance_id,))
                    exercices = cur.fetchall()
                    
                    print(f"  📝 Séance '{nom_seance}': {len(exercices)} exercices")
                    
                    for exercice in exercices:
                        ordre_ex, nom_exercice, series, repetitions, notes = exercice
                        cur.execute("""
                            INSERT INTO programme_exercices (seance_id, ordre, nom_exercice, series, repetitions, notes)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (nouveau_seance_id, ordre_ex, nom_exercice, series, repetitions, notes))
                
                conn.commit()
                
                # Vérifier après copie
                cur.execute("SELECT COUNT(*) FROM programmes")
                nb_programmes_apres = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(*) FROM programme_seances")
                nb_seances_apres = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(*) FROM programme_exercices")
                nb_exercices_apres = cur.fetchone()[0]
                
                print(f"📊 Après copie: {nb_programmes_apres} programmes, {nb_seances_apres} séances, {nb_exercices_apres} exercices")
                print(f"➕ Ajouté: {nb_programmes_apres - nb_programmes_avant} programme, {nb_seances_apres - nb_seances_avant} séances, {nb_exercices_apres - nb_exercices_avant} exercices")
                
                # Vérifier le contenu de la copie
                print(f"\n🔍 Vérification du programme copié (ID: {nouveau_programme_id}):")
                
                cur.execute("""
                    SELECT ps.nom_seance, COUNT(pe.id) as nb_exercices
                    FROM programme_seances ps
                    LEFT JOIN programme_exercices pe ON ps.id = pe.seance_id
                    WHERE ps.programme_id = ?
                    GROUP BY ps.id, ps.nom_seance
                    ORDER BY ps.ordre
                """, (nouveau_programme_id,))
                
                seances_copiees = cur.fetchall()
                for seance in seances_copiees:
                    print(f"  ✅ {seance[0]}: {seance[1]} exercices")
                
                print("\n🎉 Test de copie terminé avec succès!")
                print("💡 Vous pouvez maintenant vérifier dans l'interface web")
                
    except sqlite3.Error as e:
        print(f"❌ Erreur SQLite: {e}")
    except Exception as e:
        print(f"❌ Erreur inattendue: {e}")

if __name__ == "__main__":
    test_program_copy()
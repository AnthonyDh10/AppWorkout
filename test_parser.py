#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Test du Parser de Programme IA
==========================================

Ce script permet de tester le parser sans lancer l'application Flask.
Utile pour le débogage et les tests rapides.

Usage:
    python test_parser.py [fichier_texte]
    
    Si aucun fichier n'est spécifié, utilise EXEMPLE_REPONSE_IA.txt

Exemples:
    python test_parser.py
    python test_parser.py EXEMPLE_REPONSE_IA.txt
    python test_parser.py ma_reponse_ia.txt
"""

import re
import sys
from pathlib import Path


def parse_programme_ia_robuste(programme_text_clean, nom_programme="Programme"):
    """
    Parser robuste pour les programmes générés par l'IA
    Supporte DEUX formats :
    1. Format avec blocs [PARSE_START]...[PARSE_END] (ancien format)
    2. Format avec séparateurs ──────── et pattern "Nom : X x Y reps @ RIR ..." (nouveau format)
    
    Args:
        programme_text_clean (str): Texte nettoyé du programme (sans HTML)
        nom_programme (str): Nom du programme pour les logs
        
    Returns:
        tuple: (seances, total_exercices, success)
    """
    
    print(f"\n{'='*80}")
    print(f"🔍 DEBUG PARSING ROBUSTE - Programme: {nom_programme}")
    print(f"{'='*80}")
    print(f"📄 Longueur du texte: {len(programme_text_clean)} caractères")
    
    # Afficher un aperçu du texte
    preview_lines = programme_text_clean.split('\n')[:20]
    print(f"\n📋 Aperçu des 20 premières lignes:")
    for idx, line in enumerate(preview_lines, 1):
        print(f"   {idx:3d}: {line[:100]}")
    
    lignes = programme_text_clean.split('\n')
    
    # Détecter le format utilisé
    has_parse_blocks = '[PARSE_START]' in programme_text_clean
    has_separators = '─' * 10 in programme_text_clean  # Au moins 10 tirets consécutifs
    
    print(f"\n🔎 Détection du format:")
    print(f"   Blocs [PARSE_START]: {'✅ OUI' if has_parse_blocks else '❌ NON'}")
    print(f"   Séparateurs ────: {'✅ OUI' if has_separators else '❌ NON'}")
    
    if has_parse_blocks:
        print(f"\n📌 Utilisation du FORMAT ANCIEN (avec blocs de parsing)")
        return parse_avec_blocs(lignes, nom_programme)
    else:
        print(f"\n📌 Utilisation du FORMAT NOUVEAU (détection automatique)")
        return parse_sans_blocs(lignes, nom_programme)


def parse_avec_blocs(lignes, nom_programme):
    """Parser ancien format avec blocs [PARSE_START]...[PARSE_END]"""
    seances = []
    ordre_seance = 1
    
    i = 0
    while i < len(lignes):
        ligne = lignes[i].strip()
        
        # Détecter une nouvelle séance
        if re.match(r'^SEANCE\s*\d*\s*[:：]', ligne, re.IGNORECASE):
            match = re.match(r'^SEANCE\s*\d*\s*[:：]\s*(.+)', ligne, re.IGNORECASE)
            if match:
                nom_seance = match.group(1).strip()
                print(f"\n{'─'*80}")
                print(f"🆕 SÉANCE {ordre_seance}: {nom_seance}")
                
                exercices = []
                j = i + 1
                
                # Chercher [PARSE_START]
                while j < len(lignes) and '[PARSE_START]' not in lignes[j]:
                    j += 1
                
                if j < len(lignes) and '[PARSE_START]' in lignes[j]:
                    print(f"   ✅ [PARSE_START] trouvé")
                    j += 1
                    ordre_exercice = 1
                    
                    # Lire les exercices
                    while j < len(lignes) and '[PARSE_END]' not in lignes[j]:
                        ligne_ex = lignes[j].strip()
                        
                        if ligne_ex.startswith('EXERCICE:'):
                            parts = ligne_ex.split('|')
                            
                            nom_exercice = parts[0].replace('EXERCICE:', '').strip()
                            series = None
                            repetitions = None
                            notes = ''
                            
                            for part in parts[1:]:
                                part = part.strip()
                                if part.startswith('SERIES:'):
                                    try:
                                        series = int(part.replace('SERIES:', '').strip())
                                    except ValueError:
                                        pass
                                elif part.startswith('REPS:'):
                                    repetitions = part.replace('REPS:', '').strip()
                                elif part.startswith('NOTES:'):
                                    notes = part.replace('NOTES:', '').strip()
                            
                            exercices.append({
                                'ordre': ordre_exercice,
                                'nom': nom_exercice[:200],
                                'series': series,
                                'repetitions': repetitions,
                                'notes': notes[:500]
                            })
                            ordre_exercice += 1
                            print(f"      ✅ Ex {ordre_exercice-1}: {nom_exercice} | {series}x{repetitions}")
                        
                        j += 1
                    
                    i = j
                else:
                    print(f"   ❌ [PARSE_START] NON TROUVÉ")
                
                seances.append({
                    'ordre': ordre_seance,
                    'nom': nom_seance[:200],
                    'exercices': exercices
                })
                ordre_seance += 1
                print(f"   📊 Total: {len(exercices)} exercice(s)")
        
        i += 1
    
    total_exercices = sum(len(s.get('exercices', [])) for s in seances)
    success = len(seances) > 0 and total_exercices > 0
    
    print(f"\n📊 RÉSUMÉ: {len(seances)} séance(s), {total_exercices} exercice(s)")
    return seances, total_exercices, success


def parse_sans_blocs(lignes, nom_programme):
    """Parser nouveau format sans blocs, détection par pattern"""
    seances = []
    ordre_seance = 1
    
    i = 0
    while i < len(lignes):
        ligne = lignes[i].strip()
        
        # Détecter une séance avec séparateur ─────── SEANCE X: Nom
        # OU simplement SEANCE X: Nom
        seance_match = None
        
        # Pattern 1: Avec séparateurs
        if '─' in ligne and 'SEANCE' in ligne.upper():
            seance_match = re.search(r'SEANCE\s*(\d+)\s*[:：]\s*(.+)', ligne, re.IGNORECASE)
        # Pattern 2: Sans séparateurs
        elif re.match(r'^SEANCE\s*\d+\s*[:：]', ligne, re.IGNORECASE):
            seance_match = re.match(r'^SEANCE\s*(\d+)\s*[:：]\s*(.+)', ligne, re.IGNORECASE)
        
        if seance_match:
            num_seance = seance_match.group(1) if seance_match.lastindex >= 1 else str(ordre_seance)
            nom_seance = seance_match.group(2).strip() if seance_match.lastindex >= 2 else ligne.split(':', 1)[1].strip()
            
            print(f"\n{'─'*80}")
            print(f"🆕 SÉANCE {ordre_seance}: {nom_seance}")
            
            exercices = []
            j = i + 1
            ordre_exercice = 1
            
            # Lire les exercices jusqu'à la prochaine séance ou fin
            while j < len(lignes):
                ligne_ex = lignes[j].strip()
                
                # Arrêter si on trouve une nouvelle séance
                if ('─' in ligne_ex and 'SEANCE' in ligne_ex.upper()) or re.match(r'^SEANCE\s*\d+\s*[:：]', ligne_ex, re.IGNORECASE):
                    break
                
                # Pattern d'exercice: Nom (Matériel) : X x Y reps @ RIR Z, T min repos
                # OU : Nom : X x Y reps @ RIR Z, T min repos
                # Patterns acceptés :
                # - Avec tiret au début : "- Développé couché..."
                # - Sans tiret : "Développé couché..."
                
                exercice_pattern = r'^-?\s*(.+?)\s*:\s*(\d+)\s*x\s*([0-9\-]+)\s*reps?\s*@\s*RIR\s*([0-9\-]+)\s*,?\s*(.+?)(?:min|minutes)?\s*repos'
                match_ex = re.match(exercice_pattern, ligne_ex, re.IGNORECASE)
                
                if match_ex:
                    nom_exercice = match_ex.group(1).strip()
                    series = int(match_ex.group(2))
                    repetitions = match_ex.group(3).strip()
                    rir = match_ex.group(4).strip()
                    temps_repos = match_ex.group(5).strip()
                    
                    # Construire les notes
                    notes = f"RIR {rir}, repos {temps_repos} min"
                    
                    exercices.append({
                        'ordre': ordre_exercice,
                        'nom': nom_exercice[:200],
                        'series': series,
                        'repetitions': repetitions,
                        'notes': notes[:500]
                    })
                    ordre_exercice += 1
                    print(f"      ✅ Ex {ordre_exercice-1}: {nom_exercice} | {series}x{repetitions} | {notes}")
                elif ligne_ex and not ligne_ex.startswith('━') and not ligne_ex.startswith('─'):
                    # Ligne non vide mais qui ne match pas le pattern
                    if len(ligne_ex) > 10:  # Ignorer les lignes très courtes
                        print(f"      ⚠️ Ligne ignorée: {ligne_ex[:80]}")
                
                j += 1
            
            seances.append({
                'ordre': ordre_seance,
                'nom': nom_seance[:200],
                'exercices': exercices
            })
            ordre_seance += 1
            print(f"   📊 Total: {len(exercices)} exercice(s)")
            
            i = j - 1  # -1 car on va faire i+1 après
        
        i += 1
    
    total_exercices = sum(len(s.get('exercices', [])) for s in seances)
    success = len(seances) > 0 and total_exercices > 0
    
    print(f"\n📊 RÉSUMÉ: {len(seances)} séance(s), {total_exercices} exercice(s)")
    return seances, total_exercices, success


def main():
    """Fonction principale"""
    
    # Déterminer le fichier à tester
    if len(sys.argv) > 1:
        fichier = Path(sys.argv[1])
    else:
        fichier = Path(__file__).parent / "EXEMPLE_REPONSE_IA.txt"
    
    print(f"\n📂 Fichier à parser: {fichier}")
    
    # Vérifier que le fichier existe
    if not fichier.exists():
        print(f"❌ Erreur: Le fichier '{fichier}' n'existe pas")
        print(f"\nUsage: python test_parser.py [fichier_texte]")
        return 1
    
    # Lire le fichier
    try:
        with open(fichier, 'r', encoding='utf-8') as f:
            contenu = f.read()
    except Exception as e:
        print(f"❌ Erreur lors de la lecture du fichier: {e}")
        return 1
    
    # Enlever les balises HTML (au cas où)
    contenu_clean = re.sub('<[^<]+?>', '', contenu)
    
    # Parser
    nom_programme = fichier.stem  # Nom du fichier sans extension
    seances, total_ex, success = parse_programme_ia_robuste(contenu_clean, nom_programme)
    
    # Afficher le résultat
    if success:
        print("✅ PARSING RÉUSSI !")
        print(f"   {len(seances)} séance(s) et {total_ex} exercice(s) détectés")
        return 0
    elif len(seances) > 0:
        print("⚠️ PARSING PARTIEL")
        print(f"   {len(seances)} séance(s) détectée(s) mais 0 exercice !")
        print("   Vérifiez le format des exercices")
        return 1
    else:
        print("❌ ÉCHEC DU PARSING")
        print("   Aucune séance détectée")
        print("   Vérifiez que les titres commencent par 'SEANCE X:'")
        return 1


if __name__ == "__main__":
    exit(main())

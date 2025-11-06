#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test rapide du nouveau parser
"""

import re

# Exemple de réponse IA (nouveau format)
EXEMPLE_NOUVEAU = """
Voici votre programme pour les 5 prochaines semaines.

──────────────────────────────────────── SEANCE 1: Push / Legs A

Développé couché (Barre) : 4 x 6-8 reps @ RIR 2-3, 2.5 min repos
Squat (Barre) : 3 x 8-10 reps @ RIR 2-3, 2 min repos

──────────────────────────────────────── SEANCE 2: Pull / Legs B

Tractions : 4 x 6-8 reps @ RIR 2-3, 2.5 min repos
Rowing barre : 3 x 8-10 reps @ RIR 2-3, 2 min repos
"""

def test_pattern():
    """Test du pattern regex"""
    ligne = "Développé couché (Barre) : 4 x 6-8 reps @ RIR 2-3, 2.5 min repos"
    
    pattern = r'^-?\s*(.+?)\s*:\s*(\d+)\s*x\s*([0-9\-]+)\s*reps?\s*@\s*RIR\s*([0-9\-]+)\s*,?\s*(.+?)(?:min|minutes)?\s*repos'
    match = re.match(pattern, ligne, re.IGNORECASE)
    
    if match:
        print("✅ Pattern match!")
        print(f"   Nom: {match.group(1)}")
        print(f"   Séries: {match.group(2)}")
        print(f"   Reps: {match.group(3)}")
        print(f"   RIR: {match.group(4)}")
        print(f"   Repos: {match.group(5)}")
    else:
        print("❌ Pattern ne match pas")

def test_seance_detection():
    """Test de la détection de séance"""
    ligne1 = "──────────────────────────────────────── SEANCE 1: Push / Legs A"
    ligne2 = "SEANCE 2: Pull / Legs B"
    
    for ligne in [ligne1, ligne2]:
        print(f"\nTest: {ligne}")
        
        # Pattern 1: Avec séparateurs
        if '─' in ligne and 'SEANCE' in ligne.upper():
            match = re.search(r'SEANCE\s*(\d+)\s*[:：]\s*(.+)', ligne, re.IGNORECASE)
            if match:
                print(f"✅ Match avec séparateur - Séance {match.group(1)}: {match.group(2)}")
        
        # Pattern 2: Sans séparateurs  
        if re.match(r'^SEANCE\s*\d+\s*[:：]', ligne, re.IGNORECASE):
            match = re.match(r'^SEANCE\s*(\d+)\s*[:：]\s*(.+)', ligne, re.IGNORECASE)
            if match:
                print(f"✅ Match sans séparateur - Séance {match.group(1)}: {match.group(2)}")

if __name__ == "__main__":
    print("="*80)
    print("TEST DU PATTERN D'EXERCICE")
    print("="*80)
    test_pattern()
    
    print("\n" + "="*80)
    print("TEST DE LA DÉTECTION DE SÉANCE")
    print("="*80)
    test_seance_detection()

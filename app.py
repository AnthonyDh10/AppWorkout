import os
from flask import Flask, render_template, request, jsonify, redirect
import google.generativeai as genai
from dotenv import load_dotenv
import sqlite3
import markdown
import json
from datetime import datetime

load_dotenv() # Load environment variables from .env
base_dir = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(base_dir, 'templates'), static_folder=os.path.join(base_dir, 'static'))

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def format_date(date_string):
    """Convertit une date au format DD-MM-YYYY"""
    if not date_string:
        return ""
    
    try:
        # Essayer différents formats de date
        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y']:
            try:
                dt = datetime.strptime(str(date_string)[:19], fmt)
                return dt.strftime('%d-%m-%Y')
            except ValueError:
                continue
        
        # Si aucun format ne fonctionne, essayer de prendre juste les premiers caractères
        if len(str(date_string)) >= 10:
            # Format YYYY-MM-DD
            parts = str(date_string)[:10].split('-')
            if len(parts) == 3:
                return f"{parts[2]}-{parts[1]}-{parts[0]}"
        
        return str(date_string)[:10]
    except Exception as e:
        print(f"Erreur de formatage de date: {e}")
        return str(date_string)[:10]

def format_datetime(date_string):
    """Convertit une date au format DD-MM-YYYY HH:MM"""
    if not date_string:
        return ""
    
    try:
        # Essayer différents formats de date
        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d-%m-%Y %H:%M:%S']:
            try:
                dt = datetime.strptime(str(date_string)[:19], fmt)
                return dt.strftime('%d-%m-%Y %H:%M')
            except ValueError:
                continue
        
        return str(date_string)[:16]
    except Exception as e:
        print(f"Erreur de formatage de datetime: {e}")
        return str(date_string)[:16]

# Ajouter les filtres Jinja2
app.jinja_env.filters['format_date'] = format_date
app.jinja_env.filters['format_datetime'] = format_datetime

def migrate_database_schema(conn):
    """Migre l'ancienne structure de base de données vers la nouvelle"""
    try:
        print("🔄 Début de la migration de la base de données...")
        cursor = conn.cursor()
        
        # 1. Créer une sauvegarde des données existantes
        cursor.execute("SELECT * FROM exercises")
        old_exercises = cursor.fetchall()
        print(f"📊 {len(old_exercises)} exercices à migrer")
        
        # 2. Créer la nouvelle table exercises temporaire
        cursor.execute('''
            CREATE TABLE exercises_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                exercise_name TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
            )
        ''')
        
        # 3. Créer la table sets si elle n'existe pas
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
        
        # 4. Migrer les données vers la nouvelle structure
        for old_exercise in old_exercises:
            # old_exercise: (id, session_id, exercise_name, sets, reps, weight)
            old_id, session_id, exercise_name, sets_count, reps, weight = old_exercise
            
            # Créer le nouvel exercice (sans sets, reps, weight)
            cursor.execute('''
                INSERT INTO exercises_new (session_id, exercise_name) 
                VALUES (?, ?)
            ''', (session_id, exercise_name))
            
            new_exercise_id = cursor.lastrowid
            
            # Créer les séries individuelles
            if sets_count and reps and weight:
                for set_num in range(1, int(sets_count) + 1):
                    cursor.execute('''
                        INSERT INTO sets (exercise_id, set_number, reps, weight)
                        VALUES (?, ?, ?, ?)
                    ''', (new_exercise_id, set_num, int(reps), float(weight)))
        
        # 5. Remplacer l'ancienne table par la nouvelle
        cursor.execute("DROP TABLE exercises")
        cursor.execute("ALTER TABLE exercises_new RENAME TO exercises")
        
        conn.commit()
        print("✅ Migration terminée avec succès")
        
    except Exception as e:
        print(f"❌ Erreur durant la migration: {e}")
        conn.rollback()
        raise

def init_db():
    """Initialise la base de données avec gestion d'erreur"""
    try:
        with sqlite3.connect('database.db') as conn:
            # Vérifier si migration est nécessaire (ancienne structure avec sets dans exercises)
            cursor = conn.cursor()
            try:
                cursor.execute("PRAGMA table_info(exercises)")
                columns = [col[1] for col in cursor.fetchall()]
                if 'sets' in columns or 'reps' in columns or 'weight' in columns:
                    print("🔄 Migration de la base de données détectée...")
                    migrate_database_schema(conn)
            except sqlite3.OperationalError:
                # Table n'existe pas encore, c'est normal
                pass
            
            # Table pour les séances
            conn.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Table pour les exercices dans chaque séance (sans sets, reps, weight)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS exercises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    exercise_name TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
                )
            ''')
            
            # Table pour les séries individuelles
            conn.execute('''
                CREATE TABLE IF NOT EXISTS sets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exercise_id INTEGER NOT NULL,
                    set_number INTEGER NOT NULL,
                    reps INTEGER NOT NULL,
                    weight REAL NOT NULL,
                    FOREIGN KEY (exercise_id) REFERENCES exercises (id) ON DELETE CASCADE
                )
            ''')
            
            # Table pour les programmes d'entraînement
            conn.execute('''
                CREATE TABLE IF NOT EXISTS programmes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nom TEXT NOT NULL,
                    description TEXT,
                    actif INTEGER DEFAULT 0,
                    archive INTEGER DEFAULT 0,
                    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Table pour les séances d'un programme
            conn.execute('''
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
            
            # Table pour les exercices des séances de programme
            conn.execute('''
                CREATE TABLE IF NOT EXISTS programme_exercices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    seance_id INTEGER NOT NULL,
                    ordre INTEGER NOT NULL,
                    nom_exercice TEXT NOT NULL,
                    series INTEGER,
                    repetitions TEXT,
                    notes TEXT,
                    FOREIGN KEY (seance_id) REFERENCES programme_seances (id) ON DELETE CASCADE
                )
            ''')
            
            conn.commit()
            print("✅ Base de données initialisée avec succès")
            
    except sqlite3.Error as e:
        print(f"❌ Erreur lors de l'initialisation de la base de données: {e}")
    except Exception as e:
        print(f"❌ Erreur inattendue lors de l'initialisation: {e}")

@app.route('/')
def home():
    """Page d'accueil - affiche les séances disponibles"""
    sessions = []
    
    try:
        with sqlite3.connect('database.db') as conn:
            cur = conn.cursor()
            # Récupérer toutes les séances distinctes avec le nombre de jours depuis la dernière
            cur.execute("""
                SELECT 
                    name,
                    MAX(date) as last_date,
                    CAST((julianday('now') - julianday(MAX(date))) AS INTEGER) as days_since
                FROM sessions
                WHERE name IS NOT NULL AND name != ''
                GROUP BY name
                ORDER BY last_date DESC
            """)
            sessions = cur.fetchall()
    except sqlite3.Error as e:
        print(f"❌ Erreur lors de la récupération des séances: {e}")
    except Exception as e:
        print(f"❌ Erreur inattendue: {e}")
    
    return render_template('index.html', sessions=sessions)

@app.route('/ai', methods=['GET', 'POST'])
def ai_coach():
    """Génération de programmes d'entraînement avec l'IA"""
    training_program = None
    training_program_html = None
    if request.method == 'POST':
        user_prompt = request.form['prompt']
        
        # 📊 RÉCUPÉRER L'HISTORIQUE DES ENTRAÎNEMENTS
        history_context = "\n## 📊 HISTORIQUE DES ENTRAÎNEMENTS\n\n"
        
        try:
            with sqlite3.connect('database.db') as conn:
                cur = conn.cursor()
                
                # Récupérer les séances distinctes avec dates
                cur.execute("""
                    SELECT DISTINCT name, 
                           MAX(date) as last_date,
                           COUNT(*) as session_count,
                           CAST((julianday('now') - julianday(MAX(date))) AS INTEGER) as days_since
                    FROM sessions
                    WHERE name IS NOT NULL AND name != ''
                    GROUP BY name
                    ORDER BY last_date DESC
                    LIMIT 10
                """)
                sessions = cur.fetchall()
                
                # Récupérer les exercices récents avec leurs performances
                cur.execute("""
                    SELECT e.exercise_name, 
                           s.name as session_name,
                           s.date,
                           GROUP_CONCAT(st.set_number || 'x' || st.reps || '@' || st.weight, ', ') as sets_detail
                    FROM exercises e
                    JOIN sessions s ON e.session_id = s.id
                    LEFT JOIN sets st ON e.id = st.exercise_id
                    GROUP BY e.id, e.exercise_name, s.name, s.date
                    ORDER BY s.date DESC
                    LIMIT 30
                """)
                recent_exercises = cur.fetchall()
                
                # Calculer les statistiques par exercice
                exercise_stats = {}
                
                # Récupérer tous les sets pour calculer les max
                cur.execute("""
                    SELECT e.exercise_name, st.reps, st.weight
                    FROM exercises e
                    JOIN sets st ON e.id = st.exercise_id
                    ORDER BY e.exercise_name
                """)
                all_sets = cur.fetchall()
                
                for exercise_name, reps, weight in all_sets:
                    if exercise_name not in exercise_stats:
                        exercise_stats[exercise_name] = {
                            'max_weight': weight,
                            'max_1rm': calculate_1rm(weight, reps),
                            'occurrences': 1,
                            'last_reps': reps,
                            'last_weight': weight
                        }
                    else:
                        stats = exercise_stats[exercise_name]
                        if weight > stats['max_weight']:
                            stats['max_weight'] = weight
                        
                        current_1rm = calculate_1rm(weight, reps)
                        if current_1rm > stats['max_1rm']:
                            stats['max_1rm'] = current_1rm
                        
                        stats['occurrences'] += 1
                        stats['last_reps'] = reps
                        stats['last_weight'] = weight
                
                # Construire le contexte d'historique
                if sessions:
                    history_context += "**Types de séances réalisées :**\n"
                    for session in sessions:
                        days_text = "aujourd'hui" if session[3] == 0 else f"il y a {session[3]} jour{'s' if session[3] > 1 else ''}"
                        history_context += f"- {session[0]} : {session[2]} fois (dernière: {days_text})\n"
                    
                    history_context += "\n**Exercices pratiqués (avec charges maximales) :**\n"
                    for exercise, stats in sorted(exercise_stats.items(), key=lambda x: x[1]['max_1rm'], reverse=True)[:15]:
                        history_context += f"- {exercise} : dernière série {stats['last_reps']} reps @ {stats['last_weight']} kg (max 1RM: {stats['max_1rm']:.1f} kg) - {stats['occurrences']} séries au total\n"
                    
                    history_context += f"\n**Total d'exercices différents pratiqués :** {len(exercise_stats)}\n"
                else:
                    history_context += "Aucun historique d'entraînement disponible (première utilisation).\n"
                    
        except sqlite3.Error as e:
            print(f"❌ Erreur lors de la récupération de l'historique: {e}")
            history_context += "Erreur lors de la récupération de l'historique.\n"

        enhanced_prompt = f"""
Tu es un expert en coaching sportif de haut niveau. Ta mission est de créer des programmes d'entraînement personnalisés, cyclés (périodisés) et basés sur la science.

{history_context}

Tu utiliseras les données des entraînements réalisés (historique ci-dessus) pour ajuster les futurs programmes en appliquant le principe de la surcharge progressive.

Principes de Programmation (Ton "Savoir")
Tu dois obligatoirement suivre ces règles scientifiques pour établir le programme :

Gestion de l'Intensité (RIR - Reps In Reserve) :

Toutes les "séries effectives" doivent avoir une cible de RIR (Répétitions en Réserve).

RIR 3 = L'utilisateur aurait pu faire 3 répétitions de plus avant l'échec.

RIR 0 = Échec musculaire.

Objectif Hypertrophie : L'intensité doit se situer entre RIR 0 et RIR 3.

Objectif Force : L'intensité doit se situer entre RIR 1 et RIR 4 (l'échec est évité pour préserver le système nerveux).

La charge (Poids) n'est pas fixe : Elle est le résultat du RIR. Tu indiqueras à l'utilisateur de "Choisir un poids qui permet d'atteindre X reps à RIR Y".

Volume d'Entraînement Hebdomadaire (Priorité N°1) :

Tu dois calculer le volume total de séries effectives par groupe musculaire et par semaine.

Hypertrophie : Cible de 10 à 20 séries.

Force : Cible de 8 à 15 séries.

Tu ajusteras ce volume selon le niveau :
L'utilisateur est intermédiaire/avancé.

Fréquence (Répartition du Volume) :

Tu dois répartir ce volume hebdomadaire sur le nombre de séances fournies.

La fréquence optimale est de stimuler un muscle au moins 2 fois par semaine.

Spécificité (Fourchettes de Répétitions) :

Hypertrophie : Privilégier la fourchette 6 à 15 répétitions.

Force : Privilégier la fourchette 1 à 6 répétitions.

Sélection et Ordre des Exercices :

Priorité 1 (Début de séance) : Exercices poly-articulaires (composés) qui sollicitent le plus de masse (ex: Squat, Soulevé de terre, Développé couché, Tractions, Rowing).

Priorité 2 (Milieu/Fin de séance) : Exercices d'isolation (mono-articulaires) (ex: Curls biceps, Extensions triceps, Élévations latérales).

Tu dois assurer un équilibre agoniste/antagoniste (ex: si tu programmes des Pectoraux/Push, tu dois aussi programmer du Dos/Pull dans la semaine).

Périodisation (La Progression dans le Temps) :

Tu génères les programmes sous forme de "Mésocycle" (un cycle de 4 à 6 semaines).

Principe de Surcharge : Le programme doit se durcir de semaine en semaine. Tu feras cela en diminuant le RIR ou en augmentant le nombre de séries.

Exemple de cycle de 4 semaines (Hypertrophie) :

Semaine 1 : RIR 2-3 (Phase d'accumulation)

Semaine 2 : RIR 1-2

Semaine 3 : RIR 1

Semaine 4 : RIR 0-1 (Phase d'intensification / Overreaching)

Deload (Décharge) : Après chaque mésocycle (après la semaine 4 ou 6), tu dois programmer 1 semaine de "Deload" (environ 50% du volume, et RIR 3-5) pour permettre la récupération et la surcompensation.

Demande de l'utilisateur
L'utilisateur doit OBLIGATOIREMENT fournir les informations suivantes :

Objectif principal (Hypertrophie, Force, Endurance).

Nombre de séances par semaine (Fréquence).

Groupes musculaires à travailler OU le type de "split" souhaité.

(Optionnel) S'il entame un nouveau cycle ou à quelle semaine de son cycle il se trouve.

**DEMANDE UTILISATEUR :**
{user_prompt}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
� FORMAT DE RÉPONSE OBLIGATOIRE - TRÈS IMPORTANT 🚨
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Pour que le programme soit sauvegardé correctement, tu DOIS utiliser ce format EXACT :

ÉTAPE 1 : Écrire le titre de la séance (Garde un titre simple et clair et n'utilise pas le symbole "&")
────────────────────────────────────────
SEANCE 1: Nom de la séance

ÉTAPE 2 : Laisser UNE ligne vide
────────────────────────────────────────
(ligne vide obligatoire)

ÉTAPE 3 : Lister les exercices avec des tirets
────────────────────────────────────────
- Développé couché (Barre) : 4 x 6-8 reps @ RIR 2-3, 2.5 min repos
- Squat (Barre) : 3 x 8-10 reps @ RIR 2-3, 2 min repos

ÉTAPE 4 : Laisser UNE ligne vide
────────────────────────────────────────
(ligne vide obligatoire)

ÉTAPE 5 : Écrire exactement [PARSE_START]
────────────────────────────────────────
[PARSE_START]

ÉTAPE 6 : Copier CHAQUE exercice dans ce format
────────────────────────────────────────
EXERCICE: Développé couché (Barre) | SERIES: 4 | REPS: 6-8 | NOTES: RIR 2-3, repos 2.5 min
EXERCICE: Squat (Barre) | SERIES: 3 | REPS: 8-10 | NOTES: RIR 2-3, repos 2 min

Important pour l'ÉTAPE 6 :
- Le nom DOIT être identique à celui de l'étape 3
- Utilise le symbole | entre chaque partie
- SERIES doit être un nombre (4, pas 4-5)
- REPS peut être une fourchette (6-8) ou un nombre (10)

ÉTAPE 7 : Fermer avec [PARSE_END]
────────────────────────────────────────
[PARSE_END]

ÉTAPE 8 : Répéter pour la séance suivante
────────────────────────────────────────
Recommence à l'ÉTAPE 1 pour chaque nouvelle séance

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXEMPLE COMPLET POUR 2 SÉANCES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SEANCE 1: Push (Pectoraux/Épaules)

- Développé couché (Barre) : 4 x 6-8 reps @ RIR 2-3, 2.5 min repos
- Développé militaire (Haltères) : 3 x 8-10 reps @ RIR 2-3, 2 min repos
- Élévations latérales : 3 x 12-15 reps @ RIR 2-3, 1.5 min repos

[PARSE_START]
EXERCICE: Développé couché (Barre) | SERIES: 4 | REPS: 6-8 | NOTES: RIR 2-3, repos 2.5 min
EXERCICE: Développé militaire (Haltères) | SERIES: 3 | REPS: 8-10 | NOTES: RIR 2-3, repos 2 min
EXERCICE: Élévations latérales | SERIES: 3 | REPS: 12-15 | NOTES: RIR 2-3, repos 1.5 min
[PARSE_END]

SEANCE 2: Pull (Dos/Biceps)

- Tractions : 4 x 8-10 reps @ RIR 2-3, 2 min repos
- Rowing barre : 3 x 8-10 reps @ RIR 2-3, 2 min repos

[PARSE_START]
EXERCICE: Tractions | SERIES: 4 | REPS: 8-10 | NOTES: RIR 2-3, repos 2 min
EXERCICE: Rowing barre | SERIES: 3 | REPS: 8-10 | NOTES: RIR 2-3, repos 2 min
[PARSE_END]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

VÉRIFICATION AVANT D'ENVOYER TA RÉPONSE :
✅ Chaque séance commence par "SEANCE X:"
✅ Une ligne vide après chaque titre
✅ Les exercices commencent par "- "
✅ Une ligne vide avant [PARSE_START]
✅ Chaque exercice a une ligne "EXERCICE: ..." dans le bloc
✅ Chaque bloc se termine par [PARSE_END]

Si tu oublies les blocs [PARSE_START]...[PARSE_END], AUCUN exercice ne sera sauvegardé !

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Gestion des Informations Manquantes
Si l'Objectif, le Nombre de séances ou le Niveau ne sont pas fournis, tu ne dois PAS générer de programme. Tu dois d'abord poser une question claire pour obtenir ces informations. Exemple de question : "Pour créer un programme efficace, j'ai besoin de connaître votre objectif (prise de masse, force...), votre niveau (débutant, intermédiaire, avancé) et combien de fois par semaine vous pouvez vous entraîner."

Format de la réponse
Tu donneras le nom des exercices en FRANCAIS et les temps de repos en MINUTES.
Je veux que tu donnes exactement le même nombre de séances que je demande même si les séances se répètent. Par exemple, si pour un split de 4 jours par semaine, l'utilisateur demande 4 séances, tu dois fournir 4 séances distinctes même si le programme est composé de 2 séances distinctes (A et B).

Si c'est un nouveau programme, tu dois spécifier la durée du cycle. Exemple : "Voici votre programme pour les 5 prochaines semaines (4 semaines d'entrainement et 1 semaine de deload). Commencez la semaine 1 avec les RIR indiqués."

**IMPORTANT : Utilise l'historique fourni pour suggérer des charges appropriées et une progression réaliste.**

Tu n'écriras rien de plus que ce qui est demandé dans ce format (sauf si tu dois poser une question pour informations manquantes).
"""
        
        try:
            model = genai.GenerativeModel('gemini-flash-latest')
            response = model.generate_content(enhanced_prompt)
            training_program = response.text
            
            # Nettoyer le texte : retirer les blocs de parsing pour l'affichage
            import re
            training_program_clean = re.sub(r'\[PARSE_START\].*?\[PARSE_END\]', '', training_program, flags=re.DOTALL)
            
            # Convertir le markdown en HTML
            training_program_html = markdown.markdown(training_program_clean, extensions=['extra', 'codehilite'])
            
        except Exception as e:
            # Programme de secours en cas d'erreur
            training_program = f"""
            ⚠️ **Erreur temporaire avec l'IA**
            """
           
            training_program_html = markdown.markdown(training_program, extensions=['extra', 'codehilite'])
            print(f"Erreur Gemini API: {e}")
            
    return render_template('ai.html', training_program=training_program, training_program_html=training_program_html)

@app.route('/start-session/<session_name>')
def start_session(session_name):
    """Démarrer une nouvelle séance basée sur un template existant"""
    # Récupérer les exercices de la dernière séance avec ce nom
    exercises_with_sets = []
    
    try:
        with sqlite3.connect('database.db') as conn:
            cur = conn.cursor()
            # Trouver la dernière séance avec ce nom
            cur.execute("""
                SELECT id FROM sessions 
                WHERE name = ? 
                ORDER BY date DESC 
                LIMIT 1
            """, (session_name,))
            
            last_session = cur.fetchone()
            
            if last_session:
                session_id = last_session[0]
                # Récupérer les exercices avec leurs séries
                cur.execute("""
                    SELECT e.exercise_name, st.set_number, st.reps, st.weight
                    FROM exercises e
                    LEFT JOIN sets st ON e.id = st.exercise_id
                    WHERE e.session_id = ?
                    ORDER BY e.id, st.set_number
                """, (session_id,))
                
                raw_data = cur.fetchall()
                
                # Regrouper par exercice
                current_exercise = None
                current_sets = []
                
                for row in raw_data:
                    exercise_name, set_number, reps, weight = row
                    
                    if current_exercise != exercise_name:
                        if current_exercise is not None:
                            exercises_with_sets.append({
                                'name': current_exercise,
                                'sets': current_sets
                            })
                        current_exercise = exercise_name
                        current_sets = []
                    
                    if set_number is not None:
                        current_sets.append({
                            'number': set_number,
                            'reps': reps,
                            'weight': weight
                        })
                
                # Ajouter le dernier exercice
                if current_exercise is not None:
                    exercises_with_sets.append({
                        'name': current_exercise,
                        'sets': current_sets
                    })
                
    except sqlite3.Error as e:
        print(f"❌ Erreur lors de la récupération de la séance template: {e}")
    
    # Rediriger vers la page de suivi avec les données pré-remplies
    return render_template('track.html', 
                         session_template_name=session_name, 
                         template_exercises=exercises_with_sets,
                         message=None,
                         recent_sessions=[])

@app.route('/track', methods=['GET', 'POST'])
def track_performance():
    message = None
    recent_sessions = []
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create_session':
            try:
                # Créer une nouvelle séance
                session_name = request.form.get('session_name', 'Séance du ' + str(request.form.get('date', '')))
                
                # Récupérer les données JSON des exercices
                exercises_json = request.form.get('exercises_data')
                
                if not exercises_json:
                    message = "⚠️ Aucune donnée d'exercice reçue."
                else:
                    exercises_data = json.loads(exercises_json)
                    
                    if exercises_data:
                        with sqlite3.connect('database.db') as conn:
                            cur = conn.cursor()
                            
                            # Créer la séance
                            cur.execute("INSERT INTO sessions (name) VALUES (?)", (session_name,))
                            session_id = cur.lastrowid
                            
                            total_exercises = 0
                            total_sets = 0
                            
                            # Ajouter tous les exercices et leurs séries
                            for exercise in exercises_data:
                                exercise_name = exercise.get('name', '').strip()
                                sets = exercise.get('sets', [])
                                
                                if exercise_name and sets:
                                    # Créer l'exercice
                                    cur.execute(
                                        "INSERT INTO exercises (session_id, exercise_name) VALUES (?, ?)",
                                        (session_id, exercise_name)
                                    )
                                    exercise_id = cur.lastrowid
                                    total_exercises += 1
                                    
                                    # Ajouter toutes les séries
                                    for set_data in sets:
                                        set_number = set_data.get('number')
                                        reps = set_data.get('reps')
                                        weight = set_data.get('weight')
                                        
                                        if set_number and reps is not None and weight is not None:
                                            cur.execute(
                                                "INSERT INTO sets (exercise_id, set_number, reps, weight) VALUES (?, ?, ?, ?)",
                                                (exercise_id, set_number, int(reps), float(weight))
                                            )
                                            total_sets += 1
                            
                            conn.commit()
                            message = f"✅ Séance '{session_name}' enregistrée avec {total_exercises} exercice(s) et {total_sets} série(s)!"
                    else:
                        message = "⚠️ Aucun exercice valide trouvé dans la séance."
                    
            except json.JSONDecodeError as e:
                message = f"❌ Erreur de format des données : {str(e)}"
            except (ValueError, TypeError) as e:
                message = f"❌ Erreur dans les données saisies : {str(e)}"
            except sqlite3.Error as e:
                message = f"❌ Erreur de base de données : {str(e)}"
            except Exception as e:
                message = f"❌ Erreur inattendue : {str(e)}"
    
    # Récupérer les 5 dernières séances pour l'historique
    try:
        with sqlite3.connect('database.db') as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT s.id, s.name, s.date, COUNT(DISTINCT e.id) as exercise_count
                FROM sessions s
                LEFT JOIN exercises e ON s.id = e.session_id
                GROUP BY s.id, s.name, s.date
                ORDER BY s.date DESC
                LIMIT 5
            """)
            recent_sessions = cur.fetchall() or []
    except sqlite3.Error as e:
        print(f"Erreur lors de la récupération des séances : {e}")
        # Initialiser la base de données si elle n'existe pas
        init_db()
        recent_sessions = []
    except Exception as e:
        print(f"Erreur inattendue lors de la récupération des séances : {e}")
        recent_sessions = []
        
    return render_template('track.html', message=message, recent_sessions=recent_sessions)

@app.route('/session/<int:session_id>')
def view_session(session_id):
    session = None
    exercises = []
    session_stats = {
        'total_sets': 0,
        'total_volume': 0.0
    }
    
    try:
        with sqlite3.connect('database.db') as conn:
            cur = conn.cursor()
            
            # Récupérer les infos de la séance
            cur.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
            session = cur.fetchone()
            
            if session:
                # Récupérer les exercices avec leurs séries
                cur.execute("""
                    SELECT e.id, e.exercise_name, st.set_number, st.reps, st.weight
                    FROM exercises e
                    LEFT JOIN sets st ON e.id = st.exercise_id
                    WHERE e.session_id = ?
                    ORDER BY e.id, st.set_number
                """, (session_id,))
                
                raw_data = cur.fetchall() or []
                
                # Regrouper les séries par exercice
                exercises_dict = {}
                for row in raw_data:
                    exercise_id, exercise_name, set_number, reps, weight = row
                    
                    if exercise_id not in exercises_dict:
                        exercises_dict[exercise_id] = {
                            'id': exercise_id,
                            'name': exercise_name,
                            'sets': []
                        }
                    
                    if set_number is not None:
                        exercises_dict[exercise_id]['sets'].append({
                            'number': set_number,
                            'reps': reps,
                            'weight': weight
                        })
                        
                        # Calculer les stats
                        session_stats['total_sets'] += 1
                        session_stats['total_volume'] += (reps * weight)
                
                exercises = list(exercises_dict.values())
                            
    except sqlite3.Error as e:
        print(f"Erreur de base de données dans view_session: {e}")
        init_db()
    except Exception as e:
        print(f"Erreur inattendue dans view_session: {e}")
        
    return render_template('session_detail.html', session=session, exercises=exercises, session_stats=session_stats)

@app.route('/progress')
def view_progress():
    exercise_stats = {}
    
    try:
        with sqlite3.connect('database.db') as conn:
            cur = conn.cursor()
            
            # Récupérer toutes les séries de tous les exercices
            cur.execute("""
                SELECT e.exercise_name, st.reps, st.weight, s.date
                FROM exercises e
                JOIN sets st ON e.id = st.exercise_id
                JOIN sessions s ON e.session_id = s.id
                ORDER BY s.date DESC
            """)
            all_sets = cur.fetchall() or []
            
            # Calculer les statistiques par exercice
            for exercise_name, reps, weight, date in all_sets:
                if exercise_name and reps > 0 and weight > 0:
                    current_1rm = calculate_1rm(weight, reps)
                    current_volume = reps * weight
                    
                    if exercise_name not in exercise_stats:
                        exercise_stats[exercise_name] = {
                            'max_weight': weight,
                            'max_1rm': current_1rm,
                            'best_1rm_reps': reps,
                            'best_1rm_weight': weight,
                            'best_volume_reps': reps,
                            'best_volume_weight': weight,
                            'best_volume_total': current_volume,
                            'total_sets': 1,
                            'has_actual_1rm': (reps == 1),
                            'last_date': date
                        }
                    else:
                        stats = exercise_stats[exercise_name]
                        
                        # Mettre à jour le poids max
                        if weight > stats['max_weight']:
                            stats['max_weight'] = weight
                        
                        # Mettre à jour le 1RM (prendre le plus élevé)
                        if current_1rm > stats['max_1rm']:
                            stats['max_1rm'] = current_1rm
                            stats['best_1rm_reps'] = reps
                            stats['best_1rm_weight'] = weight
                            if reps == 1:
                                stats['has_actual_1rm'] = True
                        
                        # Mettre à jour le meilleur volume
                        if current_volume > stats['best_volume_total']:
                            stats['best_volume_reps'] = reps
                            stats['best_volume_weight'] = weight
                            stats['best_volume_total'] = current_volume
                        
                        stats['total_sets'] += 1
            
    except sqlite3.Error as e:
        print(f"Erreur de base de données dans view_progress: {e}")
        init_db()
        exercise_stats = {}
    except Exception as e:
        print(f"Erreur inattendue dans view_progress: {e}")
        exercise_stats = {}
    
    # Trier les exercices par 1RM décroissant
    try:
        sorted_exercises = sorted(exercise_stats.items(), key=lambda x: x[1]['max_1rm'], reverse=True)
    except Exception as e:
        print(f"Erreur lors du tri des exercices : {e}")
        sorted_exercises = []
        
    return render_template('progress.html', 
                         exercise_stats=sorted_exercises,
                         total_exercises=len(exercise_stats))

def calculate_1rm(weight, reps):
    """
    Calcule le 1RM en utilisant la formule d'Epley
    1RM = weight * (1 + reps/30)
    """
    try:
        weight = float(weight) if weight is not None else 0.0
        reps = int(reps) if reps is not None else 1
        
        if weight <= 0 or reps <= 0:
            return 0.0
            
        if reps == 1:
            return weight
        elif reps <= 12:  # Formule fiable jusqu'à 12 reps
            return round(weight * (1 + reps / 30), 1)
        else:  # Pour plus de 12 reps, estimation moins précise
            return round(weight * (1 + reps / 30), 1)
    except (ValueError, TypeError, ZeroDivisionError) as e:
        print(f"Erreur dans calculate_1rm: {e}, weight={weight}, reps={reps}")
        return 0.0

@app.route('/api/exercises')
def get_exercises():
    """API pour récupérer la liste des exercices existants"""
    exercises = set()
    
    try:
        with sqlite3.connect('database.db') as conn:
            cur = conn.cursor()
            
            # Récupérer les exercices distincts
            cur.execute("SELECT DISTINCT exercise_name FROM exercises WHERE exercise_name IS NOT NULL AND exercise_name != ''")
            exercises_data = cur.fetchall()
            for exercise in exercises_data:
                if exercise[0] and exercise[0].strip():
                    exercises.add(exercise[0].strip())
                
    except sqlite3.Error as e:
        print(f"Erreur de base de données dans get_exercises: {e}")
        init_db()
        exercises = set()
    except Exception as e:
        print(f"Erreur inattendue dans get_exercises: {e}")
        exercises = set()
    
    # Convertir en liste triée, filtrer les valeurs vides
    exercises_list = sorted([ex for ex in exercises if ex and ex.strip()])
    return jsonify(exercises_list)

# ============================================
# ROUTES PROGRAMMES
# ============================================

@app.route('/programme')
def programme():
    """Afficher le programme actif et la liste des programmes"""
    programme_actif = None
    seances_programme = []
    tous_programmes = []
    progression = {'completees': 0, 'total': 0, 'pourcentage': 0}
    
    try:
        with sqlite3.connect('database.db') as conn:
            cur = conn.cursor()
            
            # Récupérer le programme actif
            cur.execute("SELECT * FROM programmes WHERE actif = 1 AND archive = 0 LIMIT 1")
            programme_actif = cur.fetchone()
            
            if programme_actif:
                programme_id = programme_actif[0]
                
                # Récupérer les séances du programme actif
                cur.execute("""
                    SELECT * FROM programme_seances 
                    WHERE programme_id = ? 
                    ORDER BY ordre
                """, (programme_id,))
                seances_programme = cur.fetchall()
                
                # Calculer la progression
                if seances_programme:
                    progression['total'] = len(seances_programme)
                    progression['completees'] = sum(1 for s in seances_programme if s[5] == 1)
                    progression['pourcentage'] = int((progression['completees'] / progression['total']) * 100)
            
            # Récupérer tous les programmes non archivés
            cur.execute("SELECT * FROM programmes WHERE archive = 0 ORDER BY actif DESC, date_creation DESC")
            tous_programmes = cur.fetchall()
            
    except sqlite3.Error as e:
        print(f"❌ Erreur lors de la récupération des programmes: {e}")
    
    return render_template('programme.html', 
                         programme_actif=programme_actif,
                         seances_programme=seances_programme,
                         tous_programmes=tous_programmes,
                         progression=progression)

@app.route('/programme/create', methods=['GET', 'POST'])
def programme_create():
    """Créer un nouveau programme"""
    message = None
    
    if request.method == 'POST':
        try:
            nom = request.form.get('nom', '').strip()
            seances_json = request.form.get('seances_data')
            
            if not nom:
                message = "⚠️ Le nom du programme est obligatoire."
            elif not seances_json:
                message = "⚠️ Ajoutez au moins une séance au programme."
            else:
                seances = json.loads(seances_json)
                
                if seances:
                    with sqlite3.connect('database.db') as conn:
                        cur = conn.cursor()
                        
                        # Créer le programme
                        cur.execute("INSERT INTO programmes (nom) VALUES (?)", (nom,))
                        programme_id = cur.lastrowid
                        
                        # Ajouter les séances
                        for seance in seances:
                            cur.execute("""
                                INSERT INTO programme_seances (programme_id, ordre, nom_seance)
                                VALUES (?, ?, ?)
                            """, (programme_id, seance['ordre'], seance['nom']))
                        
                        conn.commit()
                        message = f"✅ Programme '{nom}' créé avec {len(seances)} séance(s)!"
                        
                        # Rediriger vers la page des programmes
                        return redirect('/programme')
                else:
                    message = "⚠️ Ajoutez au moins une séance au programme."
                    
        except json.JSONDecodeError as e:
            message = f"❌ Erreur de format des données: {e}"
        except sqlite3.Error as e:
            message = f"❌ Erreur de base de données: {e}"
        except Exception as e:
            message = f"❌ Erreur inattendue: {e}"
    
    return render_template('programme_create.html', message=message)

@app.route('/programme/activate/<int:programme_id>')
def programme_activate(programme_id):
    """Activer un programme (désactive les autres)"""
    try:
        with sqlite3.connect('database.db') as conn:
            # Désactiver tous les programmes
            conn.execute("UPDATE programmes SET actif = 0")
            # Activer le programme sélectionné
            conn.execute("UPDATE programmes SET actif = 1 WHERE id = ?", (programme_id,))
            conn.commit()
    except sqlite3.Error as e:
        print(f"❌ Erreur lors de l'activation du programme: {e}")
    
    return redirect('/programme')

@app.route('/programme/duplicate/<int:programme_id>')
def programme_duplicate(programme_id):
    """Dupliquer un programme"""
    try:
        with sqlite3.connect('database.db') as conn:
            cur = conn.cursor()
            
            # Récupérer le programme original
            cur.execute("SELECT nom, description FROM programmes WHERE id = ?", (programme_id,))
            programme = cur.fetchone()
            
            if programme:
                # Créer la copie
                nouveau_nom = f"{programme[0]} (Copie)"
                nouvelle_description = programme[1] if programme[1] else None
                cur.execute("INSERT INTO programmes (nom, description) VALUES (?, ?)", (nouveau_nom, nouvelle_description))
                nouveau_programme_id = cur.lastrowid
                
                # Copier les séances
                cur.execute("""
                    SELECT id, ordre, nom_seance, description
                    FROM programme_seances 
                    WHERE programme_id = ? 
                    ORDER BY ordre
                """, (programme_id,))
                seances = cur.fetchall()
                
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
                    
                    for exercice in exercices:
                        ordre_ex, nom_exercice, series, repetitions, notes = exercice
                        cur.execute("""
                            INSERT INTO programme_exercices (seance_id, ordre, nom_exercice, series, repetitions, notes)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (nouveau_seance_id, ordre_ex, nom_exercice, series, repetitions, notes))
                
                conn.commit()
    except sqlite3.Error as e:
        print(f"❌ Erreur lors de la duplication du programme: {e}")
    
    return redirect('/programme')

@app.route('/programme/archive/<int:programme_id>')
def programme_archive(programme_id):
    """Archiver un programme"""
    try:
        with sqlite3.connect('database.db') as conn:
            conn.execute("UPDATE programmes SET archive = 1, actif = 0 WHERE id = ?", (programme_id,))
            conn.commit()
    except sqlite3.Error as e:
        print(f"❌ Erreur lors de l'archivage du programme: {e}")
    
    return redirect('/programme')

@app.route('/programme/delete/<int:programme_id>')
def programme_delete(programme_id):
    """Supprimer un programme"""
    try:
        with sqlite3.connect('database.db') as conn:
            conn.execute("DELETE FROM programmes WHERE id = ?", (programme_id,))
            conn.commit()
    except sqlite3.Error as e:
        print(f"❌ Erreur lors de la suppression du programme: {e}")
    
    return redirect('/programme')

@app.route('/programme/seance/toggle/<int:seance_id>')
def programme_seance_toggle(seance_id):
    """Marquer une séance comme complétée/non complétée"""
    try:
        with sqlite3.connect('database.db') as conn:
            cur = conn.cursor()
            
            # Récupérer l'état actuel
            cur.execute("SELECT completee FROM programme_seances WHERE id = ?", (seance_id,))
            result = cur.fetchone()
            
            if result:
                nouvelle_valeur = 0 if result[0] == 1 else 1
                date_completion = datetime.now() if nouvelle_valeur == 1 else None
                
                cur.execute("""
                    UPDATE programme_seances 
                    SET completee = ?, date_completion = ? 
                    WHERE id = ?
                """, (nouvelle_valeur, date_completion, seance_id))
                conn.commit()
    except sqlite3.Error as e:
        print(f"❌ Erreur lors de la mise à jour de la séance: {e}")
    
    return redirect('/programme')

@app.route('/programme/start-seance/<int:seance_id>')
def programme_start_seance(seance_id):
    """Démarrer une séance depuis un programme"""
    try:
        with sqlite3.connect('database.db') as conn:
            cur = conn.cursor()
            
            # Récupérer les infos de la séance du programme
            cur.execute("SELECT nom_seance FROM programme_seances WHERE id = ?", (seance_id,))
            seance = cur.fetchone()
            
            print(f"🔍 DEBUG - Séance trouvée: {seance}")
            
            if seance:
                # Nettoyer le nom de la séance (enlever les balises HTML)
                import re
                nom_seance = re.sub('<[^<]+?>', '', seance[0])
                
                print(f"🔍 DEBUG - Nom séance nettoyé: {nom_seance}")
                
                # Récupérer les exercices de cette séance
                cur.execute("""
                    SELECT nom_exercice, series, repetitions, notes
                    FROM programme_exercices
                    WHERE seance_id = ?
                    ORDER BY ordre
                """, (seance_id,))
                exercices_data = cur.fetchall()
                
                print(f"🔍 DEBUG - Exercices trouvés: {len(exercices_data)} exercices")
                print(f"🔍 DEBUG - Données brutes: {exercices_data}")
                
                # Formater les exercices pour le template
                template_exercises = []
                for ex in exercices_data:
                    exercice = {
                        'name': ex[0],
                        'sets': []
                    }
                    
                    # Si on a des séries/reps, créer les sets
                    if ex[1]:  # series
                        nb_series = ex[1]
                        reps = ex[2] if ex[2] else '8-12'  # Valeur par défaut
                        
                        for i in range(nb_series):
                            exercice['sets'].append({
                                'reps': reps,
                                'weight': ''
                            })
                    else:
                        # Si pas de séries définies, ajouter 3 sets par défaut
                        for i in range(3):
                            exercice['sets'].append({
                                'reps': '8-12',
                                'weight': ''
                            })
                    
                    template_exercises.append(exercice)
                
                print(f"🔍 DEBUG - Template exercises formatés: {template_exercises}")
                
                # Rediriger vers la page de création de séance avec tout pré-rempli
                return render_template('track.html', 
                                     session_template_name=nom_seance,
                                     template_exercises=template_exercises,
                                     message=None,
                                     recent_sessions=[])
    except sqlite3.Error as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
    
    return redirect('/track')
    return redirect('/track')

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
    import re
    
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
    seances = []
    ordre_seance = 1
    
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
    import re
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
    import re
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

@app.route('/programme/save-from-ai', methods=['POST'])
def programme_save_from_ai():
    """Sauvegarder un programme généré par l'IA avec parsing robuste"""
    try:
        import re
        
        nom = request.form.get('nom', '').strip()
        programme_text = request.form.get('programme_text', '').strip()
        
        if not nom or not programme_text:
            return jsonify({'success': False, 'message': 'Données manquantes'})
        
        # Enlever toutes les balises HTML du texte
        programme_text_clean = re.sub('<[^<]+?>', '', programme_text)
        
        # NOUVEAU PARSER ROBUSTE
        seances, total_exercices, success = parse_programme_ia_robuste(programme_text_clean, nom)
        
        if not seances:
            return jsonify({
                'success': False, 
                'message': '❌ Aucune séance détectée. Vérifiez que le texte contient des lignes "SEANCE X:"'
            })
        
        if total_exercices == 0:
            return jsonify({
                'success': False, 
                'message': '⚠️ Séances détectées mais AUCUN exercice trouvé. Vérifiez le format des exercices.'
            })
        
        # Sauvegarder en base de données
        with sqlite3.connect('database.db') as conn:
            cur = conn.cursor()
            
            # Créer le programme
            cur.execute("INSERT INTO programmes (nom) VALUES (?)", (nom,))
            programme_id = cur.lastrowid
            
            # Ajouter les séances et leurs exercices
            for seance in seances:
                cur.execute("""
                    INSERT INTO programme_seances (programme_id, ordre, nom_seance)
                    VALUES (?, ?, ?)
                """, (programme_id, seance['ordre'], seance['nom']))
                seance_id = cur.lastrowid
                
                # Ajouter les exercices de cette séance
                for exercice in seance.get('exercices', []):
                    cur.execute("""
                        INSERT INTO programme_exercices (seance_id, ordre, nom_exercice, series, repetitions, notes)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (seance_id, exercice['ordre'], exercice['nom'], 
                          exercice.get('series'), exercice.get('repetitions'), exercice.get('notes', '')))
            
            conn.commit()
            
        message_success = f'✅ Programme "{nom}" sauvegardé avec succès!\n'
        message_success += f'📋 {len(seances)} séance(s) créée(s)\n'
        message_success += f'💪 {total_exercices} exercice(s) au total'
        
        return jsonify({'success': True, 'message': message_success})
            
    except Exception as e:
        print(f"\n{'='*80}")
        print(f"❌ ERREUR CRITIQUE LORS DU PARSING")
        print(f"{'='*80}")
        print(f"Type d'erreur: {type(e).__name__}")
        print(f"Message: {str(e)}")
        import traceback
        print(f"\nTraceback complet:")
        traceback.print_exc()
        print(f"{'='*80}\n")
        return jsonify({'success': False, 'message': f'❌ Erreur: {str(e)}'})

@app.route('/manifest.json')

@app.route('/manifest.json')
def manifest():
    return app.send_static_file('manifest.json')

@app.route('/sw.js')
def service_worker():
    response = app.send_static_file('sw.js')
    response.headers['Content-Type'] = 'application/javascript'
    response.headers['Service-Worker-Allowed'] = '/'
    return response

if __name__ == '__main__':  
    init_db()
    app.run(debug=True)
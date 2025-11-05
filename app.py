import os
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
from dotenv import load_dotenv
import sqlite3
import markdown
import json
from datetime import datetime

load_dotenv() # Load environment variables from .env

app = Flask(__name__)

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

def init_db():
    """Initialise la base de données avec gestion d'erreur"""
    try:
        with sqlite3.connect('database.db') as conn:
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

Gestion des Informations Manquantes
Si l'Objectif, le Nombre de séances ou le Niveau ne sont pas fournis, tu ne dois PAS générer de programme. Tu dois d'abord poser une question claire pour obtenir ces informations. Exemple de question : "Pour créer un programme efficace, j'ai besoin de connaître votre objectif (prise de masse, force...), votre niveau (débutant, intermédiaire, avancé) et combien de fois par semaine vous pouvez vous entraîner."

Format de la réponse
Tu donneras le nom des exercices en FRANCAIS et les temps de repos en MINUTES.
Tu fourniras pour chaque exercice que tu recommandes :

Le NOM de l'exercice

Le nombre de SÉRIES

Le nombre de RÉPÉTITIONS

L'INTENSITÉ (cible RIR)

Le temps de repos entre les séries

Tu rédigeras de la façon suivante (note le changement de "POIDS" pour "RIR") : NOM : SÉRIE X RÉPÉTITIONS @ RIR X, REPOS Exemple : Développé couché : 4 x 8-10 reps @ RIR 2, 2-3 min repos

Si c'est un nouveau programme, tu dois spécifier la durée du cycle. Exemple : "Voici votre programme pour les 5 prochaines semaines (4 semaines d'entrainement et 1 semaine de deload). Commencez la semaine 1 avec les RIR indiqués."

**IMPORTANT : Utilise l'historique fourni pour suggérer des charges appropriées et une progression réaliste.**

Tu n'écriras rien de plus que ce qui est demandé dans ce format (sauf si tu dois poser une question pour informations manquantes).
"""
        
        try:
            model = genai.GenerativeModel('gemini-flash-latest')
            response = model.generate_content(enhanced_prompt)
            training_program = response.text
            
            # Convertir le markdown en HTML
            training_program_html = markdown.markdown(training_program, extensions=['extra', 'codehilite'])
            
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
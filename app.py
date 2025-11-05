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
                    name TEXT,
                    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Table pour les exercices dans chaque séance
            conn.execute('''
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
            conn.execute('''
                CREATE TABLE IF NOT EXISTS performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exercise TEXT NOT NULL,
                    sets INTEGER NOT NULL,
                    reps INTEGER NOT NULL,
                    weight REAL NOT NULL,
                    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
                           e.sets, 
                           e.reps, 
                           e.weight,
                           s.name as session_name,
                           s.date
                    FROM exercises e
                    JOIN sessions s ON e.session_id = s.id
                    ORDER BY s.date DESC
                    LIMIT 30
                """)
                recent_exercises = cur.fetchall()
                
                # Calculer les statistiques par exercice
                exercise_stats = {}
                for ex in recent_exercises:
                    exercise_name = ex[0]
                    if exercise_name not in exercise_stats:
                        exercise_stats[exercise_name] = {
                            'max_weight': ex[3],
                            'last_sets': ex[1],
                            'last_reps': ex[2],
                            'occurrences': 1
                        }
                    else:
                        exercise_stats[exercise_name]['max_weight'] = max(
                            exercise_stats[exercise_name]['max_weight'], 
                            ex[3]
                        )
                        exercise_stats[exercise_name]['occurrences'] += 1
                
                # Construire le contexte d'historique
                if sessions:
                    history_context += "**Types de séances réalisées :**\n"
                    for session in sessions:
                        days_text = "aujourd'hui" if session[3] == 0 else f"il y a {session[3]} jour{'s' if session[3] > 1 else ''}"
                        history_context += f"- {session[0]} : {session[2]} fois (dernière: {days_text})\n"
                    
                    history_context += "\n**Exercices pratiqués (avec charges maximales) :**\n"
                    for exercise, stats in sorted(exercise_stats.items(), key=lambda x: x[1]['max_weight'], reverse=True)[:15]:
                        history_context += f"- {exercise} : {stats['last_sets']}×{stats['last_reps']} @ {stats['max_weight']} kg (max) - {stats['occurrences']} fois\n"
                    
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
    exercises = []
    
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
                # Récupérer les exercices de cette séance
                cur.execute("""
                    SELECT exercise_name, sets, reps, weight 
                    FROM exercises 
                    WHERE session_id = ?
                    ORDER BY id
                """, (session_id,))
                exercises = cur.fetchall()
                
    except sqlite3.Error as e:
        print(f"❌ Erreur lors de la récupération de la séance template: {e}")
    
    # Rediriger vers la page de suivi avec les données pré-remplies
    return render_template('track.html', 
                         session_template_name=session_name, 
                         template_exercises=exercises,
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
                exercises_data = []
                
                # Récupérer tous les exercices de la séance
                exercise_count = int(request.form.get('exercise_count', 0))
                for i in range(exercise_count):
                    exercise_name = request.form.get(f'exercise_name_{i}')
                    sets = request.form.get(f'sets_{i}')
                    reps = request.form.get(f'reps_{i}')
                    weight = request.form.get(f'weight_{i}')
                    
                    if exercise_name and sets and reps and weight:
                        exercises_data.append({
                            'name': exercise_name.strip(),
                            'sets': int(sets),
                            'reps': int(reps),
                            'weight': float(weight)
                        })
                
                if exercises_data:
                    with sqlite3.connect('database.db') as conn:
                        # Créer la séance
                        cur = conn.cursor()
                        cur.execute("INSERT INTO sessions (name) VALUES (?)", (session_name,))
                        session_id = cur.lastrowid
                        
                        # Ajouter tous les exercices
                        for exercise in exercises_data:
                            conn.execute(
                                "INSERT INTO exercises (session_id, exercise_name, sets, reps, weight) VALUES (?, ?, ?, ?, ?)",
                                (session_id, exercise['name'], exercise['sets'], exercise['reps'], exercise['weight'])
                            )
                        
                    message = f"✅ Séance '{session_name}' enregistrée avec {len(exercises_data)} exercice(s)!"
                else:
                    message = "⚠️ Aucun exercice valide trouvé dans la séance."
                    
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
                SELECT s.id, s.name, s.date, COUNT(e.id) as exercise_count
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
                # Récupérer les exercices de la séance
                cur.execute("SELECT * FROM exercises WHERE session_id = ?", (session_id,))
                exercises = cur.fetchall() or []
                
                # Calculer les statistiques de la séance
                if exercises:
                    for exercise in exercises:
                        try:
                            # exercise = [id, session_id, exercise_name, sets, reps, weight]
                            sets = exercise[3] if exercise[3] is not None else 0
                            reps = exercise[4] if exercise[4] is not None else 0
                            weight = exercise[5] if exercise[5] is not None else 0.0
                            
                            session_stats['total_sets'] += sets
                            session_stats['total_volume'] += (sets * reps * weight)
                        except (IndexError, TypeError) as e:
                            print(f"Erreur lors du calcul des stats pour l'exercice {exercise}: {e}")
                            continue
                            
    except sqlite3.Error as e:
        print(f"Erreur de base de données dans view_session: {e}")
        # Initialiser la base de données si elle n'existe pas
        init_db()
    except Exception as e:
        print(f"Erreur inattendue dans view_session: {e}")
        
    return render_template('session_detail.html', session=session, exercises=exercises, session_stats=session_stats)

@app.route('/progress')
def view_progress():
    old_entries = []
    new_entries = []
    exercise_stats = {}
    
    try:
        with sqlite3.connect('database.db') as conn:
            cur = conn.cursor()
            
            # Récupérer toutes les performances de l'ancienne table
            try:
                cur.execute("SELECT * FROM performance ORDER BY date DESC")
                old_entries = cur.fetchall() or []
            except sqlite3.OperationalError:
                # Table performance n'existe pas encore
                old_entries = []
            
            # Récupérer toutes les performances des nouvelles séances
            try:
                cur.execute("""
                    SELECT e.exercise_name, e.sets, e.reps, e.weight, s.date, s.name
                    FROM exercises e
                    JOIN sessions s ON e.session_id = s.id
                    ORDER BY s.date DESC
                """)
                new_entries = cur.fetchall() or []
            except sqlite3.OperationalError:
                # Tables exercises/sessions n'existent pas encore
                new_entries = []
            
    except sqlite3.Error as e:
        print(f"Erreur de base de données dans view_progress: {e}")
        # Initialiser la base de données si elle n'existe pas
        init_db()
        old_entries = []
        new_entries = []
    except Exception as e:
        print(f"Erreur inattendue dans view_progress: {e}")
        old_entries = []
        new_entries = []
    
    # Calculer les statistiques par exercice
    try:
        # Traiter les anciennes entrées
        for entry in old_entries:
            if len(entry) >= 5:
                exercise_name = entry[1] if entry[1] else "Exercice inconnu"
                sets = entry[2] if entry[2] is not None else 0
                reps = entry[3] if entry[3] is not None else 0
                weight = entry[4] if entry[4] is not None else 0.0
                
                if exercise_name and sets > 0 and reps > 0 and weight > 0:
                    if exercise_name not in exercise_stats:
                        exercise_stats[exercise_name] = {
                            'max_weight': weight,
                            'max_1rm': calculate_1rm(weight, reps),
                            'best_volume_sets': sets,
                            'best_volume_reps': reps,
                            'best_volume_weight': weight,
                            'best_volume_total': sets * reps * weight,
                            'total_sessions': 1,
                            'has_actual_1rm': (reps == 1)
                        }
                    else:
                        stats = exercise_stats[exercise_name]
                        
                        # Mettre à jour le poids max
                        if weight > stats['max_weight']:
                            stats['max_weight'] = weight
                        
                        # Mettre à jour le 1RM
                        current_1rm = calculate_1rm(weight, reps)
                        if current_1rm > stats['max_1rm']:
                            stats['max_1rm'] = current_1rm
                            if reps == 1:
                                stats['has_actual_1rm'] = True
                        
                        # Mettre à jour le meilleur volume
                        current_volume = sets * reps * weight
                        if current_volume > stats['best_volume_total']:
                            stats['best_volume_sets'] = sets
                            stats['best_volume_reps'] = reps
                            stats['best_volume_weight'] = weight
                            stats['best_volume_total'] = current_volume
                        
                        stats['total_sessions'] += 1
        
        # Traiter les nouvelles entrées (exercices dans les séances)
        for entry in new_entries:
            if len(entry) >= 4:
                exercise_name = entry[0] if entry[0] else "Exercice inconnu"
                sets = entry[1] if entry[1] is not None else 0
                reps = entry[2] if entry[2] is not None else 0
                weight = entry[3] if entry[3] is not None else 0.0
                
                if exercise_name and sets > 0 and reps > 0 and weight > 0:
                    if exercise_name not in exercise_stats:
                        exercise_stats[exercise_name] = {
                            'max_weight': weight,
                            'max_1rm': calculate_1rm(weight, reps),
                            'best_volume_sets': sets,
                            'best_volume_reps': reps,
                            'best_volume_weight': weight,
                            'best_volume_total': sets * reps * weight,
                            'total_sessions': 1,
                            'has_actual_1rm': (reps == 1)
                        }
                    else:
                        stats = exercise_stats[exercise_name]
                        
                        # Mettre à jour le poids max
                        if weight > stats['max_weight']:
                            stats['max_weight'] = weight
                        
                        # Mettre à jour le 1RM
                        current_1rm = calculate_1rm(weight, reps)
                        if current_1rm > stats['max_1rm']:
                            stats['max_1rm'] = current_1rm
                            if reps == 1:
                                stats['has_actual_1rm'] = True
                        
                        # Mettre à jour le meilleur volume
                        current_volume = sets * reps * weight
                        if current_volume > stats['best_volume_total']:
                            stats['best_volume_sets'] = sets
                            stats['best_volume_reps'] = reps
                            stats['best_volume_weight'] = weight
                            stats['best_volume_total'] = current_volume
                        
                        stats['total_sessions'] += 1
        
    except Exception as e:
        print(f"Erreur lors du calcul des statistiques : {e}")
        exercise_stats = {}
    
    # Trier les exercices par 1RM décroissant
    try:
        sorted_exercises = sorted(exercise_stats.items(), key=lambda x: x[1]['max_1rm'], reverse=True)
    except Exception as e:
        print(f"Erreur lors du tri des exercices : {e}")
        sorted_exercises = []
        
    return render_template('progress.html', 
                         entries=old_entries, 
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
            
            # Récupérer les exercices de l'ancienne table
            try:
                cur.execute("SELECT DISTINCT exercise FROM performance WHERE exercise IS NOT NULL AND exercise != ''")
                old_exercises = cur.fetchall()
                for exercise in old_exercises:
                    if exercise[0] and exercise[0].strip():
                        exercises.add(exercise[0].strip())
            except sqlite3.OperationalError:
                # Table performance n'existe pas encore
                pass
            
            # Récupérer les exercices des nouvelles séances
            try:
                cur.execute("SELECT DISTINCT exercise_name FROM exercises WHERE exercise_name IS NOT NULL AND exercise_name != ''")
                new_exercises = cur.fetchall()
                for exercise in new_exercises:
                    if exercise[0] and exercise[0].strip():
                        exercises.add(exercise[0].strip())
            except sqlite3.OperationalError:
                # Table exercises n'existe pas encore
                pass
                
    except sqlite3.Error as e:
        print(f"Erreur de base de données dans get_exercises: {e}")
        # Initialiser la base de données si elle n'existe pas
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
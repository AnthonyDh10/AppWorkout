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
            # Récupérer toutes les séances distinctes avec leur date la plus récente
            cur.execute("""
                SELECT 
                    name,
                    MAX(date) as last_date,
                    COUNT(*) as session_count
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
        
        # Prompt amélioré en français avec formatage markdown
        enhanced_prompt = f"""
        Tu es un coach sportif professionnel expérimenté. Crée un programme d'entraînement personnalisé et détaillé pour cette demande:
        
        **DEMANDE CLIENT:** "{user_prompt}"
        
        Le programme doit inclure:
        
        ## 🎯 ANALYSE DES OBJECTIFS
        - Interpréter les objectifs du client
        - Niveau estimé (débutant/intermédiaire/avancé)
        
        ## 📅 PLANIFICATION
        - Fréquence d'entraînement optimale
        - Durée des séances
        - Périodisation suggérée
        
        ## 🏋️ EXERCICES DÉTAILLÉS
        - Liste d'exercices spécifiques et adaptés
        - Séries, répétitions, temps de repos
        - Alternatives pour différents niveaux
        - Progression sur 4-6 semaines
        
        ## 💡 CONSEILS PRATIQUES
        - Technique et sécurité
        - Récupération et nutrition
        - Motivation et régularité
        
        ## 📊 SUIVI ET ÉVALUATION
        - Indicateurs de progrès à surveiller
        - Ajustements recommandés
        
        **Format:** Utilise la syntaxe Markdown avec des titres, listes, et formatage pour une présentation claire.
        **Langue:** Français
        **Ton:** Motivant et professionnel
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
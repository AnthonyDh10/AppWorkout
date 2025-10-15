import os
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
from dotenv import load_dotenv
import sqlite3
import markdown
import json

load_dotenv() # Load environment variables from .env

app = Flask(__name__)

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def init_db():
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

@app.route('/', methods=['GET', 'POST'])
def home():
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
            
    return render_template('index.html', training_program=training_program, training_program_html=training_program_html)

@app.route('/track', methods=['GET', 'POST'])
def track_performance():
    message = None
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create_session':
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
                        'name': exercise_name,
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
    
    # Récupérer les 5 dernières séances pour l'historique
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
        recent_sessions = cur.fetchall()
        
    return render_template('track.html', message=message, recent_sessions=recent_sessions)

@app.route('/session/<int:session_id>')
def view_session(session_id):
    with sqlite3.connect('database.db') as conn:
        cur = conn.cursor()
        # Récupérer les infos de la séance
        cur.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        session = cur.fetchone()
        
        # Récupérer les exercices de la séance
        cur.execute("SELECT * FROM exercises WHERE session_id = ?", (session_id,))
        exercises = cur.fetchall()
        
    return render_template('session_detail.html', session=session, exercises=exercises)

@app.route('/progress')
def view_progress():
    with sqlite3.connect('database.db') as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM performance ORDER BY date DESC")
        entries = cur.fetchall()
    return render_template('progress.html', entries=entries)

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
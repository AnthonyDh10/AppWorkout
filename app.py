import os
from flask import Flask, render_template, request
import google.generativeai as genai
from dotenv import load_dotenv
import sqlite3
import markdown

load_dotenv() # Load environment variables from .env

app = Flask(__name__)

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def init_db():
    with sqlite3.connect('database.db') as conn:
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
    if request.method == 'POST':
        exercise = request.form['exercise']
        sets = request.form['sets']
        reps = request.form['reps']
        weight = request.form['weight']
        with sqlite3.connect('database.db') as conn:
            conn.execute("INSERT INTO performance (exercise, sets, reps, weight) VALUES (?, ?, ?, ?)",
                         (exercise, sets, reps, weight))
    return render_template('track.html')

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
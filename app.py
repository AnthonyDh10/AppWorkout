import os
from flask import Flask, render_template, request
import google.generativeai as genai
from dotenv import load_dotenv
import sqlite3

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
    if request.method == 'POST':
        user_prompt = request.form['prompt']
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(f"Create a personalized training program for: {user_prompt}")
        training_program = response.text
    return render_template('index.html', training_program=training_program)

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

if __name__ == '__main__':  
    init_db()
    app.run(debug=True)
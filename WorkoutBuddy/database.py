import sqlite3
import os
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_name="workouts.db"):
        self.db_name = db_name
        self.init_db()

    def init_db(self):
        """Initialize the database and table if they don't exist."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS workouts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    exercise_name TEXT NOT NULL,
                    weight REAL,
                    reps_completed INTEGER NOT NULL,
                    duration_seconds INTEGER,
                    avg_depth REAL,
                    avg_form_score REAL,
                    most_common_error TEXT
                )
            ''')

            # Backward-compatible migration for existing DBs.
            cursor.execute("PRAGMA table_info(workouts)")
            existing = {row[1] for row in cursor.fetchall()}
            if "avg_depth" not in existing:
                cursor.execute("ALTER TABLE workouts ADD COLUMN avg_depth REAL")
            if "avg_form_score" not in existing:
                cursor.execute("ALTER TABLE workouts ADD COLUMN avg_form_score REAL")
            if "most_common_error" not in existing:
                cursor.execute("ALTER TABLE workouts ADD COLUMN most_common_error TEXT")
            conn.commit()

    def add_workout(
        self,
        exercise_name,
        weight,
        reps_completed,
        duration_seconds=0,
        avg_depth=None,
        avg_form_score=None,
        most_common_error=None,
    ):
        """Add a new completed workout to the database."""
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO workouts (
                    date, exercise_name, weight, reps_completed, duration_seconds,
                    avg_depth, avg_form_score, most_common_error
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                current_date, exercise_name, weight, reps_completed, duration_seconds,
                avg_depth, avg_form_score, most_common_error
            ))
            conn.commit()
            return cursor.lastrowid

    def get_all_workouts(self):
        """Retrieve all workouts sorted by most recent first."""
        with sqlite3.connect(self.db_name) as conn:
            # Setting row_factory to sqlite3.Row allows accessing columns by name
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM workouts ORDER BY id DESC')
            return [dict(row) for row in cursor.fetchall()]

    def delete_workout(self, workout_id):
        """Delete a workout entry by its ID."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM workouts WHERE id = ?', (workout_id,))
            conn.commit()

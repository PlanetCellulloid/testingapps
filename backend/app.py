#!/usr/bin/env python3

from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import datetime
import os
import uuid
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend-backend communication

# Database setup
DATABASE = 'tasks.db'

def init_db():
    """Initialize the database with tasks table"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            completed BOOLEAN DEFAULT FALSE,
            priority TEXT DEFAULT 'medium',
            category TEXT DEFAULT 'general',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # This allows us to access columns by name
    return conn

# Routes

@app.route('/')
def home():
    return jsonify({
        "message": "Task Manager API",
        "version": "1.0.0",
        "endpoints": {
            "GET /api/tasks": "Get all tasks",
            "POST /api/tasks": "Create a new task",
            "GET /api/tasks/<id>": "Get a specific task",
            "PUT /api/tasks/<id>": "Update a task",
            "DELETE /api/tasks/<id>": "Delete a task",
            "GET /api/stats": "Get task statistics"
        }
    })

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    """Get all tasks with optional filtering"""
    conn = get_db_connection()
    
    # Get query parameters
    status = request.args.get('status')  # 'completed', 'pending'
    category = request.args.get('category')
    priority = request.args.get('priority')
    
    query = "SELECT * FROM tasks WHERE 1=1"
    params = []
    
    if status == 'completed':
        query += " AND completed = ?"
        params.append(True)
    elif status == 'pending':
        query += " AND completed = ?"
        params.append(False)
    
    if category:
        query += " AND category = ?"
        params.append(category)
    
    if priority:
        query += " AND priority = ?"
        params.append(priority)
    
    query += " ORDER BY created_at DESC"
    
    tasks = conn.execute(query, params).fetchall()
    conn.close()
    
    return jsonify([dict(task) for task in tasks])

@app.route('/api/tasks', methods=['POST'])
def create_task():
    """Create a new task"""
    data = request.get_json()
    
    if not data or not data.get('title'):
        return jsonify({"error": "Title is required"}), 400
    
    task_id = str(uuid.uuid4())
    title = data.get('title')
    description = data.get('description', '')
    priority = data.get('priority', 'medium')
    category = data.get('category', 'general')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO tasks (id, title, description, priority, category)
        VALUES (?, ?, ?, ?, ?)
    ''', (task_id, title, description, priority, category))
    
    conn.commit()
    
    # Get the created task
    task = cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    conn.close()
    
    return jsonify(dict(task)), 201

@app.route('/api/tasks/<task_id>', methods=['GET'])
def get_task(task_id):
    """Get a specific task"""
    conn = get_db_connection()
    task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    conn.close()
    
    if task is None:
        return jsonify({"error": "Task not found"}), 404
    
    return jsonify(dict(task))

@app.route('/api/tasks/<task_id>', methods=['PUT'])
def update_task(task_id):
    """Update a task"""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if task exists
    task = cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if task is None:
        conn.close()
        return jsonify({"error": "Task not found"}), 404
    
    # Update fields
    title = data.get('title', task['title'])
    description = data.get('description', task['description'])
    completed = data.get('completed', task['completed'])
    priority = data.get('priority', task['priority'])
    category = data.get('category', task['category'])
    
    cursor.execute('''
        UPDATE tasks 
        SET title = ?, description = ?, completed = ?, priority = ?, category = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (title, description, completed, priority, category, task_id))
    
    conn.commit()
    
    # Get updated task
    updated_task = cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    conn.close()
    
    return jsonify(dict(updated_task))

@app.route('/api/tasks/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    """Delete a task"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if task exists
    task = cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if task is None:
        conn.close()
        return jsonify({"error": "Task not found"}), 404
    
    cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()
    
    return jsonify({"message": "Task deleted successfully"})

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get task statistics"""
    conn = get_db_connection()
    
    # Total tasks
    total = conn.execute('SELECT COUNT(*) as count FROM tasks').fetchone()['count']
    
    # Completed tasks
    completed = conn.execute('SELECT COUNT(*) as count FROM tasks WHERE completed = TRUE').fetchone()['count']
    
    # Pending tasks
    pending = total - completed
    
    # Tasks by priority
    priority_stats = conn.execute('''
        SELECT priority, COUNT(*) as count 
        FROM tasks 
        GROUP BY priority
    ''').fetchall()
    
    # Tasks by category
    category_stats = conn.execute('''
        SELECT category, COUNT(*) as count 
        FROM tasks 
        GROUP BY category
    ''').fetchall()
    
    conn.close()
    
    return jsonify({
        "total": total,
        "completed": completed,
        "pending": pending,
        "by_priority": [dict(row) for row in priority_stats],
        "by_category": [dict(row) for row in category_stats]
    })

@app.route('/api/tasks/bulk', methods=['DELETE'])
def delete_completed_tasks():
    """Delete all completed tasks"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM tasks WHERE completed = TRUE')
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    
    return jsonify({"message": f"Deleted {deleted_count} completed tasks"})

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    init_db()
    print("🚀 Task Manager API Server Starting...")
    print("📊 Database initialized")
    
    # Get port from environment variable or use default
    port = int(os.environ.get('PORT', 5001))
    debug = os.environ.get('FLASK_ENV') != 'production'
    
    print(f"🌐 Server running on port {port}")
    print("📋 API Documentation available at /")
    
    app.run(debug=debug, host='0.0.0.0', port=port)

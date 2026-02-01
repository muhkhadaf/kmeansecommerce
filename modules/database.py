import mysql.connector
from mysql.connector import Error
import json
import os
from datetime import datetime, timedelta
import pandas as pd
import bcrypt
from config import Config

def get_db_connection():
    """
    Membuat koneksi ke database MySQL
    """
    try:
        connection = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DATABASE,
            autocommit=True
        )
        return connection
    except Error as e:
        print(f"❌ Error connecting to MySQL: {e}")
        return None

def init_database():
    """
    Inisialisasi database dan membuat tabel jika belum ada
    """
    try:
        # First, connect without specifying database to create it
        connection = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            autocommit=True
        )
        cursor = connection.cursor()
        
        # Create database if not exists
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {Config.MYSQL_DATABASE}")
        cursor.execute(f"USE {Config.MYSQL_DATABASE}")
        
        # Baca dan eksekusi schema.sql jika ada
        schema_file = 'schema.sql'
        if os.path.exists(schema_file):
            with open(schema_file, 'r', encoding='utf-8') as file:
                schema_content = file.read()
            
            # Split dan eksekusi statement
            statements = []
            current_statement = ""
            
            for line in schema_content.split('\n'):
                line = line.strip()
                if line.startswith('--') or not line:
                    continue
                current_statement += line + " "
                if line.endswith(';'):
                    statements.append(current_statement.strip())
                    current_statement = ""
            
            for statement in statements:
                if statement and not statement.startswith('CREATE DATABASE') and not statement.startswith('USE'):
                    try:
                        cursor.execute(statement)
                    except Error as e:
                        print(f"⚠️ Warning: {e}")
        
        connection.close()
        print("✅ MySQL Database initialized successfully")
        return True
        
    except Error as e:
        print(f"❌ Error initializing database: {e}")
        return False

# User Authentication Functions
def create_user(username, email, password):
    """
    Membuat user baru
    """
    try:
        connection = get_db_connection()
        if not connection:
            return False, "Database connection failed"
            
        cursor = connection.cursor()
        
        # Check if username or email already exists
        cursor.execute("SELECT id FROM users WHERE username = %s OR email = %s", (username, email))
        if cursor.fetchone():
            connection.close()
            return False, "Username or email already exists"
        
        # Hash password
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Insert new user
        cursor.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
            (username, email, password_hash)
        )
        
        user_id = cursor.lastrowid
        connection.close()
        return True, user_id
        
    except Error as e:
        print(f"❌ Error creating user: {e}")
        return False, str(e)

def authenticate_user(username, password):
    """
    Autentikasi user
    """
    try:
        connection = get_db_connection()
        if not connection:
            return None
            
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        
        connection.close()
        
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            return user
        return None
        
    except Error as e:
        print(f"❌ Error authenticating user: {e}")
        return None

def get_user_by_id(user_id):
    """
    Mendapatkan user berdasarkan ID
    """
    try:
        connection = get_db_connection()
        if not connection:
            return None
            
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        connection.close()
        return user
        
    except Error as e:
        print(f"❌ Error getting user: {e}")
        return None

def check_username_exists(username):
    """
    Cek apakah username sudah ada
    """
    try:
        connection = get_db_connection()
        if not connection:
            return False
            
        cursor = connection.cursor()
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        result = cursor.fetchone()
        
        connection.close()
        return result is not None
        
    except Error as e:
        print(f"❌ Error checking username: {e}")
        return False

def check_email_exists(email):
    """
    Cek apakah email sudah ada
    """
    try:
        connection = get_db_connection()
        if not connection:
            return False
            
        cursor = connection.cursor()
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        result = cursor.fetchone()
        
        connection.close()
        return result is not None
        
    except Error as e:
        print(f"❌ Error checking email: {e}")
        return False

def update_user_profile(user_id, username, email):
    """
    Update profil user (username dan email)
    """
    try:
        connection = get_db_connection()
        if not connection:
            return False
            
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE users SET username = %s, email = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (username, email, user_id)
        )
        
        success = cursor.rowcount > 0
        connection.close()
        return success
        
    except Error as e:
        print(f"❌ Error updating user profile: {e}")
        return False

def update_user_password(user_id, new_password):
    """
    Update password user
    """
    try:
        connection = get_db_connection()
        if not connection:
            return False
            
        cursor = connection.cursor()
        
        # Hash password baru
        password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        cursor.execute(
            "UPDATE users SET password_hash = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (password_hash, user_id)
        )
        
        success = cursor.rowcount > 0
        connection.close()
        return success
        
    except Error as e:
        print(f"❌ Error updating password: {e}")
        return False

# Clustering Results Functions - Updated for new structure
def save_clustering_result(user_id, session_id, results_data):
    """
    Menyimpan hasil clustering ke database dengan struktur baru
    """
    try:
        connection = get_db_connection()
        if not connection:
            return False
            
        cursor = connection.cursor()
        
        # 1. Insert ke clustering_sessions
        cursor.execute('''
            INSERT INTO clustering_sessions (user_id, session_id, filename)
            VALUES (%s, %s, %s)
        ''', (
            user_id,
            session_id,
            results_data.get('filename', '')
        ))
        
        session_result_id = cursor.lastrowid
        
        # 2. Insert ke clustering_metrics
        cursor.execute('''
            INSERT INTO clustering_metrics (session_result_id, optimal_k, silhouette_score, inertia)
            VALUES (%s, %s, %s, %s)
        ''', (
            session_result_id,
            results_data.get('optimal_k', 0),
            results_data.get('silhouette_score', 0.0),
            results_data.get('inertia', 0.0)
        ))
        
        # 3. Insert ke clustering_plots
        cursor.execute('''
            INSERT INTO clustering_plots (session_result_id, elbow_plot_path, silhouette_plot_path, cluster_plot_path)
            VALUES (%s, %s, %s, %s)
        ''', (
            session_result_id,
            results_data.get('elbow_plot_path', ''),
            results_data.get('silhouette_plot_path', ''),
            results_data.get('cluster_plot_path', '')
        ))
        
        # 4. Prepare dan insert ke clustering_data
        original_data_json = None
        clustered_data_json = None
        cluster_centers_json = None
        
        if 'original_data' in results_data and results_data['original_data'] is not None:
            if isinstance(results_data['original_data'], pd.DataFrame):
                original_data_json = results_data['original_data'].to_json()
            else:
                original_data_json = json.dumps(results_data['original_data'])
        
        if 'clustered_data' in results_data and results_data['clustered_data'] is not None:
            if isinstance(results_data['clustered_data'], pd.DataFrame):
                clustered_data_json = results_data['clustered_data'].to_json()
            else:
                clustered_data_json = json.dumps(results_data['clustered_data'])
        
        if 'cluster_centers' in results_data and results_data['cluster_centers'] is not None:
            cluster_centers_json = json.dumps(results_data['cluster_centers'].tolist() if hasattr(results_data['cluster_centers'], 'tolist') else results_data['cluster_centers'])
        
        cursor.execute('''
            INSERT INTO clustering_data (session_result_id, original_data, clustered_data, cluster_centers)
            VALUES (%s, %s, %s, %s)
        ''', (
            session_result_id,
            original_data_json,
            clustered_data_json,
            cluster_centers_json
        ))
        
        connection.close()
        print(f"✅ Clustering result saved for user {user_id}, session: {session_id}")
        return True
        
    except Error as e:
        print(f"❌ Error saving clustering result: {e}")
        return False

def get_clustering_result(session_id):
    """
    Mengambil hasil clustering berdasarkan session ID dengan struktur baru
    """
    try:
        connection = get_db_connection()
        if not connection:
            return None
            
        cursor = connection.cursor(dictionary=True)
        
        # Join semua tabel untuk mendapatkan data lengkap
        cursor.execute('''
            SELECT 
                cs.id, cs.user_id, cs.session_id, cs.filename, cs.created_at,
                cm.optimal_k, cm.silhouette_score, cm.inertia,
                cp.elbow_plot_path, cp.silhouette_plot_path, cp.cluster_plot_path,
                cd.original_data, cd.clustered_data, cd.cluster_centers
            FROM clustering_sessions cs
            LEFT JOIN clustering_metrics cm ON cs.id = cm.session_result_id
            LEFT JOIN clustering_plots cp ON cs.id = cp.session_result_id
            LEFT JOIN clustering_data cd ON cs.id = cd.session_result_id
            WHERE cs.session_id = %s
        ''', (session_id,))
        
        result = cursor.fetchone()
        connection.close()
        
        if result:
            # Parse JSON data back to Python objects
            if result['original_data']:
                try:
                    result['original_data'] = pd.read_json(result['original_data'])
                except:
                    result['original_data'] = json.loads(result['original_data'])
            
            if result['clustered_data']:
                try:
                    result['clustered_data'] = pd.read_json(result['clustered_data'])
                except:
                    result['clustered_data'] = json.loads(result['clustered_data'])
            
            if result['cluster_centers']:
                result['cluster_centers'] = json.loads(result['cluster_centers'])
        
        return result
        
    except Error as e:
        print(f"❌ Error getting clustering result: {e}")
        return None

def get_user_clustering_results(user_id, limit=10):
    """
    Mengambil riwayat hasil clustering user dengan struktur baru
    """
    try:
        connection = get_db_connection()
        if not connection:
            return []
            
        cursor = connection.cursor(dictionary=True)
        cursor.execute('''
            SELECT 
                cs.id, cs.session_id, cs.filename, cs.created_at,
                cm.optimal_k, cm.silhouette_score, cm.inertia
            FROM clustering_sessions cs
            LEFT JOIN clustering_metrics cm ON cs.id = cm.session_result_id
            WHERE cs.user_id = %s 
            ORDER BY cs.created_at DESC 
            LIMIT %s
        ''', (user_id, limit))
        
        results = cursor.fetchall()
        connection.close()
        return results
        
    except Error as e:
        print(f"❌ Error getting user clustering results: {e}")
        return []

def cleanup_old_results(days=30):
    """
    Membersihkan hasil clustering yang lama dengan struktur baru
    """
    try:
        connection = get_db_connection()
        if not connection:
            return False
            
        cursor = connection.cursor()
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Hapus dari clustering_sessions (akan cascade ke tabel lain)
        cursor.execute("DELETE FROM clustering_sessions WHERE created_at < %s", (cutoff_date,))
        deleted_count = cursor.rowcount
        
        connection.close()
        print(f"✅ Cleaned up {deleted_count} old clustering results")
        return True
        
    except Error as e:
        print(f"❌ Error cleaning up old results: {e}")
        return False
"""
Flask Web Application untuk K-Means Clustering dengan User Authentication
Aplikasi ini memungkinkan user untuk upload file CSV dan melakukan clustering
menggunakan algoritma K-Means dengan preprocessing otomatis dan visualisasi hasil.
"""

import os
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file, make_response
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
import uuid
import threading
import time
import io
import json

# Import modul custom
from modules.preprocessing import preprocess_data, get_data_summary
from modules.clustering import find_optimal_clusters, perform_kmeans_clustering, evaluate_clustering
from modules.visualization import create_elbow_plot, create_cluster_plot, cleanup_old_plots
from modules.database import init_database, save_clustering_result, get_clustering_result, create_user, authenticate_user, get_user_by_id, get_user_clustering_results
from modules.forms import LoginForm, RegistrationForm, User, EcommerceScrapingForm
from modules.insights import generate_clustering_insights
from modules.ecommerce_scraper import scrape_ecommerce_data
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Silakan login untuk mengakses halaman ini.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    user_data = get_user_by_id(int(user_id))
    if user_data:
        return User(user_data)
    return None

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# Konfigurasi upload
UPLOAD_FOLDER = app.config['UPLOAD_FOLDER']
ALLOWED_EXTENSIONS = app.config['ALLOWED_EXTENSIONS']
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB

app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Global variables untuk progress tracking
progress_data = {}
scraping_data = {}

def update_progress(session_id, step, progress, message):
    """Update progress for a specific session"""
    progress_data[session_id] = {
        'step': step,
        'progress': progress,
        'message': message,
        'timestamp': time.time()
    }
    socketio.emit('progress_update', progress_data[session_id], room=session_id)



@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print(f"Client disconnected: {request.sid}")

@socketio.on('join')
def handle_join(data):
    """Handle client joining a room"""
    room = data.get('room') or data.get('session_id')
    join_room(room)
    print(f"Client {request.sid} joined room {room}")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user_data = authenticate_user(form.username.data, form.password.data)
        if user_data:
            user = User(user_data)  # Create User object from dictionary
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            flash('Login berhasil!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Username atau password salah.', 'error')
    
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        success, result = create_user(form.username.data, form.email.data, form.password.data)
        if success:
            flash('Registrasi berhasil! Silakan login.', 'success')
            return redirect(url_for('login'))
        else:
            error_message = result if isinstance(result, str) else 'Registrasi gagal. Silakan coba lagi.'
            flash(error_message, 'error')
    
    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Anda telah logout.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    clustering_results = get_user_clustering_results(current_user.id)
    
    # Calculate statistics
    total_analyses = len(clustering_results)
    avg_silhouette = sum(r['silhouette_score'] for r in clustering_results) / total_analyses if total_analyses > 0 else 0
    avg_optimal_k = sum(r['optimal_k'] for r in clustering_results) / total_analyses if total_analyses > 0 else 0
    
    stats = {
        'total_analyses': total_analyses,
        'avg_silhouette': round(avg_silhouette, 3),
        'avg_optimal_k': round(avg_optimal_k, 1)
    }
    
    return render_template('dashboard.html', clustering_results=clustering_results, stats=stats)

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    """Handle file upload dan mulai proses clustering dengan progress tracking"""
    try:
        # Cek apakah file ada dalam request
        if 'file' not in request.files:
            flash('Tidak ada file yang dipilih', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        
        # Cek apakah file dipilih
        if file.filename == '':
            flash('Tidak ada file yang dipilih', 'error')
            return redirect(request.url)
        
        # Cek apakah file valid
        if file and allowed_file(file.filename):
            # Generate unique filename
            filename = str(uuid.uuid4()) + '_' + secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            # Simpan file
            file.save(filepath)
            
            # Generate unique session ID for each analysis
            session_id = str(uuid.uuid4())
            
            # Start processing in background thread
            thread = threading.Thread(
                target=process_clustering_with_progress,
                args=(filepath, file.filename, session_id, current_user.id)
            )
            thread.daemon = True
            thread.start()
            
            # Return progress page
            return render_template('progress.html', filename=file.filename, session_id=session_id)
        
        else:
            flash('File harus berformat CSV', 'error')
            return redirect(url_for('index'))
    
    except Exception as e:
        print(f"❌ Error umum: {str(e)}")
        flash(f'Terjadi kesalahan: {str(e)}', 'error')
        return redirect(url_for('index'))

def process_clustering_with_progress(filepath, original_filename, session_id, user_id=None):
    """Process clustering with progress updates"""
    try:
        # Step 1: Load data
        update_progress(session_id, "loading", 10, "📂 Memuat file CSV...")
        time.sleep(0.5)
        df = pd.read_csv(filepath)
        
        # Step 2: Preprocessing
        update_progress(session_id, "preprocessing", 20, "🧹 Memulai preprocessing data...")
        time.sleep(0.5)
        
        update_progress(session_id, "preprocessing", 30, f"📊 Menganalisis data dengan shape: {df.shape}")
        processed_data, scaler, preprocessing_info = preprocess_data(
            df,
            progress_callback=lambda step, progress, message: update_progress(session_id, step, progress, message)
        )
        numeric_columns = preprocessing_info.get('numeric_columns', [])
        
        if processed_data is None:
            update_progress(session_id, "error", 0, "❌ Data tidak dapat diproses. Pastikan file CSV memiliki kolom numerik.")
            return
        
        # Step 3: Find optimal clusters
        update_progress(session_id, "clustering", 60, "🔍 Mencari jumlah cluster optimal...")
        time.sleep(0.5)
        optimal_k, elbow_scores, silhouette_scores = find_optimal_clusters(processed_data, progress_callback=lambda step, progress, message: update_progress(session_id, step, progress, message))
        
        # Step 4: Perform K-Means
        update_progress(session_id, "clustering", 75, f"🎯 Melakukan K-Means clustering dengan k={optimal_k}...")
        time.sleep(0.5)
        kmeans_model, cluster_labels, cluster_centers = perform_kmeans_clustering(processed_data, optimal_k, progress_callback=lambda step, progress, message: update_progress(session_id, step, progress, message))
        
        # Step 5: Evaluate results
        update_progress(session_id, "evaluation", 85, "📈 Mengevaluasi hasil clustering...")
        time.sleep(0.5)
        inertia, silhouette_avg, calinski_harabasz, davies_bouldin = evaluate_clustering(processed_data, cluster_labels)
        
        # Step 6: Create visualizations
        update_progress(session_id, "visualization", 90, "📊 Membuat visualisasi...")
        time.sleep(0.5)
        elbow_plot_path = create_elbow_plot(elbow_scores, silhouette_scores, optimal_k, progress_callback=lambda step, progress, message: update_progress(session_id, step, progress, message))
        cluster_plot_path = create_cluster_plot(processed_data, cluster_labels, cluster_centers, progress_callback=lambda step, progress, message: update_progress(session_id, step, progress, message))
        
        # Cleanup old plots
        cleanup_old_plots()
        
        # Step 7: Generate insights
        update_progress(session_id, "generating_insights", 92, "🧠 Menghasilkan insight strategis...")
        
        # Generate dynamic insights
        metrics = {
            'silhouette_score': silhouette_avg,
            'calinski_harabasz': calinski_harabasz,
            'davies_bouldin': davies_bouldin
        }
        
        insights = generate_clustering_insights(processed_data, cluster_labels, optimal_k, metrics)
        
        # Step 8: Prepare results
        update_progress(session_id, "finalizing", 95, "✨ Menyiapkan hasil...")
        time.sleep(0.5)
        
        # Gabungkan data asli dengan hasil cluster hanya pada baris yang dipakai clustering
        clustered_index = processed_data.index
        original_with_clusters = df.loc[clustered_index].copy()
        original_with_clusters['Cluster'] = cluster_labels
        
        # Siapkan data untuk template
        results = {
            'optimal_k': optimal_k,
            'inertia': round(inertia, 4),
            'silhouette_score': round(silhouette_avg, 4),
            'calinski_harabasz': round(calinski_harabasz, 4),
            'davies_bouldin': round(davies_bouldin, 4),
            'data_shape': df.shape,
            'processed_shape': preprocessing_info.get('final_shape'),
            'numeric_columns': numeric_columns,
            'removed_columns': preprocessing_info.get('removed_columns', []),
            'clustered_data': original_with_clusters.to_html(classes='table table-striped table-hover', 
                                                           table_id='results-table', 
                                                           escape=False, 
                                                           max_rows=100),
            'elbow_plot': elbow_plot_path,
            'cluster_plot': cluster_plot_path,
            'filename': original_filename,
            'insights': insights
        }
        
        # Step 9: Save to database
        update_progress(session_id, "saving", 98, "💾 Menyimpan hasil ke database...")
        
        # Prepare data for database storage
        # Convert NumPy data types to Python native types
        import numpy as np
        
        db_data = {
            'filename': original_filename,
            'optimal_k': int(optimal_k) if isinstance(optimal_k, (np.integer, np.int64)) else optimal_k,
            'inertia': float(inertia) if isinstance(inertia, (np.floating, np.float64)) else inertia,
            'silhouette_score': float(silhouette_avg) if isinstance(silhouette_avg, (np.floating, np.float64)) else silhouette_avg,
            'calinski_harabasz': float(calinski_harabasz) if isinstance(calinski_harabasz, (np.floating, np.float64)) else calinski_harabasz,
            'davies_bouldin': float(davies_bouldin) if isinstance(davies_bouldin, (np.floating, np.float64)) else davies_bouldin,
            'elbow_plot_path': elbow_plot_path,
            'cluster_plot_path': cluster_plot_path,
            'cluster_centers': cluster_centers,
            'cluster_labels': cluster_labels,
            'original_data': original_with_clusters,
            'data_summary': {
                'shape': df.shape,
                'numeric_columns': numeric_columns,
                'processed_shape': preprocessing_info.get('final_shape'),
                'removed_columns': preprocessing_info.get('removed_columns', [])
            },
            'elbow_scores': {k: float(v) if isinstance(v, (np.floating, np.float64)) else v for k, v in elbow_scores.items()},
            'silhouette_scores': {k: float(v) if isinstance(v, (np.floating, np.float64)) else v for k, v in silhouette_scores.items()},
            'insights': insights
        }
        
        # Save to database with user_id
        save_success = save_clustering_result(user_id, session_id, db_data)
        if save_success:
            update_progress(session_id, "complete", 100, "✅ Clustering berhasil diselesaikan dan disimpan!")
        else:
            update_progress(session_id, "complete", 100, "✅ Clustering berhasil diselesaikan!")
        
        time.sleep(1)
        
        # Store results in session for retrieval
        progress_data[session_id]['results'] = results
        
        # Emit completion event
        socketio.emit('clustering_complete', {'redirect_url': f'/results/{session_id}'}, room=session_id)
        
        # Schedule cleanup of progress data after 5 minutes to allow result viewing
        def cleanup_progress_data():
            time.sleep(300)  # Wait 5 minutes
            if session_id in progress_data:
                del progress_data[session_id]
                print(f"🧹 Cleaned up progress data for session: {session_id}")
        
        cleanup_thread = threading.Thread(target=cleanup_progress_data)
        cleanup_thread.daemon = True
        cleanup_thread.start()
        
        # Hapus file upload setelah diproses
        os.remove(filepath)
        
    except Exception as e:
        print(f"❌ Error dalam pemrosesan: {str(e)}")
        update_progress(session_id, "error", 0, f"❌ Error: {str(e)}")
        # Hapus file jika ada error
        if os.path.exists(filepath):
            os.remove(filepath)

@app.route('/results/<session_id>')
@login_required
def show_results(session_id):
    """Display clustering results"""
    # Check if processing is still in progress
    if session_id in progress_data:
        current_progress = progress_data[session_id]
        
        # If processing is not complete, redirect back to progress page
        if current_progress.get('progress', 0) < 100 and current_progress.get('step') != 'complete':
            return redirect(url_for('progress_page', session_id=session_id))
        
        # If results are available in memory, use them
        if 'results' in current_progress:
            results = current_progress['results']
            return render_template('result.html', results=results, session_id=session_id)
    
    # Try to get from database
    db_results = get_clustering_result(session_id)
    
    if db_results:
        # Convert database results to template format
        import pandas as pd
        
        # Recreate clustered data HTML
        original_data = db_results.get('original_data')
        if original_data is not None:
            try:
                # Convert back to DataFrame if it's a dict
                if isinstance(original_data, dict):
                    df = pd.DataFrame(original_data)
                else:
                    df = original_data
                
                # Check if DataFrame is not empty
                if not df.empty:
                    clustered_data_html = df.to_html(classes='table table-striped table-hover', 
                                                    table_id='results-table', 
                                                    escape=False, 
                                                    max_rows=100)
                else:
                    clustered_data_html = "<p>No data available</p>"
            except Exception as e:
                print(f"Error converting data to HTML: {e}")
                clustered_data_html = "<p>Error displaying data</p>"
        else:
            clustered_data_html = "<p>No data available</p>"
        
        # Prepare results for template
        results = {
            'optimal_k': db_results.get('optimal_k', 0),
            'inertia': round(db_results.get('inertia', 0), 4),
            'silhouette_score': round(db_results.get('silhouette_score', 0), 4),
            'calinski_harabasz': round(db_results.get('calinski_harabasz', 0), 4),
            'davies_bouldin': round(db_results.get('davies_bouldin', 0), 4),
            'data_shape': db_results.get('data_summary', {}).get('shape', (0, 0)),
            'numeric_columns': db_results.get('data_summary', {}).get('numeric_columns', []),
            'clustered_data': clustered_data_html,
            'elbow_plot': db_results.get('elbow_plot_path', ''),
            'cluster_plot': db_results.get('cluster_plot_path', ''),
            'filename': db_results.get('filename', 'Unknown'),
            'insights': db_results.get('insights', {})
        }
        
        return render_template('result.html', results=results, session_id=session_id)
    
    else:
        flash('Hasil tidak ditemukan atau sudah kedaluwarsa.', 'error')
        return redirect(url_for('index'))

@app.route('/progress/<session_id>')
@login_required
def get_progress(session_id):
    """Get current progress for a session"""
    if session_id in progress_data:
        return jsonify(progress_data[session_id])
    else:
        return jsonify({'step': 'waiting', 'progress': 0, 'message': 'Menunggu...'})

@app.route('/progress_page/<session_id>')
@login_required
def progress_page(session_id):
    """Display progress page for ongoing processing"""
    return render_template('progress.html', session_id=session_id)

@app.route('/user_profile')
@login_required
def user_profile():
    """Halaman kelola profil user"""
    return render_template('user_profile.html')

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    """Update informasi profil user"""
    try:
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        
        # Validasi input
        if not username or len(username) < 3:
            flash('Username harus minimal 3 karakter.', 'error')
            return redirect(url_for('user_profile'))
        
        if not email or '@' not in email:
            flash('Email tidak valid.', 'error')
            return redirect(url_for('user_profile'))
        
        # Import database functions
        from modules.database import update_user_profile, check_username_exists, check_email_exists
        
        # Cek apakah username sudah digunakan user lain
        if username != current_user.username and check_username_exists(username):
            flash('Username sudah digunakan oleh user lain.', 'error')
            return redirect(url_for('user_profile'))
        
        # Cek apakah email sudah digunakan user lain
        if email != current_user.email and check_email_exists(email):
            flash('Email sudah digunakan oleh user lain.', 'error')
            return redirect(url_for('user_profile'))
        
        # Update profil
        if update_user_profile(current_user.id, username, email):
            # Update current_user object
            current_user.username = username
            current_user.email = email
            flash('Profil berhasil diperbarui!', 'success')
        else:
            flash('Gagal memperbarui profil. Silakan coba lagi.', 'error')
            
    except Exception as e:
        print(f"Error updating profile: {e}")
        flash('Terjadi kesalahan saat memperbarui profil.', 'error')
    
    return redirect(url_for('user_profile'))

@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    """Ubah password user"""
    try:
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validasi input
        if not current_password or not new_password or not confirm_password:
            flash('Semua field password harus diisi.', 'error')
            return redirect(url_for('user_profile'))
        
        if len(new_password) < 6:
            flash('Password baru harus minimal 6 karakter.', 'error')
            return redirect(url_for('user_profile'))
        
        if new_password != confirm_password:
            flash('Konfirmasi password tidak cocok.', 'error')
            return redirect(url_for('user_profile'))
        
        # Import database functions
        from modules.database import verify_password, update_user_password
        
        # Verifikasi password saat ini
        if not verify_password(current_user.id, current_password):
            flash('Password saat ini tidak benar.', 'error')
            return redirect(url_for('user_profile'))
        
        # Update password
        if update_user_password(current_user.id, new_password):
            flash('Password berhasil diubah!', 'success')
        else:
            flash('Gagal mengubah password. Silakan coba lagi.', 'error')
            
    except Exception as e:
        print(f"Error changing password: {e}")
        flash('Terjadi kesalahan saat mengubah password.', 'error')
    
    return redirect(url_for('user_profile'))

@app.route('/download_results/<session_id>')
@login_required
def download_results(session_id):
    """Download hasil clustering sebagai file CSV"""
    try:
        # Ambil data hasil clustering dari database
        result_data = get_clustering_result(session_id)
        
        if not result_data:
            flash('Data hasil clustering tidak ditemukan.', 'error')
            return redirect(url_for('dashboard'))
        
        # Pastikan user memiliki akses ke data ini
        if result_data['user_id'] != current_user.id:
            flash('Anda tidak memiliki akses ke data ini.', 'error')
            return redirect(url_for('dashboard'))
        
        # Parse clustered data dari JSON
        if result_data['clustered_data']:
            clustered_df = pd.read_json(result_data['clustered_data'])
            
            # Buat file CSV dalam memory
            output = io.StringIO()
            clustered_df.to_csv(output, index=False)
            output.seek(0)
            
            # Buat response dengan file CSV
            response = make_response(output.getvalue())
            response.headers['Content-Type'] = 'text/csv'
            response.headers['Content-Disposition'] = f'attachment; filename=clustering_results_{result_data["filename"]}_{session_id[:8]}.csv'
            
            return response
        else:
            flash('Data clustering tidak tersedia untuk didownload.', 'error')
            return redirect(url_for('show_results', session_id=session_id))
            
    except Exception as e:
        print(f"Error downloading results: {e}")
        flash('Terjadi kesalahan saat mendownload data.', 'error')
        return redirect(url_for('dashboard'))

@app.route('/download_cluster/<session_id>/<int:cluster_id>')
@login_required
def download_cluster(session_id, cluster_id):
    """Download hasil clustering untuk cluster tertentu sebagai file CSV"""
    try:
        # Ambil data hasil clustering dari database
        result_data = get_clustering_result(session_id)
        
        if not result_data:
            flash('Data hasil clustering tidak ditemukan.', 'error')
            return redirect(url_for('dashboard'))
        
        # Pastikan user memiliki akses ke data ini
        if result_data['user_id'] != current_user.id:
            flash('Anda tidak memiliki akses ke data ini.', 'error')
            return redirect(url_for('dashboard'))
        
        # Parse clustered data dari JSON
        if result_data['clustered_data']:
            clustered_df = pd.read_json(result_data['clustered_data'])
            
            # Filter data untuk cluster tertentu
            if 'Cluster' not in clustered_df.columns:
                flash('Data tidak memiliki kolom Cluster.', 'error')
                return redirect(url_for('show_results', session_id=session_id))
            
            cluster_df = clustered_df[clustered_df['Cluster'] == cluster_id]
            
            if cluster_df.empty:
                flash(f'Tidak ada data untuk Cluster {cluster_id}.', 'error')
                return redirect(url_for('show_results', session_id=session_id))
            
            # Buat file CSV dalam memory
            output = io.StringIO()
            cluster_df.to_csv(output, index=False)
            output.seek(0)
            
            # Buat response dengan file CSV
            response = make_response(output.getvalue())
            response.headers['Content-Type'] = 'text/csv'
            response.headers['Content-Disposition'] = f'attachment; filename=cluster_{cluster_id}_data_{session_id[:8]}.csv'
            
            return response
        else:
            flash('Data clustering tidak tersedia untuk didownload.', 'error')
            return redirect(url_for('show_results', session_id=session_id))
            
    except Exception as e:
        print(f"Error downloading cluster data: {e}")
        flash('Terjadi kesalahan saat mendownload data cluster.', 'error')
        return redirect(url_for('dashboard'))

@app.route('/about')
def about():
    """Halaman tentang aplikasi"""
    return render_template('about.html')

@app.route('/scraping')
@login_required
def scraping():
    """Halaman scraping E-Commerce (Tokopedia/Shopee)"""
    form = EcommerceScrapingForm()
    return render_template('scraping.html', form=form)

@app.route('/start_scraping', methods=['POST'])
@login_required
def start_scraping():
    """Memulai proses scraping E-Commerce dengan logging lengkap"""
    form = EcommerceScrapingForm()
    
    if form.validate_on_submit():
        session_id = str(uuid.uuid4())
        
        # Log permintaan scraping
        print(f"🚀 PERMINTAAN SCRAPING BARU")
        print(f"👤 User: {current_user.username} (ID: {current_user.id})")
        print(f"🏪 Platform: {form.platform.data}")
        print(f"🔍 Keyword: '{form.keyword.data}'")
        print(f"📊 Max Products: {form.max_products.data}")
        print(f"🆔 Session ID: {session_id}")
        
        # Simpan data scraping
        scraping_data[session_id] = {
            'status': 'starting',
            'progress': 0,
            'message': 'Memulai scraping...',
            'user_id': current_user.id,
            'platform': form.platform.data,
            'keyword': form.keyword.data,
            'max_products': form.max_products.data,
            'start_time': time.time()
        }
        
        print(f"💾 Data scraping disimpan untuk session: {session_id}")
        
        # Mulai scraping di thread terpisah
        thread = threading.Thread(
            target=process_scraping_with_progress,
            args=(session_id,)
        )
        thread.daemon = True
        thread.start()
        
        print(f"🔄 Thread scraping dimulai untuk session: {session_id}")
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': 'Scraping dimulai! Anda akan diarahkan ke halaman progress.'
        })
    
    # Jika form tidak valid, kembalikan error
    print(f"❌ FORM VALIDATION ERROR:")
    errors = []
    for field, field_errors in form.errors.items():
        for error in field_errors:
            error_msg = f"{form[field].label.text}: {error}"
            errors.append(error_msg)
            print(f"   - {error_msg}")
    
    return jsonify({
        'success': False,
        'errors': errors
    })

def process_scraping_with_progress(session_id):
    """Proses scraping dengan progress tracking dan monitoring lengkap"""
    try:
        scraping_info = scraping_data[session_id]
        
        # Log memulai scraping
        print(f"🎬 MEMULAI SCRAPING SESSION: {session_id}")
        print(f"📋 Parameter: platform='{scraping_info['platform']}', keyword='{scraping_info['keyword']}', max_products={scraping_info['max_products']}")
        
        # Update progress: Memulai scraping
        update_scraping_progress(session_id, 'starting', 10, 'Menyiapkan browser dan memulai scraping...')
        
        # Progress callback untuk monitoring real-time
        def progress_callback(step, progress, message):
            print(f"📊 Progress Update: {step} - {progress}% - {message}")
            update_scraping_progress(session_id, step, progress, message)
        
        # Panggil fungsi scraping dengan parameter yang benar
        products, csv_file = scrape_ecommerce_data(
            platform=scraping_info['platform'],
            keyword=scraping_info['keyword'],
            max_products=scraping_info['max_products'],
            progress_callback=progress_callback
        )
        
        # Scraping berhasil
        print(f"✅ SCRAPING BERHASIL: {len(products)} produk dikumpulkan")
        print(f"💾 File CSV disimpan di: {csv_file}")
        
        # Update data scraping dengan hasil
        scraping_data[session_id].update({
            'status': 'completed',
            'progress': 100,
            'message': 'Scraping selesai!',
            'csv_file': csv_file,
            'total_products': len(products),
            'end_time': time.time()
        })
        
        update_scraping_progress(session_id, 'completed', 100, f'Berhasil scraping {len(products)} produk!')
        
        # Emit completion event
        socketio.emit('scraping_complete', {
            'session_id': session_id,
            'total_products': len(products)
        }, room=f'scraping_{session_id}')
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ SCRAPING ERROR: {error_msg}")
        
        scraping_data[session_id].update({
            'status': 'error',
            'progress': 0,
            'message': f'Error: {error_msg}',
            'end_time': time.time()
        })
        
        update_scraping_progress(session_id, 'error', 0, f'Error: {error_msg}')
        
        # Emit error event
        socketio.emit('scraping_error', {
            'session_id': session_id,
            'error': error_msg
        }, room=f'scraping_{session_id}')

def update_scraping_progress(session_id, step, progress, message):
    """Update progress scraping dengan logging detail"""
    # Log progress ke terminal
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] 📊 SCRAPING PROGRESS [{session_id[:8]}]: {step.upper()} - {progress}% - {message}")
    
    # Update data progress
    if session_id in scraping_data:
        scraping_data[session_id].update({
            'step': step,
            'progress': progress,
            'message': message,
            'last_update': time.time()
        })
    
    # Emit ke client via SocketIO
    socketio.emit('scraping_progress', {
        'session_id': session_id,
        'step': step,
        'progress': progress,
        'message': message,
        'timestamp': timestamp
    }, room=f'scraping_{session_id}')

@app.route('/scraping_progress/<session_id>')
@login_required
def scraping_progress_page(session_id):
    """Halaman progress scraping"""
    if session_id not in scraping_data:
        flash('Session scraping tidak ditemukan.', 'error')
        return redirect(url_for('scraping'))
    
    return render_template('progress.html', 
                         session_id=session_id, 
                         process_type='scraping')

@app.route('/scraping_status/<session_id>')
@login_required
def get_scraping_status(session_id):
    """API untuk mendapatkan status scraping"""
    if session_id not in scraping_data:
        return jsonify({'error': 'Session tidak ditemukan'}), 404
    
    data = scraping_data[session_id]
    return jsonify({
        'status': data.get('status', 'unknown'),
        'progress': data.get('progress', 0),
        'message': data.get('message', ''),
        'step': data.get('step', '')
    })

@app.route('/scraping_results/<session_id>')
@login_required
def scraping_results(session_id):
    """Halaman hasil scraping"""
    if session_id not in scraping_data:
        flash('Session scraping tidak ditemukan.', 'error')
        return redirect(url_for('scraping'))
    
    data = scraping_data[session_id]
    
    if data['status'] != 'completed':
        flash('Scraping belum selesai atau gagal.', 'error')
        return redirect(url_for('scraping_progress_page', session_id=session_id))
    
    # Baca data CSV untuk ditampilkan
    try:
        df = pd.read_csv(data['csv_file'])
        
        # Hitung statistik
        stats = {
            'total_products': len(df),
            'avg_price': df['Harga'].mean() if 'Harga' in df.columns else 0,
            'avg_rating': df['Rating'].mean() if 'Rating' in df.columns else 0,
            'total_sales': df['Jumlah Penjualan'].sum() if 'Jumlah Penjualan' in df.columns else 0,
            'price_min': df['Harga'].min() if 'Harga' in df.columns else 0,
            'price_max': df['Harga'].max() if 'Harga' in df.columns else 0
        }
        
        # Konversi DataFrame ke list of dicts untuk template
        products = df.head(100).to_dict('records')  # Batasi 100 produk untuk performa
        
        return render_template('scraping_results.html',
                             session_id=session_id,
                             scraping_info=data,
                             stats=stats,
                             products=products,
                             total_products=len(df))
    
    except Exception as e:
        flash(f'Error membaca hasil scraping: {str(e)}', 'error')
        return redirect(url_for('scraping'))

@app.route('/download_scraping/<session_id>')
@login_required
def download_scraping_results(session_id):
    """Download hasil scraping dalam format CSV"""
    if session_id not in scraping_data:
        flash('Session scraping tidak ditemukan.', 'error')
        return redirect(url_for('scraping'))
    
    data = scraping_data[session_id]
    
    if data['status'] != 'completed' or 'csv_file' not in data:
        flash('File hasil scraping tidak tersedia.', 'error')
        return redirect(url_for('scraping'))
    
    try:
        return send_file(
            data['csv_file'],
            as_attachment=True,
            download_name=f"tokopedia_scraping_{session_id[:8]}.csv",
            mimetype='text/csv'
        )
    except Exception as e:
        flash(f'Error downloading file: {str(e)}', 'error')
        return redirect(url_for('scraping_results', session_id=session_id))

@app.route('/process_scraped_data/<session_id>')
@login_required
def process_scraped_data(session_id):
    """Proses data scraping untuk clustering"""
    if session_id not in scraping_data:
        flash('Session scraping tidak ditemukan.', 'error')
        return redirect(url_for('scraping'))
    
    data = scraping_data[session_id]
    
    if data['status'] != 'completed' or 'csv_file' not in data:
        flash('Data scraping tidak tersedia untuk diproses.', 'error')
        return redirect(url_for('scraping'))
    
    try:
        # Baca file CSV hasil scraping
        csv_file = data['csv_file']
        
        # Generate session ID baru untuk clustering
        clustering_session_id = str(uuid.uuid4())
        
        # Mulai proses clustering dengan data scraping
        thread = threading.Thread(
            target=process_clustering_with_progress,
            args=(csv_file, f"tokopedia_scraping_{session_id[:8]}.csv", clustering_session_id, current_user.id)
        )
        thread.daemon = True
        thread.start()
        
        flash('Data scraping akan diproses untuk clustering. Anda akan diarahkan ke halaman progress.', 'success')
        return redirect(url_for('progress_page', session_id=clustering_session_id))
        
    except Exception as e:
        flash(f'Error memproses data scraping: {str(e)}', 'error')
        return redirect(url_for('scraping_results', session_id=session_id))

@app.route('/scraping/cancel/<session_id>', methods=['POST'])
@login_required
def cancel_scraping(session_id):
    """Cancel scraping process dengan logging"""
    print(f"🛑 PERMINTAAN CANCEL SCRAPING")
    print(f"👤 User: {current_user.username} (ID: {current_user.id})")
    print(f"🆔 Session ID: {session_id}")
    
    if session_id in scraping_data:
        scraping_data[session_id]['status'] = 'cancelled'
        scraping_data[session_id]['message'] = 'Scraping dibatalkan oleh user'
        scraping_data[session_id]['end_time'] = time.time()
        
        print(f"✅ Scraping berhasil dibatalkan untuk session: {session_id}")
        return jsonify({'success': True, 'message': 'Scraping berhasil dibatalkan'})
    else:
        print(f"❌ Session tidak ditemukan: {session_id}")
        return jsonify({'success': False, 'message': 'Session tidak ditemukan'}), 404

@app.errorhandler(413)
def too_large(e):
    """Handle file terlalu besar"""
    flash('File terlalu besar. Maksimal ukuran file adalah 16MB.', 'error')
    return redirect(url_for('index'))

@app.errorhandler(404)
def not_found(e):
    """Handle halaman tidak ditemukan"""
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(e):
    """Handle internal server error"""
    return render_template('500.html'), 500

if __name__ == '__main__':
    # Buat direktori yang diperlukan
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs('static', exist_ok=True)
    os.makedirs('uploads', exist_ok=True)
    
    # Inisialisasi database
    init_database()
    
    # Log informasi sistem dan startup
    print("=" * 80)
    print("🚀 STARTING K-MEANS CLUSTERING WEB APPLICATION")
    print("=" * 80)
    print(f"📊 Upload CSV file untuk melakukan clustering otomatis")
    print(f"🔗 Akses aplikasi di: http://localhost:5000")
    print(f"📁 Upload folder: {UPLOAD_FOLDER}")
    print(f"📂 Static folder: static")
    print(f"💾 Database: Initialized")
    print(f"🌐 SocketIO: Enabled")
    print(f"🔧 Debug mode: True")
    print("=" * 80)
    print("📋 FITUR YANG TERSEDIA:")
    print("   ✅ Upload dan analisis file CSV")
    print("   ✅ K-Means clustering otomatis")
    print("   ✅ Visualisasi hasil clustering")
    print("   ✅ Scraping data Tokopedia")
    print("   ✅ Real-time progress monitoring")
    print("   ✅ User authentication & management")
    print("=" * 80)
    print("🔍 MONITORING SCRAPING:")
    print("   📊 Progress real-time di terminal")
    print("   🌐 Verifikasi koneksi internet")
    print("   ⚡ Monitoring resource sistem")
    print("   🔄 Retry mechanism & timeout")
    print("   📈 Statistik error rate")
    print("=" * 80)

    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
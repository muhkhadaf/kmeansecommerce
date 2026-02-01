"""
Modul Visualisasi untuk K-Means Clustering
Berisi fungsi-fungsi untuk membuat grafik elbow method,
scatter plot hasil clustering, dan visualisasi lainnya.
"""

import matplotlib.pyplot as plt
import matplotlib
import seaborn as sns
import pandas as pd
import numpy as np
from sklearn.decomposition import PCA
import os
import uuid
import warnings

# Set matplotlib backend untuk server
matplotlib.use('Agg')
warnings.filterwarnings('ignore')

# Set style untuk grafik yang lebih menarik
plt.style.use('default')
sns.set_palette("husl")

def create_elbow_plot(inertia_scores, silhouette_scores, optimal_k, progress_callback=None):
    """
    Membuat grafik Elbow Method dan Silhouette Score
    
    Args:
        inertia_scores (dict): Dictionary inertia scores
        silhouette_scores (dict): Dictionary silhouette scores
        optimal_k (int): Nilai k optimal yang dipilih
        progress_callback (function): Callback untuk update progress
        
    Returns:
        str: Path file grafik yang disimpan
    """
    def update_progress(step, progress, message):
        if progress_callback:
            progress_callback(step, progress, message)
        print(f"📊 {message}")
    
    update_progress('visualization', 10, "Membuat grafik Elbow Method dan Silhouette Score...")
    
    try:
        # Siapkan data
        k_values = sorted(inertia_scores.keys())
        inertias = [inertia_scores[k] for k in k_values]
        silhouettes = [silhouette_scores.get(k, 0) for k in k_values]
        
        update_progress('visualization', 30, "Menggambar plot inertia...")
        
        # Buat figure dengan 2 subplot
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        # Plot 1: Elbow Method (Inertia)
        ax1.plot(k_values, inertias, 'bo-', linewidth=2, markersize=8, color='#2E86AB')
        ax1.axvline(x=optimal_k, color='red', linestyle='--', linewidth=2, alpha=0.7, label=f'Optimal k = {optimal_k}')
        ax1.set_xlabel('Jumlah Cluster (k)', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Inertia (Within-cluster sum of squares)', fontsize=12, fontweight='bold')
        ax1.set_title('Elbow Method untuk Menentukan Jumlah Cluster Optimal', fontsize=14, fontweight='bold', pad=20)
        ax1.grid(True, alpha=0.3)
        ax1.legend(fontsize=11)
        
        # Tambahkan anotasi pada titik optimal
        optimal_inertia = inertia_scores.get(optimal_k, 0)
        ax1.annotate(f'Optimal\nk={optimal_k}', 
                    xy=(optimal_k, optimal_inertia), 
                    xytext=(optimal_k + 0.5, optimal_inertia + max(inertias) * 0.1),
                    arrowprops=dict(arrowstyle='->', color='red', alpha=0.7),
                    fontsize=10, fontweight='bold', color='red')
        
        update_progress('visualization', 60, "Menggambar plot silhouette...")
        
        # Plot 2: Silhouette Score
        ax2.plot(k_values, silhouettes, 'go-', linewidth=2, markersize=8, color='#A23B72')
        ax2.axvline(x=optimal_k, color='red', linestyle='--', linewidth=2, alpha=0.7, label=f'Optimal k = {optimal_k}')
        ax2.set_xlabel('Jumlah Cluster (k)', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Silhouette Score', fontsize=12, fontweight='bold')
        ax2.set_title('Silhouette Score untuk Berbagai Jumlah Cluster', fontsize=14, fontweight='bold', pad=20)
        ax2.grid(True, alpha=0.3)
        ax2.legend(fontsize=11)
        
        # Tambahkan anotasi pada titik optimal
        optimal_silhouette = silhouette_scores.get(optimal_k, 0)
        ax2.annotate(f'Optimal\nk={optimal_k}\nScore={optimal_silhouette:.3f}', 
                    xy=(optimal_k, optimal_silhouette), 
                    xytext=(optimal_k + 0.5, optimal_silhouette + max(silhouettes) * 0.1),
                    arrowprops=dict(arrowstyle='->', color='red', alpha=0.7),
                    fontsize=10, fontweight='bold', color='red')
        
        # Atur layout
        plt.tight_layout()
        
        update_progress('visualization', 80, "Menyimpan grafik...")
        
        # Simpan grafik
        filename = f"elbow_plot_{uuid.uuid4().hex[:8]}.png"
        filepath = os.path.join('static', filename)
        plt.savefig(filepath, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        
        update_progress('visualization', 90, f"Grafik Elbow Method disimpan: {filepath}")
        return filename
        
    except Exception as e:
        print(f"❌ Error membuat grafik elbow: {str(e)}")
        return None

def create_cluster_plot(data, cluster_labels, cluster_centers, progress_callback=None):
    """
    Membuat scatter plot hasil clustering dengan PCA jika diperlukan
    
    Args:
        data (pd.DataFrame): Data yang sudah dinormalisasi
        cluster_labels (array): Label cluster untuk setiap data point
        cluster_centers (array): Koordinat pusat cluster
        progress_callback (function): Callback untuk update progress
    
    Returns:
        str: Path file plot yang disimpan
    """
    def update_progress(step, progress, message):
        if progress_callback:
            progress_callback(step, progress, message)
        print(f"📊 {message}")
    
    update_progress('visualization', 20, "Membuat cluster scatter plot...")
    
    try:
        # Jika data memiliki lebih dari 2 dimensi, gunakan PCA
        feature_count = data.shape[1]

        if feature_count > 2:
            update_progress('visualization', 40, "Menggunakan PCA untuk reduksi dimensi ke 2D...")
            pca = PCA(n_components=2)
            data_2d = pca.fit_transform(data)
            centers_2d = pca.transform(cluster_centers)
            
            # Informasi variance explained
            variance_explained = pca.explained_variance_ratio_
            update_progress('visualization', 50, f"PCA variance explained: {variance_explained[0]:.3f}, {variance_explained[1]:.3f}")
            
            x_label = f'PC1 ({variance_explained[0]:.1%} variance)'
            y_label = f'PC2 ({variance_explained[1]:.1%} variance)'
        elif feature_count == 2:
            data_2d = data.values
            centers_2d = cluster_centers
            x_label = data.columns[0]
            y_label = data.columns[1]
        elif feature_count == 1:
            data_2d = np.column_stack([data.values.flatten(), np.zeros(len(data))])
            centers_2d = np.column_stack([cluster_centers.flatten(), np.zeros(len(cluster_centers))])
            x_label = data.columns[0]
            y_label = 'Feature 2'
        else:
            raise ValueError("Dataset tidak memiliki fitur yang cukup untuk visualisasi clustering.")
        
        update_progress('visualization', 60, "Menggambar scatter plot...")
        
        # Buat plot
        plt.figure(figsize=(12, 8))
        
        # Warna untuk setiap cluster
        colors = plt.cm.Set3(np.linspace(0, 1, len(np.unique(cluster_labels))))
        
        # Plot setiap cluster
        for i, color in enumerate(colors):
            cluster_mask = cluster_labels == i
            plt.scatter(data_2d[cluster_mask, 0], data_2d[cluster_mask, 1], 
                       c=[color], label=f'Cluster {i}', alpha=0.7, s=50)
        
        # Plot cluster centers
        plt.scatter(centers_2d[:, 0], centers_2d[:, 1], 
                   c='red', marker='x', s=200, linewidths=3, label='Centroids')
        
        plt.xlabel(x_label, fontsize=12, fontweight='bold')
        plt.ylabel(y_label, fontsize=12, fontweight='bold')
        plt.title('K-Means Clustering Results', fontsize=14, fontweight='bold')
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        update_progress('visualization', 80, "Menyimpan cluster plot...")
        
        # Simpan plot
        filename = f"cluster_plot_{uuid.uuid4().hex[:8]}.png"
        filepath = os.path.join('static', filename)
        plt.savefig(filepath, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        
        update_progress('visualization', 90, f"Cluster plot disimpan: {filepath}")
        return filename
        
    except Exception as e:
        print(f"❌ Error membuat grafik clustering: {str(e)}")
        return None

def create_cluster_distribution_plot(cluster_labels):
    """
    Membuat bar chart distribusi data per cluster
    
    Args:
        cluster_labels (array): Label cluster
        
    Returns:
        str: Path file grafik yang disimpan
    """
    print("📊 Membuat grafik distribusi cluster...")
    
    try:
        # Hitung distribusi cluster
        cluster_counts = pd.Series(cluster_labels).value_counts().sort_index()
        
        # Buat figure
        plt.figure(figsize=(10, 6))
        
        # Buat bar chart
        bars = plt.bar(cluster_counts.index, cluster_counts.values, 
                      color=plt.cm.Set3(np.linspace(0, 1, len(cluster_counts))),
                      alpha=0.8, edgecolor='black', linewidth=1)
        
        # Tambahkan label pada bar
        for bar, count in zip(bars, cluster_counts.values):
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height + height*0.01,
                    f'{count}\n({count/len(cluster_labels)*100:.1f}%)',
                    ha='center', va='bottom', fontweight='bold')
        
        # Atur grafik
        plt.xlabel('Cluster ID', fontsize=12, fontweight='bold')
        plt.ylabel('Jumlah Data Points', fontsize=12, fontweight='bold')
        plt.title('Distribusi Data per Cluster', fontsize=14, fontweight='bold', pad=20)
        plt.grid(True, alpha=0.3, axis='y')
        
        # Atur x-axis
        plt.xticks(cluster_counts.index)
        
        # Tambahkan informasi total
        total_points = len(cluster_labels)
        plt.figtext(0.02, 0.02, f'Total data points: {total_points}', 
                   fontsize=10, style='italic')
        
        # Atur layout
        plt.tight_layout()
        
        # Simpan grafik
        filename = f"cluster_distribution_{uuid.uuid4().hex[:8]}.png"
        filepath = os.path.join('static', filename)
        plt.savefig(filepath, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        
        print(f"✅ Grafik distribusi cluster disimpan: {filepath}")
        return filename
        
    except Exception as e:
        print(f"❌ Error membuat grafik distribusi: {str(e)}")
        return None

def create_feature_importance_plot(data, feature_names, cluster_labels, n_clusters):
    """
    Membuat heatmap untuk menunjukkan karakteristik setiap cluster
    
    Args:
        data (pandas.DataFrame): Data yang sudah dinormalisasi
        feature_names (list): Nama-nama fitur
        cluster_labels (array): Label cluster
        n_clusters (int): Jumlah cluster
        
    Returns:
        str: Path file grafik yang disimpan
    """
    print("🔥 Membuat heatmap karakteristik cluster...")
    
    try:
        # Buat dataframe dengan cluster labels
        df_with_clusters = data.copy()
        df_with_clusters['Cluster'] = cluster_labels
        
        # Hitung rata-rata setiap fitur per cluster
        cluster_means = df_with_clusters.groupby('Cluster')[feature_names].mean()
        
        # Buat figure
        plt.figure(figsize=(12, 8))
        
        # Buat heatmap
        sns.heatmap(cluster_means.T, 
                   annot=True, 
                   cmap='RdYlBu_r', 
                   center=0,
                   fmt='.3f',
                   cbar_kws={'label': 'Normalized Value'},
                   linewidths=0.5)
        
        # Atur grafik
        plt.title('Karakteristik Setiap Cluster (Rata-rata Fitur)', 
                 fontsize=14, fontweight='bold', pad=20)
        plt.xlabel('Cluster ID', fontsize=12, fontweight='bold')
        plt.ylabel('Features', fontsize=12, fontweight='bold')
        
        # Atur layout
        plt.tight_layout()
        
        # Simpan grafik
        filename = f"cluster_heatmap_{uuid.uuid4().hex[:8]}.png"
        filepath = os.path.join('static', filename)
        plt.savefig(filepath, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        
        print(f"✅ Heatmap karakteristik cluster disimpan: {filepath}")
        return filename
        
    except Exception as e:
        print(f"❌ Error membuat heatmap: {str(e)}")
        return None

def cleanup_old_plots(max_age_hours=24):
    """
    Membersihkan file plot lama untuk menghemat ruang disk
    
    Args:
        max_age_hours (int): Maksimal umur file dalam jam
    """
    try:
        import time
        current_time = time.time()
        static_dir = 'static'
        
        if not os.path.exists(static_dir):
            return
        
        for filename in os.listdir(static_dir):
            if filename.endswith('.png') and ('elbow_plot_' in filename or 'cluster_plot_' in filename):
                filepath = os.path.join(static_dir, filename)
                file_age = current_time - os.path.getctime(filepath)
                
                # Hapus file jika lebih tua dari max_age_hours
                if file_age > (max_age_hours * 3600):
                    os.remove(filepath)
                    print(f"🗑️ Menghapus file plot lama: {filename}")
                    
    except Exception as e:
        print(f"⚠️ Error membersihkan file plot lama: {str(e)}")

# Fungsi utilitas untuk mengatur style matplotlib
def set_plot_style():
    """Mengatur style default untuk semua plot"""
    plt.rcParams.update({
        'figure.facecolor': 'white',
        'axes.facecolor': 'white',
        'axes.edgecolor': 'black',
        'axes.linewidth': 1,
        'axes.grid': True,
        'grid.alpha': 0.3,
        'font.size': 10,
        'axes.titlesize': 14,
        'axes.labelsize': 12,
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'legend.fontsize': 10
    })

# Inisialisasi style saat modul diimport
set_plot_style()
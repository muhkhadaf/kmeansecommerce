"""
Modul Clustering untuk K-Means
Berisi fungsi-fungsi untuk menentukan jumlah cluster optimal,
menjalankan algoritma K-Means, dan evaluasi hasil clustering.
"""

import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, calinski_harabasz_score, davies_bouldin_score
import warnings

warnings.filterwarnings('ignore')

def calculate_inertia_scores(data, max_k=10, progress_callback=None):
    """
    Menghitung inertia scores untuk berbagai nilai k (Elbow Method)
    
    Args:
        data (pd.DataFrame): Data yang sudah dinormalisasi
        max_k (int): Nilai k maksimum untuk dicoba
        progress_callback (function): Callback untuk update progress
    
    Returns:
        tuple: (k_values, inertia_scores)
    """
    def update_progress(step, progress, message):
        if progress_callback:
            progress_callback(step, progress, message)
        print(f"📊 {message}")
    
    update_progress('clustering', 10, f"Menghitung inertia scores untuk k=1 hingga k={max_k}...")
    
    k_values = range(1, max_k + 1)
    inertia_scores = []
    
    for i, k in enumerate(k_values):
        progress = 10 + (i / len(k_values)) * 40  # 10% to 50%
        update_progress('clustering', progress, f"Menghitung inertia untuk k={k}...")
        
        if k == 1:
            # Untuk k=1, inertia adalah total sum of squares
            centroid = data.mean()
            inertia = ((data - centroid) ** 2).sum().sum()
        else:
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            kmeans.fit(data)
            inertia = kmeans.inertia_
        
        inertia_scores.append(inertia)
        update_progress('clustering', progress, f"k={k}: inertia={inertia:.2f}")
    
    return list(k_values), inertia_scores

def calculate_silhouette_scores(data, max_k=10, min_k=2, progress_callback=None):
    """
    Menghitung silhouette score untuk berbagai nilai k
    
    Args:
        data (pandas.DataFrame): Data yang sudah dinormalisasi
        max_k (int): Nilai k maksimum untuk dicoba
        min_k (int): Nilai k minimum untuk dicoba
        progress_callback (function): Callback untuk update progress
        
    Returns:
        dict: Dictionary dengan k sebagai key dan silhouette score sebagai value
    """
    def update_progress(step, progress, message):
        if progress_callback:
            progress_callback(step, progress, message)
        print(f"📊 {message}")
    
    silhouette_scores = {}
    
    # Batasi max_k berdasarkan jumlah data
    max_possible_k = min(max_k, len(data) - 1)
    
    update_progress('clustering', 50, f"Menghitung silhouette scores untuk k={min_k} hingga k={max_possible_k}...")
    
    k_range = list(range(min_k, max_possible_k + 1))
    
    for i, k in enumerate(k_range):
        progress = 50 + (i / len(k_range)) * 30  # 50% to 80%
        update_progress('clustering', progress, f"Menghitung silhouette untuk k={k}...")
        
        try:
            kmeans = KMeans(
                n_clusters=k, 
                random_state=42, 
                n_init=20,
                max_iter=300
            )
            cluster_labels = kmeans.fit_predict(data)
            
            # Hitung silhouette score
            sil_score = silhouette_score(data, cluster_labels)
            silhouette_scores[k] = sil_score
            update_progress('clustering', progress, f"k={k}: silhouette={sil_score:.3f}")
            
        except Exception as e:
            print(f"⚠️ Error untuk k={k}: {str(e)}")
            continue
    
    return silhouette_scores

def find_elbow_point(inertia_scores):
    """
    Mencari titik elbow menggunakan metode second derivative
    
    Args:
        inertia_scores (dict): Dictionary inertia scores
        
    Returns:
        int: Nilai k optimal berdasarkan elbow method
    """
    if len(inertia_scores) < 3:
        return min(inertia_scores.keys()) if inertia_scores else 3
    
    k_values = sorted(inertia_scores.keys())
    inertias = [inertia_scores[k] for k in k_values]
    
    # Hitung first derivative (slope)
    first_derivatives = []
    for i in range(1, len(inertias)):
        slope = inertias[i] - inertias[i-1]
        first_derivatives.append(slope)
    
    # Hitung second derivative
    second_derivatives = []
    for i in range(1, len(first_derivatives)):
        second_slope = first_derivatives[i] - first_derivatives[i-1]
        second_derivatives.append(abs(second_slope))
    
    # Cari titik dengan second derivative terbesar (elbow point)
    if second_derivatives:
        max_second_deriv_idx = np.argmax(second_derivatives)
        elbow_k = k_values[max_second_deriv_idx + 2]  # +2 karena offset dari derivative
    else:
        elbow_k = k_values[1] if len(k_values) > 1 else k_values[0]
    
    return elbow_k

def find_optimal_clusters(data, max_k=10, progress_callback=None):
    """
    Menentukan jumlah cluster optimal menggunakan Elbow Method dan Silhouette Score
    
    Args:
        data (pandas.DataFrame): Data yang sudah dinormalisasi
        max_k (int): Nilai k maksimum untuk dicoba
        progress_callback (function): Callback untuk update progress
        
    Returns:
        tuple: (optimal_k, inertia_scores, silhouette_scores)
    """
    def update_progress(step, progress, message):
        if progress_callback:
            progress_callback(step, progress, message)
        print(f"🔍 {message}")
    
    update_progress('clustering', 5, "Mencari jumlah cluster optimal...")
    
    # Batasi max_k berdasarkan ukuran data
    data_size = len(data)
    max_k = min(max_k, data_size // 2, 15)  # Maksimal 15 cluster atau setengah dari data
    min_k = 2
    
    update_progress('clustering', 10, f"Menguji k dari {min_k} hingga {max_k}")
    
    # Hitung inertia scores (Elbow Method)
    k_values, inertia_scores = calculate_inertia_scores(data, max_k, progress_callback)
    update_progress('clustering', 50, f"Inertia scores: {dict(zip(k_values, inertia_scores))}")
    
    # Hitung silhouette scores
    silhouette_scores = calculate_silhouette_scores(data, max_k, min_k, progress_callback)
    update_progress('clustering', 80, f"Silhouette scores: {silhouette_scores}")
    
    # Tentukan k optimal berdasarkan elbow method
    elbow_k = find_elbow_point(dict(zip(k_values, inertia_scores)))
    update_progress('clustering', 85, f"Elbow point: k = {elbow_k}")
    
    # Tentukan k optimal berdasarkan silhouette score (maksimum)
    if silhouette_scores:
        silhouette_k = max(silhouette_scores, key=silhouette_scores.get)
        update_progress('clustering', 87, f"Silhouette optimal: k = {silhouette_k} (score: {silhouette_scores[silhouette_k]:.4f})")
    else:
        silhouette_k = elbow_k
    
    # Pilih k optimal (prioritas pada silhouette score jika reasonable)
    if abs(elbow_k - silhouette_k) <= 2:
        # Jika perbedaan kecil, pilih yang silhouette score lebih tinggi
        optimal_k = silhouette_k
        reason = "silhouette score"
    else:
        # Jika perbedaan besar, pilih elbow point
        optimal_k = elbow_k
        reason = "elbow method"
    
    # Validasi k optimal
    optimal_k = max(2, min(optimal_k, max_k))
    
    update_progress('clustering', 90, f"K optimal dipilih: {optimal_k} (berdasarkan {reason})")
    
    return optimal_k, dict(zip(k_values, inertia_scores)), silhouette_scores

def perform_kmeans_clustering(data, n_clusters, random_state=42, progress_callback=None):
    """
    Melakukan K-Means clustering dengan parameter optimal
    
    Args:
        data (pd.DataFrame): Data yang sudah dinormalisasi
        n_clusters (int): Jumlah cluster
        random_state (int): Random state untuk reproducibility
        progress_callback (function): Callback untuk update progress
    
    Returns:
        tuple: (kmeans_model, cluster_labels, cluster_centers)
    """
    def update_progress(step, progress, message):
        if progress_callback:
            progress_callback(step, progress, message)
        print(f"🎯 {message}")
    
    update_progress('clustering', 92, f"Melakukan K-Means clustering dengan k={n_clusters}...")
    
    # Inisialisasi dan fit K-Means
    kmeans = KMeans(
        n_clusters=n_clusters,
        random_state=random_state,
        n_init=20,
        max_iter=300,
        tol=1e-4
    )
    
    update_progress('clustering', 95, "Menjalankan algoritma K-Means...")
    cluster_labels = kmeans.fit_predict(data)
    cluster_centers = kmeans.cluster_centers_
    
    update_progress('clustering', 98, "Clustering selesai!")
    cluster_distribution = np.bincount(cluster_labels)
    update_progress('clustering', 100, f"Distribusi cluster: {cluster_distribution}")
    
    return kmeans, cluster_labels, cluster_centers

def evaluate_clustering(data, cluster_labels):
    """
    Evaluasi hasil clustering menggunakan berbagai metrik
    
    Args:
        data (pandas.DataFrame): Data yang sudah dinormalisasi
        cluster_labels (array): Label cluster hasil K-Means
        
    Returns:
        tuple: (inertia, silhouette_avg, calinski_harabasz, davies_bouldin)
    """
    print("📊 Mengevaluasi hasil clustering...")
    
    try:
        # Hitung inertia (dari model K-Means)
        kmeans_temp = KMeans(n_clusters=len(np.unique(cluster_labels)), random_state=42)
        kmeans_temp.fit(data)
        inertia = kmeans_temp.inertia_
        
        # Hitung silhouette score
        silhouette_avg = silhouette_score(data, cluster_labels)
        
        # Hitung Calinski-Harabasz Index
        calinski_harabasz = calinski_harabasz_score(data, cluster_labels)
        
        # Hitung Davies-Bouldin Index
        davies_bouldin = davies_bouldin_score(data, cluster_labels)
        
        print(f"📈 Hasil evaluasi:")
        print(f"   Inertia: {inertia:.4f}")
        print(f"   Silhouette Score: {silhouette_avg:.4f}")
        print(f"   Calinski-Harabasz Index: {calinski_harabasz:.4f}")
        print(f"   Davies-Bouldin Index: {davies_bouldin:.4f}")
        
        return inertia, silhouette_avg, calinski_harabasz, davies_bouldin
        
    except Exception as e:
        print(f"❌ Error dalam evaluasi: {str(e)}")
        return 0, 0, 0, 0

def get_cluster_centers(kmeans_model, feature_names):
    """
    Mendapatkan pusat cluster dalam format yang mudah dibaca
    
    Args:
        kmeans_model: Model K-Means yang sudah di-fit
        feature_names (list): Nama-nama fitur
        
    Returns:
        pandas.DataFrame: DataFrame berisi pusat cluster
    """
    centers_df = pd.DataFrame(
        kmeans_model.cluster_centers_,
        columns=feature_names
    )
    centers_df.index.name = 'Cluster'
    return centers_df

def get_cluster_statistics(clustered_data, original_data, numeric_columns):
    """
    Mendapatkan statistik untuk setiap cluster
    
    Args:
        clustered_data (pandas.DataFrame): Data dengan label cluster
        original_data (pandas.DataFrame): Data asli sebelum normalisasi
        numeric_columns (list): Nama kolom numerik
        
    Returns:
        dict: Statistik untuk setiap cluster
    """
    cluster_stats = {}
    
    # Gabungkan data asli dengan cluster labels
    original_with_clusters = original_data[numeric_columns].copy()
    original_with_clusters['Cluster'] = clustered_data['Cluster']
    
    for cluster_id in sorted(clustered_data['Cluster'].unique()):
        cluster_data = original_with_clusters[original_with_clusters['Cluster'] == cluster_id]
        
        stats = {
            'count': len(cluster_data),
            'percentage': (len(cluster_data) / len(original_with_clusters)) * 100,
            'mean': cluster_data[numeric_columns].mean().to_dict(),
            'std': cluster_data[numeric_columns].std().to_dict(),
            'min': cluster_data[numeric_columns].min().to_dict(),
            'max': cluster_data[numeric_columns].max().to_dict()
        }
        
        cluster_stats[f'Cluster_{cluster_id}'] = stats
    
    return cluster_stats
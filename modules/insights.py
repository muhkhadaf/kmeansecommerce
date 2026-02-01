"""
Modul untuk menghasilkan insight dinamis dari hasil clustering
Versi UPGRADE: Dynamic Insight + Label & Makna Cluster
(Siap Skripsi & UI)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any


# =========================================================
# KAMUS MAKNA CLUSTER
# =========================================================
CLUSTER_MEANINGS = {
    "Produk Unggulan": {
        "title": "Produk Unggulan",
        "description": (
            "Produk dengan tingkat penjualan dan rating di atas rata-rata pasar. "
            "Cluster ini menunjukkan performa terbaik dan menjadi prioritas utama "
            "dalam strategi pemasaran dan pengelolaan stok."
        )
    },
    "Produk Fast Moving": {
        "title": "Produk Fast Moving",
        "description": (
            "Produk dengan harga relatif lebih rendah namun memiliki tingkat penjualan tinggi. "
            "Cocok untuk strategi volume penjualan, promosi, dan bundling produk."
        )
    },
    "Produk Premium / Niche": {
        "title": "Produk Premium / Niche",
        "description": (
            "Produk dengan harga di atas rata-rata dan tingkat penjualan lebih rendah. "
            "Menargetkan segmen pasar khusus dengan potensi margin keuntungan yang lebih tinggi."
        )
    },
    "Produk Potensial": {
        "title": "Produk Potensial",
        "description": (
            "Produk dengan rating tinggi namun tingkat penjualan belum optimal. "
            "Memiliki peluang besar untuk dikembangkan melalui peningkatan promosi."
        )
    },
    "Produk Perlu Evaluasi": {
        "title": "Produk Perlu Evaluasi",
        "description": (
            "Produk yang belum menunjukkan keunggulan signifikan dari sisi harga, "
            "penjualan, maupun rating sehingga perlu evaluasi atau perbaikan strategi."
        )
    }
}


# =========================================================
# ENTRY POINT
# =========================================================
def generate_clustering_insights(
    data: pd.DataFrame,
    cluster_labels: np.ndarray,
    optimal_k: int,
    metrics: Dict[str, float]
) -> Dict[str, Any]:

    return {
        'cluster_analysis': analyze_clusters(data, cluster_labels, optimal_k),
        'quality_assessment': assess_clustering_quality(metrics),
        'strategic_recommendations': generate_strategic_recommendations(
            data, cluster_labels, optimal_k, metrics
        ),
        'cluster_characteristics': get_cluster_characteristics(data, cluster_labels),
        'business_implications': generate_business_implications(
            data, cluster_labels, optimal_k
        )
    }


# =========================================================
# ANALISIS DISTRIBUSI CLUSTER
# =========================================================
def analyze_clusters(
    data: pd.DataFrame,
    cluster_labels: np.ndarray,
    optimal_k: int
) -> Dict[str, Any]:

    total_data = len(cluster_labels)
    cluster_sizes = pd.Series(cluster_labels).value_counts().sort_index()

    analysis = {
        'total_clusters': optimal_k,
        'total_data_points': total_data,
        'cluster_distribution': {},
        'balance_assessment': '',
        'largest_cluster': int(cluster_sizes.idxmax()),
        'smallest_cluster': int(cluster_sizes.idxmin())
    }

    for cid in range(optimal_k):
        size = int(cluster_sizes.get(cid, 0))
        analysis['cluster_distribution'][f'Cluster {cid}'] = {
            'size': size,
            'percentage': round((size / total_data) * 100, 1)
        }

    ratio = cluster_sizes.min() / cluster_sizes.max() if cluster_sizes.max() else 0

    if ratio > 0.7:
        analysis['balance_assessment'] = "Cluster sangat seimbang"
    elif ratio > 0.4:
        analysis['balance_assessment'] = "Cluster cukup seimbang"
    elif ratio > 0.2:
        analysis['balance_assessment'] = "Cluster tidak seimbang"
    else:
        analysis['balance_assessment'] = "Cluster sangat tidak seimbang"

    return analysis


# =========================================================
# KUALITAS CLUSTERING
# =========================================================
def assess_clustering_quality(metrics: Dict[str, float]) -> Dict[str, Any]:

    sil = metrics.get('silhouette_score', 0)
    cal = metrics.get('calinski_harabasz', 0)
    dav = metrics.get('davies_bouldin', 999)

    return {
        'overall_quality': (
            "Sangat Baik" if sil >= 0.7 else
            "Baik" if sil >= 0.5 else
            "Cukup" if sil >= 0.25 else
            "Kurang"
        ),
        'silhouette_interpretation': (
            "Cluster sangat jelas" if sil >= 0.7 else
            "Cluster cukup jelas" if sil >= 0.5 else
            "Cluster masih overlap" if sil >= 0.25 else
            "Cluster kurang jelas"
        ),
        'separation_quality': (
            "Sangat baik" if dav <= 1 else
            "Cukup baik" if dav <= 2 else
            "Kurang baik"
        ),
        'compactness_quality': (
            "Sangat kompak" if cal >= 100 else
            "Cukup kompak" if cal >= 50 else
            "Kurang kompak"
        ),
        'recommendations': []
    }


# =========================================================
# KARAKTERISTIK & MAKNA CLUSTER
# =========================================================
def get_cluster_characteristics(
    data: pd.DataFrame,
    cluster_labels: np.ndarray
) -> Dict[str, Any]:

    df = data.copy()
    df['Cluster'] = cluster_labels

    numeric_columns = data.select_dtypes(include=[np.number]).columns

    def find_column(cols, keywords):
        for col in cols:
            name = col.lower()
            for k in keywords:
                if k in name:
                    return col
        return None

    price_col = find_column(numeric_columns, {'price', 'harga'})
    sold_col = find_column(numeric_columns, {'sold', 'terjual'})
    rating_col = find_column(numeric_columns, {'rating'})

    global_means = data[numeric_columns].mean()
    characteristics = {}

    for cluster_id in sorted(df['Cluster'].unique()):
        cluster_data = df[df['Cluster'] == cluster_id]
        cluster_means = cluster_data[numeric_columns].mean()

        # Statistik deskriptif
        stats = {
            col: {
                'mean': round(cluster_data[col].mean(), 2),
                'std': round(cluster_data[col].std(), 2),
                'min': round(cluster_data[col].min(), 2),
                'max': round(cluster_data[col].max(), 2),
            }
            for col in numeric_columns
        }

        # Label default
        label = "Produk Perlu Evaluasi"

        if all([price_col, sold_col, rating_col]):
            label = classify_cluster_label(
                cluster_means,
                global_means,
                price_col,
                sold_col,
                rating_col
            )

        characteristics[f'Cluster {cluster_id}'] = {
            'size': len(cluster_data),
            'statistics': stats,
            'profile': identify_cluster_profile(
                cluster_data, data, numeric_columns
            ),
            'label': label,
            'meaning': CLUSTER_MEANINGS[label]
        }

    return characteristics


# =========================================================
# PROFIL NUMERIK CLUSTER
# =========================================================
def identify_cluster_profile(
    cluster_data: pd.DataFrame,
    all_data: pd.DataFrame,
    numeric_columns: List[str]
) -> Dict[str, str]:

    profile = {}

    for col in numeric_columns:
        c_mean = cluster_data[col].mean()
        g_mean = all_data[col].mean()

        if c_mean > g_mean * 1.15:
            profile[col] = "Tinggi"
        elif c_mean < g_mean * 0.85:
            profile[col] = "Rendah"
        else:
            profile[col] = "Sedang"

    return profile


# =========================================================
# KLASIFIKASI LABEL CLUSTER
# =========================================================
def classify_cluster_label(
    cluster_means: pd.Series,
    global_means: pd.Series,
    price_col: str,
    sold_col: str,
    rating_col: str
) -> str:

    sold = cluster_means[sold_col]
    price = cluster_means[price_col]
    rating = cluster_means[rating_col]

    if sold > global_means[sold_col] and rating > global_means[rating_col]:
        return "Produk Unggulan"
    elif sold > global_means[sold_col] and price < global_means[price_col]:
        return "Produk Fast Moving"
    elif price > global_means[price_col] and sold < global_means[sold_col]:
        return "Produk Premium / Niche"
    elif rating > global_means[rating_col]:
        return "Produk Potensial"
    else:
        return "Produk Perlu Evaluasi"


# =========================================================
# REKOMENDASI STRATEGIS
# =========================================================
def generate_strategic_recommendations(
    data: pd.DataFrame,
    cluster_labels: np.ndarray,
    optimal_k: int,
    metrics: Dict[str, float]
) -> List[str]:

    rec = []
    sil = metrics.get('silhouette_score', 0)

    rec.append(
        "Clustering cukup baik untuk segmentasi pasar"
        if sil >= 0.5 else
        "Perlu evaluasi lanjutan pada jumlah cluster atau fitur"
    )

    rec.append(
        "Segmentasi sederhana" if optimal_k <= 3 else
        "Segmentasi moderat" if optimal_k <= 5 else
        "Segmentasi kompleks"
    )

    rec.extend([
        "Lakukan promosi berbeda untuk tiap cluster",
        "Pantau performa cluster secara berkala",
        "Gunakan hasil cluster sebagai dasar pengambilan keputusan bisnis"
    ])

    return rec


# =========================================================
# IMPLIKASI BISNIS
# =========================================================
def generate_business_implications(
    data: pd.DataFrame,
    cluster_labels: np.ndarray,
    optimal_k: int
) -> Dict[str, Any]:

    sizes = pd.Series(cluster_labels).value_counts()
    largest_pct = (sizes.max() / len(cluster_labels)) * 100

    segmentation = (
        "Pasar didominasi satu segmen utama" if largest_pct > 50 else
        "Terdapat segmen dominan dan pendukung" if largest_pct > 30 else
        "Pasar tersebar merata"
    )

    return {
        'market_segmentation': segmentation,
        'resource_allocation': "Alokasi sumber daya disesuaikan per cluster",
        'targeting_strategy': f"Strategi targeting berbasis {optimal_k} cluster",
        'growth_opportunities': [
            "Optimalisasi cluster unggulan",
            "Pengembangan cluster potensial",
            "Eksplorasi pasar niche"
        ]
    }

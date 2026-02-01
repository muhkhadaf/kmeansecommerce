"""
Modul Preprocessing untuk K-Means Clustering
Berisi fungsi-fungsi untuk membersihkan data, normalisasi, dan persiapan data
sebelum dilakukan clustering menggunakan algoritma K-Means.
"""

import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
import warnings

warnings.filterwarnings('ignore')

def identify_numeric_columns(df):
    """
    Identifikasi kolom numerik dalam dataframe
    
    Args:
        df (pandas.DataFrame): Dataframe input
        
    Returns:
        list: Daftar nama kolom numerik
    """
    numeric_columns = []
    
    for col in df.columns:
        # Cek apakah kolom adalah numerik
        if df[col].dtype in ['int64', 'float64', 'int32', 'float32']:
            numeric_columns.append(col)
        else:
            # Coba konversi ke numerik
            try:
                pd.to_numeric(df[col], errors='raise')
                numeric_columns.append(col)
            except (ValueError, TypeError):
                continue
    
    return numeric_columns

def clean_data(df, numeric_columns):
    """
    Membersihkan data dari nilai kosong dan outlier ekstrem
    
    Args:
        df (pandas.DataFrame): Dataframe input
        numeric_columns (list): Daftar kolom numerik
        
    Returns:
        tuple: (cleaned_df, updated_numeric_columns, cleaning_stats)
    """
    # Buat copy dataframe
    numeric_columns = list(numeric_columns)
    cleaned_df = df[numeric_columns].copy()
    removed_columns = []
    
    # Konversi ke numerik dan ganti error dengan NaN
    for col in numeric_columns:
        cleaned_df[col] = pd.to_numeric(cleaned_df[col], errors='coerce')
    
    # Hapus kolom yang seluruh nilainya NaN setelah konversi
    all_nan_columns = [col for col in numeric_columns if cleaned_df[col].isna().all()]
    if all_nan_columns:
        cleaned_df = cleaned_df.drop(columns=all_nan_columns)
        numeric_columns = [col for col in numeric_columns if col not in all_nan_columns]
        removed_columns.extend(all_nan_columns)
    
    if not numeric_columns:
        stats = {
            'removed_columns': removed_columns,
            'missing_values_handled': 0,
            'outliers_removed': 0
        }
        return cleaned_df, numeric_columns, stats
    
    # Hapus baris yang semua kolomnya NaN
    cleaned_df = cleaned_df.dropna(how='all')
    
    # Impute nilai kosong dengan median (jika ada)
    missing_before = cleaned_df[numeric_columns].isnull().sum().sum()
    if missing_before > 0:
        imputer = SimpleImputer(strategy='median')
        cleaned_df[numeric_columns] = imputer.fit_transform(cleaned_df[numeric_columns])
    
    # Hapus outlier ekstrem menggunakan IQR method dan catat jumlah baris yang dihapus
    outliers_removed = 0
    for col in list(numeric_columns):
        Q1 = cleaned_df[col].quantile(0.25)
        Q3 = cleaned_df[col].quantile(0.75)
        IQR = Q3 - Q1
        
        # Definisi outlier: nilai di luar 1.5 * IQR dari Q1 dan Q3
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        
        # Filter outlier ekstrem (hanya yang sangat jauh)
        extreme_lower = Q1 - 3 * IQR
        extreme_upper = Q3 + 3 * IQR
        
        before_rows = len(cleaned_df)
        cleaned_df = cleaned_df[
            (cleaned_df[col] >= extreme_lower) & 
            (cleaned_df[col] <= extreme_upper)
        ]
        outliers_removed += before_rows - len(cleaned_df)
    
    # Hapus kolom dengan variance 0
    zero_variance_columns = [col for col in numeric_columns if cleaned_df[col].std() == 0]
    if zero_variance_columns:
        cleaned_df = cleaned_df.drop(columns=zero_variance_columns)
        numeric_columns = [col for col in numeric_columns if col not in zero_variance_columns]
        removed_columns.extend(zero_variance_columns)
    
    stats = {
        'removed_columns': removed_columns,
        'missing_values_handled': int(missing_before),
        'outliers_removed': int(outliers_removed)
    }
    
    return cleaned_df, numeric_columns, stats

def normalize_data(df, scaler=None):
    """
    Normalisasi data menggunakan StandardScaler
    
    Args:
        df (pandas.DataFrame): Dataframe input
        scaler (StandardScaler, optional): Scaler yang sudah di-fit sebelumnya
        
    Returns:
        tuple: (normalized_data, fitted_scaler)
    """
    if scaler is None:
        scaler = StandardScaler()
        normalized_data = scaler.fit_transform(df)
    else:
        normalized_data = scaler.transform(df)
    
    # Konversi kembali ke DataFrame
    normalized_df = pd.DataFrame(
        normalized_data, 
        columns=df.columns,
        index=df.index
    )
    
    return normalized_df, scaler

def validate_data_for_clustering(df, min_samples=10, min_features=1):
    """
    Validasi apakah data cocok untuk clustering
    
    Args:
        df (pandas.DataFrame): Dataframe input
        min_samples (int): Minimum jumlah sampel
        min_features (int): Minimum jumlah fitur
        
    Returns:
        tuple: (is_valid, error_message)
    """
    # Cek jumlah sampel
    if len(df) < min_samples:
        return False, f"Data terlalu sedikit. Minimal {min_samples} baris data diperlukan."
    
    # Cek jumlah fitur
    if len(df.columns) < min_features:
        return False, f"Fitur terlalu sedikit. Minimal {min_features} kolom numerik diperlukan."
    
    # Cek variance
    for col in df.columns:
        if df[col].var() == 0:
            return False, f"Kolom '{col}' memiliki variance 0 (semua nilai sama)."
    
    # Cek apakah ada nilai infinite
    if np.isinf(df.values).any():
        return False, "Data mengandung nilai infinite."
    
    # Cek apakah ada nilai NaN
    if df.isnull().any().any():
        return False, "Data masih mengandung nilai kosong setelah preprocessing."
    
    return True, "Data valid untuk clustering."

def preprocess_data(df, target_column=None, progress_callback=None):
    """
    Fungsi utama untuk preprocessing data
    
    Args:
        df (pd.DataFrame): DataFrame input
        target_column (str): Nama kolom target (jika ada)
        progress_callback (function): Callback untuk update progress
    
    Returns:
        tuple: (processed_df, scaler, preprocessing_info)
    """
    preprocessing_info = {
        'original_shape': df.shape,
        'original_columns': df.columns.tolist(),
        'numeric_columns': [],
        'removed_columns': [],
        'missing_values_handled': 0,
        'outliers_removed': 0,
        'scaling_method': 'StandardScaler',
        'final_shape': None,
        'final_columns': []
    }
    
    def update_progress(step, progress, message):
        if progress_callback:
            progress_callback(step, progress, message)
        print(f"🔄 {message}")
    
    update_progress('preprocessing', 10, "Memulai preprocessing data...")
    
    # 1. Identifikasi kolom numerik
    update_progress('preprocessing', 20, "Mengidentifikasi kolom numerik...")
    numeric_cols = identify_numeric_columns(df)
    preprocessing_info['numeric_columns'] = numeric_cols
    update_progress('preprocessing', 30, f"Ditemukan {len(numeric_cols)} kolom numerik")
    
    # 2. Filter hanya kolom numerik
    if not numeric_cols:
        raise ValueError("Tidak ada kolom numerik yang ditemukan untuk clustering!")
    
    update_progress('preprocessing', 40, "Memfilter kolom numerik...")
    df_numeric = df[numeric_cols].copy()
    preprocessing_info['removed_columns'] = [col for col in df.columns if col not in numeric_cols]
    
    # 3. Bersihkan data
    update_progress('preprocessing', 50, "Membersihkan data (missing values & outliers)...")
    df_cleaned, numeric_cols, cleaning_stats = clean_data(df_numeric, numeric_cols)
    preprocessing_info['missing_values_handled'] = cleaning_stats.get('missing_values_handled', 0)
    preprocessing_info['outliers_removed'] = cleaning_stats.get('outliers_removed', 0)
    preprocessing_info['removed_columns'].extend(cleaning_stats.get('removed_columns', []))
    preprocessing_info['numeric_columns'] = numeric_cols

    if not numeric_cols:
        raise ValueError("Tidak ada kolom numerik yang valid setelah preprocessing!")
    
    update_progress('preprocessing', 70, f"Data cleaning selesai")
    
    # 4. Normalisasi data
    update_progress('preprocessing', 80, "Melakukan normalisasi data...")
    df_normalized, scaler = normalize_data(df_cleaned)
    update_progress('preprocessing', 90, f"Normalisasi selesai menggunakan {preprocessing_info['scaling_method']}")
    
    # 5. Validasi data
    update_progress('preprocessing', 95, "Memvalidasi data untuk clustering...")
    validation_result, error_msg = validate_data_for_clustering(df_normalized)
    
    if not validation_result:
        raise ValueError(f"Data tidak cocok untuk clustering setelah preprocessing: {error_msg}")
    
    preprocessing_info['final_shape'] = df_normalized.shape
    preprocessing_info['final_columns'] = df_normalized.columns.tolist()
    
    update_progress('preprocessing', 100, "Preprocessing data selesai!")
    
    return df_normalized, scaler, preprocessing_info

def get_data_summary(df, numeric_columns):
    """
    Mendapatkan ringkasan statistik data
    
    Args:
        df (pandas.DataFrame): Dataframe input
        numeric_columns (list): Daftar kolom numerik
        
    Returns:
        dict: Ringkasan statistik
    """
    summary = {
        'total_rows': len(df),
        'total_columns': len(df.columns),
        'numeric_columns': len(numeric_columns),
        'missing_values': df.isnull().sum().sum(),
        'data_types': df.dtypes.value_counts().to_dict()
    }
    
    if numeric_columns:
        numeric_data = df[numeric_columns]
        summary.update({
            'numeric_stats': {
                'mean': numeric_data.mean().to_dict(),
                'std': numeric_data.std().to_dict(),
                'min': numeric_data.min().to_dict(),
                'max': numeric_data.max().to_dict()
            }
        })
    
    return summary
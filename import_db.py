import mysql.connector
import sys

def import_database():
    print("====================================")
    print("  Railway Database Importer Script  ")
    print("====================================")
    print("Pastikan Anda sudah mendapatkan detail koneksi dari tab 'Connect' di Railway.")
    print("")

    # Input Credentials
    host = input("Host (contoh: monorail.proxy.rlwy.net): ").strip()
    if not host:
        print("Host tidak boleh kosong.")
        return

    port_input = input("Port (contoh: 53123): ").strip()
    try:
        port = int(port_input)
    except ValueError:
        print("Port harus berupa angka.")
        return

    user = input("User (biasanya: root): ").strip()
    password = input("Password: ").strip()
    database = input("Database Name (contoh: railway): ").strip()

    print("\n[INFO] Menghubungkan ke database...")
    
    try:
        mydb = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            port=port,
            database=database
        )
        cursor = mydb.cursor()
        print("[SUKSES] Terhubung ke database!")
        
        filename = 'kmeans_clustering_web.sql'
        print(f"[INFO] Membaca file '{filename}'...")
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                sql_script = f.read()
        except FileNotFoundError:
            print(f"[ERROR] File '{filename}' tidak ditemukan di folder ini.")
            return

        print("[INFO] Menjalankan import SQL... (mohon tunggu sebentar)")
        
        # Execute multiple statements
        # Iterating over the generator executes the statements
        for result in cursor.execute(sql_script, multi=True):
            if result.with_rows:
                result.fetchall() # Consume results if any
            
        mydb.commit()
        print("[SUKSES] Import database berhasil selesai!")
        print("Tabel dan data telah berhasil dibuat di Railway.")
        
    except mysql.connector.Error as err:
        print(f"[MYSQL ERROR] {err}")
    except Exception as e:
        print(f"[ERROR] Terjadi kesalahan: {e}")
    finally:
        if 'mydb' in locals() and mydb.is_connected():
            cursor.close()
            mydb.close()
            print("[INFO] Koneksi ditutup.")

if __name__ == "__main__":
    import_database()

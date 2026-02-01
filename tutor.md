Tutorial Deployment ke Railway
Tutorial ini akan memandu Anda langkah demi langkah untuk men-deploy aplikasi Flask K-Means Ecommerce ini ke Railway.app.

Persiapan Awal
Saya telah menyiapkan file-file yang diperlukan untuk deployment supaya project ini kompatibel dengan cloud server:

Dockerfile
: File konfigurasi untuk membuat environment server yang berisi Python dan Google Chrome (untuk fitur scraping).
requirements.txt
: Ditambahkan gunicorn dan eventlet sebagai web server produksi.
modules/ecommerce_scraper.py
: Diupdate agar browser berjalan dalam mode "headless" (tanpa tampilan grafis) agar bisa jalan di server.
Langkah 1: Upload ke GitHub
Railway mengambil kode langsung dari GitHub, jadi Anda harus meng-upload project ini ke repository GitHub terlebih dahulu.

Buat repository baru di GitHub. Beri nama bebas, misal kmeans-ecommerce.
Buka terminal di folder project ini (kmeans_web) dan jalankan perintah berikut:
git init
git add .
git commit -m "Siap deploy ke Railway"
git branch -M main
git remote add origin https://github.com/<USERNAME_ANDA>/kmeans-ecommerce.git
git push -u origin main
Catatan: Ganti <USERNAME_ANDA> dengan username GitHub Anda sesuai URL repository yang baru dibuat.

Langkah 2: Buat Project di Railway
Buka Railway.app dan login (bisa pakai akun GitHub).
Klik "New Project" > "Deploy from GitHub repo".
Pilih repository yang baru saja Anda upload (kmeans-ecommerce).
Klik "Deploy Now".
Langkah 3: Konfigurasi Database (MySQL)
Aplikasi ini membutuhkan database MySQL. Kita akan buat langsung di Railway.

Di dashboard project Railway Anda, klik tombol "New" (atau klik kanan di area kosong).
Pilih "Database" > "MySQL".
Tunggu hingga database selesai dibuat (statusnya hijau/aktif).
Klik pada kotak MySQL yang baru muncul, lalu buka tab "Variables".
Anda akan melihat daftar variabel seperti MYSQLHOST, MYSQLPORT, MYSQLUSER, MYSQLPASSWORD, MYSQLDATABASE, dll. Biarkan tab ini terbuka.
Langkah 4: Hubungkan Aplikasi ke Database
Sekarang kita perlu memberi tahu aplikasi Flask untuk menggunakan database MySQL yang baru dibuat.

Kembali ke view project (klik nama project di kiri atas).
Klik pada kotak aplikasi Anda (biasanya bernama sesuai nama repo).
Buka tab "Variables".
Klik "New Variable" dan masukkan data berikut (copy dari tab Variables MySQL tadi):
Variable Name	Value
MYSQL_HOST	${{MySQL.MYSQLHOST}}
MYSQL_PORT	${{MySQL.MYSQLPORT}}
MYSQL_USER	${{MySQL.MYSQLUSER}}
MYSQL_PASSWORD	${{MySQL.MYSQLPASSWORD}}
MYSQL_DATABASE	${{MySQL.MYSQLDATABASE}}
SECRET_KEY	Masukkan text acak yang panjang (misal: rahasia_app_kmeans_12345)
Tips: Menggunakan ${{MySQL.VAR}} adalah fitur "Reference" Railway. Jika Anda mengetik ${{, Railway akan otomatis menyarankan variabel dari service lain (MySQL). Ini lebih aman daripada copy-paste manual nilai password.

Langkah 5: Setup Tabel Database
Aplikasi sudah terhubung, tapi databasenya masih kosong. Anda perlu mengimpor struktur tabel.

Cara Paling Mudah (via Railway CLI / Query):

Klik service MySQL di Railway.
Buka tab "Data".
Anda bisa menjalankan query SQL di sini.
Buka file 
kmeans_clustering_web.sql
 di project lokal Anda.
Copy semua isinya, lalu paste ke terminal SQL di Railway (jika tersedia) atau gunakan tool database manager seperti DBeaver atau HeidiSQL untuk connect ke database Railway (gunakan kredensial dari tab Connect) dan import file SQL tersebut.
Alternatif (jika fitur Data Railway terbatas): Gunakan DBeaver/HeidiSQL di laptop Anda:

Host: (Lihat di tab Connect Railway -> Public Networking. Jika belum ada, klik "Generate Domain" di service MySQL tapi ini biasanya berbayar/pro. Untuk pengguna free, biasanya koneksi internal sudah cukup, tapi untuk import awal butuh akses luar. Saran: Gunakan TCP Proxy yang disediakan Railway di tab Connect untuk akses dari DBeaver).
Langkah 6: Generate Domain (Agar bisa diakses publik)
Klik pada service aplikasi Flask Anda.
Buka tab "Settings".
Scroll ke bawah ke bagian "Networking".
Klik "Generate Domain".
Railway akan memberikan URL (contoh: kmeans-ecommerce-production.up.railway.app).
Klik URL tersebut untuk membuka aplikasi Anda.
Troubleshooting
Error Scraping: Jika fitur scraping gagal, cek tab "Logs" di service aplikasi. Pastikan tidak ada error terkait Chrome/Chromium. Setup Dockerfile sudah menangani instalasi Chrome, jadi seharusnya aman.
Database Error: Pastikan variabel environment sudah benar sama persis penulisannya (MYSQL_HOST, dll).
Build Failed: Cek tab Build Logs. Biasanya karena ada library yang gagal install.
Selamat! Aplikasi Anda sekarang sudah online. 🚀


Comment
Ctrl+Alt+M

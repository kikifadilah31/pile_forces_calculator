# 🏗️ Pile Forces Calculator

**Alat bantu teknik sipil untuk mendistribusikan gaya reaksi struktur (dari Midas Civil / SAP2000 / ETABS) menjadi gaya di setiap tiang pancang dalam satu pilecap**, memakai metode *rigid pilecap* (distribusi elastis berbasis inersia polar grup tiang).

Tersedia dalam **dua antarmuka yang berbagi satu mesin hitung yang sama**:

| Antarmuka | Untuk apa | Cara akses |
|-----------|-----------|------------|
| 🌐 **Web app** (Streamlit, ter-host) | Eksplorasi interaktif, input tabel, plot Plotly, simpan/muat proyek — **langsung pakai di browser, tanpa instalasi** | **[pileforcescalculator.streamlit.app](https://pileforcescalculator.streamlit.app/)** |
| ⌨️ **CLI** (command line) | Otomasi/batch, laporan siap audit, output file terstruktur, dijalankan lokal | `pile-forces ...` (pasang via `uv`) |

Karena keduanya memakai inti (`src/pile_forces/`) yang sama, **hasil angkanya identik**.

---

## Daftar Isi
1. [Apa yang dihitung](#1-apa-yang-dihitung)
2. [Instalasi CLI](#2-instalasi-cli)
3. [Cara pakai — CLI](#3-cara-pakai--cli)
4. [Web app (Streamlit)](#4-web-app-streamlit)
5. [Format file input](#5-format-file-input)
6. [Parameter desain](#6-parameter-desain)
7. [Output yang dihasilkan](#7-output-yang-dihasilkan)
8. [Metodologi & rumus](#8-metodologi--rumus)
9. [Konvensi tanda & satuan](#9-konvensi-tanda--satuan)
10. [Diagram](#10-diagram)
11. [Struktur project](#11-struktur-project)
12. [Testing & verifikasi (V&V)](#12-testing--verifikasi-vv)
13. [Batasan & asumsi](#13-batasan--asumsi)

---

## 1. Apa yang dihitung

Untuk **setiap kombinasi tiang × load case**, alat ini menghitung:

- **Gaya aksial** tiap tiang (kompresi positif / tarik negatif), termasuk tambahan berat sendiri pilecap, tanah timbunan, dan tiang.
- **Gaya lateral** `Hx`, `Hy` dan resultannya `H = √(Hx²+Hy²)`, termasuk kontribusi torsi (`Mz`).
- **Envelope (governing load case)** per tiang: kompresi maksimum, tarik maksimum, dan lateral maksimum/minimum — lengkap dengan LC penyebabnya.

Cocok untuk desain pondasi tiang di mana reaksi dari analisis struktur perlu didistribusikan ke masing-masing tiang.

---

## 2. Instalasi CLI

CLI dipasang dengan **[uv](https://docs.astral.sh/uv/)** — tidak perlu clone repo, tidak perlu urus virtual environment manual.

### Langkah 1 — Pasang `uv` (sekali saja)

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```
```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Langkah 2 — Pasang Pile Forces Calculator

**Opsi A — via Git (disarankan):**
```bash
uv tool install git+https://github.com/kikifadilah31/pile_forces_calculator.git
```

**Opsi B — tanpa Git, langsung dari ZIP:**
```bash
uv tool install https://github.com/kikifadilah31/pile_forces_calculator/archive/refs/heads/main.zip
```

Setelah itu perintah **`pile-forces`** tersedia di seluruh terminal Anda:
```bash
pile-forces --help
```

**Memperbarui / menghapus:**
```bash
uv tool upgrade pile-forces-calculator
uv tool uninstall pile-forces-calculator
```

### Menjalankan sekali tanpa memasang (ephemeral)

```bash
uvx --from git+https://github.com/kikifadilah31/pile_forces_calculator.git pile-forces --help
```

> **Developer** (ingin ubah kode / jalankan test): clone repo lalu
> `uv venv --python 3.11 && uv pip install -e ".[dev]"`.

---

## 3. Cara pakai — CLI

Perintah utama: **`pile-forces`**.

```bash
# Paling sederhana: pakai contoh data di folder input/
pile-forces --piles input/piles.csv --load-cases input/load_cases.csv --params input/params.json

# Tanpa file params JSON — parameter lewat flag, satuan Ton, tanpa PDF
pile-forces --piles input/piles.csv --load-cases input/load_cases.csv \
    --pile-shape Square --pile-dim 0.5 --unit Ton --no-report

# Centroid manual (untuk pilecap asimetris)
pile-forces --piles input/piles.csv --load-cases input/load_cases.csv \
    --centroid Manual --xc 1.5 --yc 1.5

# Lihat semua opsi
pile-forces --help
```

### Semua argumen

**File input (path wajib eksplisit — tidak ada auto-detect):**

| Flag | Wajib? | Keterangan |
|------|--------|------------|
| `--piles CSV/XLSX` | ✅ | Koordinat tiang `[Pile_ID, X, Y]` (m). Menerima **CSV atau Excel** |
| `--load-cases CSV/XLSX` | ✅ | Load cases `[LC_ID, Fx, Fy, Fz, Mx, My, Mz]` (kN, kN·m) |
| `--params JSON` | ➖ | Parameter desain (opsional) |
| `--pilecap CSV/XLSX` | ➖ | Polygon pilecap tak beraturan `[X, Y]` (m). Bila kosong → rectangle `pilecap_length × pilecap_width` terpusat di centroid |

**Output:**

| Flag | Default | Keterangan |
|------|---------|------------|
| `--output DIR` | `output` | Folder induk untuk hasil ber-timestamp |
| `--excel` | (off) | Tulis juga `results.xlsx` (sheet Master + Envelope) |
| `--no-labels` | (off) | Sembunyikan teks nilai gaya di plot |
| `--no-report` | (off) | Lewati pembuatan PDF Typst |
| `--report-title TEKS` | "Pile Forces Analysis Report" | Judul di PDF |

**Capacity check (kapasitas izin/allowable, kN):**

| Flag | Keterangan |
|------|------------|
| `--check-capacity` | Aktifkan pengecekan DCR |
| `--cap-axial-comp` / `--cap-axial-tension` / `--cap-lateral` | Kapasitas izin per tiang (isi ≥ 1 yang > 0) |

**Analisis & metadata:**

| Flag | Keterangan |
|------|------------|
| `--no-ixy` | Matikan suku product-of-inertia (pakai rumus per-sumbu klasik). Default: Ixy aktif |
| `--project-name` / `--engineer` / `--revision` | Metadata proyek untuk laporan PDF |

**Override parameter desain** (menimpa `--params` / default):
`--pilecap-length`, `--pilecap-width`, `--pilecap-height`, `--gamma-concrete`,
`--soil-height`, `--gamma-soil`, `--pile-shape {Circle,Square}`, `--pile-dim`,
`--pile-length`, `--gamma-pile`, `--centroid {Auto,Manual}`, `--xc`, `--yc`,
`--unit {kN,Ton}`.

Contoh capacity check + Excel + metadata:
```bash
pile-forces --piles input/piles.csv --load-cases input/load_cases.csv --params input/params.json \
    --check-capacity --cap-axial-comp 1500 --cap-axial-tension 300 --cap-lateral 80 \
    --excel --project-name "Jembatan X" --engineer "KFT" --revision "R1"
```

### Urutan prioritas parameter (berlapis)

```
config default  ←  file params.json  ←  flag CLI
   (paling rendah)                       (paling tinggi)
```

Artinya: flag CLI selalu menang; jika suatu nilai tidak diberikan lewat flag, dipakai nilai dari `params.json`; jika `params.json` tidak diberikan, dipakai default bawaan.

---

## 4. Web app (Streamlit)

Versi web sudah **ter-host dan siap pakai langsung di browser — tanpa instalasi apa pun**:

### 👉 **https://pileforcescalculator.streamlit.app/**

Aplikasi web punya 6 tab: **Input Data**, **Results**, **Lateral Vectors**, **Axial Bubbles**, **Envelope**, dan **Report**. Fitur khusus web:

- Input tabel interaktif (copy-paste dari Excel) atau upload CSV.
- Plot Plotly interaktif (zoom, hover, download PNG) — dengan **boundary pilecap (hijau)** & **outline dimensi pile (biru putus-putus)**, sama seperti versi CLI.
- **Pilecap tak beraturan**: aktifkan "Custom pilecap (irregular shape)" di sidebar, lalu isi titik polygon (tabel atau upload CSV/Excel `[X, Y]`).
- **Capacity Check (DCR)**: aktifkan di sidebar + isi kapasitas izin → tab **🛡️ Capacity Check** (tabel DCR, verdict OK/INADEQUATE, download).
- **Toggle Ixy** (grup asimetris) di sidebar.
- **Excel**: upload input `.xlsx`, dan unduh hasil sebagai `.xlsx` (Master + Envelope).
- **Metadata laporan** (project/engineer/revision) di tab Report.
- **Simpan/Muat proyek** sebagai file `.json` (menyimpan semua parameter + tabel).
- Generate & unduh laporan PDF.

> **Kapan pakai web vs CLI?** Web cocok untuk eksplorasi cepat dan sekali-jalan.
> CLI cocok untuk banyak load case, otomasi, atau bila butuh output file
> terstruktur + laporan siap audit.
>
> <sub>Catatan teknis: deployment web memakai `requirements.txt` (memasang paket
> ini beserta extra `web`). Untuk menjalankan web secara lokal saat
> pengembangan: `uv pip install -e ".[web]"` lalu `streamlit run app.py`.</sub>

---

## 5. Format file input

### `piles.csv` — koordinat tiang

```csv
Pile_ID,X,Y
P1,0.0,0.0
P2,3.0,0.0
P3,0.0,3.0
P4,3.0,3.0
```

| Kolom | Tipe | Satuan |
|-------|------|--------|
| `Pile_ID` | teks (unik) | — |
| `X`, `Y` | angka | meter |

### `load_cases.csv` — load cases (reaksi dari Midas)

```csv
LC_ID,Fx,Fy,Fz,Mx,My,Mz
LC1,100.0,50.0,1000.0,200.0,150.0,80.0
LC2,-80.0,120.0,1400.0,-260.0,90.0,-60.0
```

| Kolom | Tipe | Satuan |
|-------|------|--------|
| `LC_ID` | teks (unik) | — |
| `Fx`, `Fy`, `Fz` | angka | kN |
| `Mx`, `My`, `Mz` | angka | kN·m |

> Nilai gaya adalah **reaksi** dari Midas — alat ini otomatis mengonversinya menjadi **aksi** untuk desain pondasi (lihat [§9](#9-konvensi-tanda--satuan)).

### `pilecap.csv` — pilecap tak beraturan (opsional)

Untuk pilecap **bukan persegi**, sediakan koordinat titik-titik polygon (urut mengelilingi tepi, tertutup otomatis):

```csv
X,Y
-0.6,-0.6
2.4,-0.6
2.4,1.5
0.9,2.6
-0.6,1.5
```

| Kolom | Tipe | Satuan | Keterangan |
|-------|------|--------|------------|
| `X`, `Y` | angka | m | Titik sudut polygon (minimal 3) |

- **Tanpa `--pilecap`** → pilecap dianggap **persegi** `pilecap_length × pilecap_width`, terpusat di centroid grup tiang.
- **Dengan `--pilecap`** → boundary mengikuti polygon; **berat pilecap & tanah dihitung dari luas polygon aktual** (rumus shoelace), sehingga gambar dan perhitungan konsisten.

### `params.json` — parameter desain (opsional)

```json
{
  "pilecap_length": 5.0,
  "pilecap_width": 5.0,
  "pilecap_height": 1.5,
  "gamma_concrete": 24.0,
  "soil_height": 1.0,
  "gamma_soil": 18.0,
  "pile_shape": "Circle",
  "pile_dim": 0.6,
  "pile_length": 20.0,
  "gamma_pile": 24.0,
  "centroid_mode": "Auto",
  "x_centroid": 0.0,
  "y_centroid": 0.0,
  "apply_ixy": true,
  "check_capacity": false,
  "cap_axial_comp": 0.0,
  "cap_axial_tension": 0.0,
  "cap_lateral": 0.0,
  "project_name": "",
  "engineer": "",
  "revision": "",
  "output_unit": "kN"
}
```

> File input (`--piles`, `--load-cases`, `--pilecap`) menerima **CSV maupun Excel (`.xlsx`)** — dispatch otomatis dari ekstensi.

**Validasi fail-fast:** jika kolom hilang, ada nilai non-numerik/kosong, `Pile_ID`/`LC_ID` duplikat, atau dimensi ≤ 0 → program **berhenti dengan pesan jelas** (bukan diam-diam menghasilkan angka salah).

---

## 6. Parameter desain

| Parameter | Default | Satuan | Keterangan |
|-----------|---------|--------|------------|
| `pilecap_length` / `_width` / `_height` | 5.0 / 5.0 / 1.5 | m | Dimensi pilecap (P × L × tebal) |
| `gamma_concrete` | 24.0 | kN/m³ | Berat jenis beton |
| `soil_height` | 1.0 | m | Tinggi tanah timbunan di atas pilecap |
| `gamma_soil` | 18.0 | kN/m³ | Berat jenis tanah |
| `pile_shape` | `Circle` | — | `Circle` atau `Square` |
| `pile_dim` | 0.6 | m | Diameter (Circle) atau sisi (Square) |
| `pile_length` | 20.0 | m | Panjang tiang |
| `gamma_pile` | 24.0 | kN/m³ | Berat jenis tiang |
| `centroid_mode` | `Auto` | — | `Auto` (rata-rata koordinat) atau `Manual` |
| `x_centroid` / `y_centroid` | 0.0 / 0.0 | m | Dipakai jika `centroid_mode = Manual` |
| `apply_ixy` | `true` | — | Sertakan suku product-of-inertia (grup asimetris). Matikan untuk bandingkan dengan rumus per-sumbu klasik |
| `check_capacity` | `false` | — | Aktifkan pengecekan DCR (kapasitas izin) |
| `cap_axial_comp` / `cap_axial_tension` / `cap_lateral` | 0.0 | kN | Kapasitas **izin** per tiang (isi ≥ 1 yang > 0 saat check aktif) |
| `project_name` / `engineer` / `revision` | "" | — | Metadata untuk laporan PDF |
| `output_unit` | `kN` | — | Satuan output: `kN` atau `Ton` (1 Ton = 9.81 kN) |

---

## 7. Output yang dihasilkan

Setiap run CLI membuat **folder baru ber-timestamp** (tidak menimpa run sebelumnya):

```
output/pile_forces_YYYYMMDD_HHMMSS/
├── run_manifest.json     # jejak reproduksibilitas (lihat di bawah)
├── run.log               # log diagnostik proses
├── master_output.csv     # semua hasil pile × LC
├── envelope.csv          # governing load case per tiang
├── plots/
│   ├── lateral_<LC>.png       # vektor lateral tiap LC
│   ├── axial_<LC>.png         # bubble aksial tiap LC
│   ├── env_max_compression.png
│   ├── env_max_tension.png
│   ├── env_max_lateral.png
│   └── env_min_lateral.png
├── SUMMARY.md            # ringkasan auditable (nilai antara + governing + verdict kapasitas)
├── results.xlsx          # (bila --excel) workbook Master + Envelope
└── Pile_Analysis_Report.pdf   # laporan Typst (kecuali --no-report)
```

Bila **capacity check aktif**, `master_output.csv` & `envelope.csv` mendapat kolom tambahan
`DCR_Comp, DCR_Tension, DCR_Lateral, DCR_Max, Status` (governing `Max_DCR` + `Status` di envelope).

**`run_manifest.json`** mencatat: versi tool, timestamp, versi Python & dependency, **hash SHA-256 tiap file input**, seluruh parameter & argumen, serta metode/standar yang dipakai — sehingga hasil bisa direproduksi dan ditelusuri kapan pun.

---

## 8. Metodologi & rumus

Metode: **distribusi elastis rigid-pilecap berbasis inersia polar grup tiang** (asumsi pilecap kaku sempurna).

**Berat sendiri:**

```
W_pilecap = L × W × H × γ_beton
W_soil    = L × W × H_tanah × γ_tanah
A_tiang   = D²           (Square, D = sisi)
          = ¼ π D²        (Circle, D = diameter)
W_tiang   = A_tiang × L_tiang × γ_tiang
```

**Gaya aksial tiap tiang i:**

```
P_i = (Fz_aksi + W_pilecap + W_soil)/n  +  b·x_i + c·y_i  +  W_tiang

dengan (biaxial + product of inertia):
  Ixx=Σy², Iyy=Σx², Ixy=Σ(x·y), det = Ixx·Iyy − Ixy²
  b = (My·Ixx + Mx·Ixy)/det ,  c = (−Mx·Iyy − My·Ixy)/det
```

Untuk grup **simetris** (Ixy=0) ini menyederhana jadi bentuk klasik
`−Mx·y_i/Σy² + My·x_i/Σx²`. Suku Ixy hanya berpengaruh pada layout **asimetris**
dan bisa dimatikan (`--no-ixy` / checkbox) untuk perbandingan.

**Capacity check (DCR, basis kapasitas izin):**

```
DCR_kompresi = P_i (tekan) / cap_axial_comp
DCR_tarik    = |P_i (tarik)| / cap_axial_tension
DCR_lateral  = H_i / cap_lateral
DCR_max      = maks(ketiganya)   →  Status = OK bila ≤ 1.0, else INADEQUATE
```
Kapasitas 0 = komponen tak dicek. Semua dihitung di kN (rasio, tak terpengaruh unit output).

**Gaya lateral + torsi tiap tiang i:**

```
Hx_i = Fx_aksi/n − Mz_aksi·y_i / I_polar
Hy_i = Fy_aksi/n + Mz_aksi·x_i / I_polar
H_i  = √(Hx_i² + Hy_i²)

dengan  I_polar = Σx² + Σy²
        x_i, y_i = koordinat tiang relatif terhadap centroid
        n = jumlah tiang
```

**Proteksi pembagian nol:** jika seluruh tiang segaris (Σx²=0, Σy², atau I_polar = 0), suku momen/torsi pada sumbu tersebut otomatis menjadi 0 (benar secara fisik — tidak ada lengan momen penahan).

---

## 9. Konvensi tanda & satuan

**Satuan internal selalu kN dan meter (momen kN·m).** Konversi ke Ton hanya dilakukan di batas output (tampilan/file), bukan saat perhitungan → menjamin konsistensi.

**Reaksi → Aksi** (Midas menghasilkan reaksi; desain pondasi butuh aksi):

| Komponen | Konversi |
|----------|----------|
| `Fx`, `Fy` | dibalik tanda (× −1) |
| `Mx`, `My`, `Mz` | dibalik tanda (× −1) |
| `Fz` | **tetap positif** (gravitasi ke bawah = kompresi = positif untuk desain pondasi) |

**Tanda gaya aksial hasil:** **positif = kompresi**, **negatif = tarik**.

---

## 10. Diagram

Kedua jenis diagram (aksial & lateral) menampilkan:

- **Boundary pilecap** = garis **hijau** tertutup (rectangle untuk pilecap persegi, polygon untuk pilecap custom dari `pilecap.csv`).
- **Bentuk tiang sesuai `pile_shape`** — lingkaran untuk Circle, kotak untuk Square.
- **Garis putus-putus biru** = ukuran fisik tiang sebenarnya (diameter/sisi, skala nyata dalam meter), terpisah dari besaran gaya.
- **Centroid** ditandai salib emas.
- **Legend** diletakkan di luar area plot (tidak menutupi tiang), dengan ukuran simbol tetap.

**Axial Bubbles:** ukuran bubble ∝ besar gaya aksial; **merah = kompresi**, **biru = tarik**; bubble bergaya-nol disembunyikan.

**Lateral Vectors:** panah hijau menunjukkan arah & besar relatif gaya lateral resultan tiap tiang.

---

## 11. Struktur project

```
pile_forces_calculator/
├── app.py                      # Frontend Streamlit
├── input/                      # Contoh data siap pakai
│   ├── piles.csv
│   ├── load_cases.csv
│   ├── pilecap.csv             # contoh pilecap tak beraturan
│   └── params.json
├── src/pile_forces/            # ── INTI BERSAMA (shared core) ──
│   ├── config.py               # Konstanta terpusat (satuan, default, warna, toleransi)
│   ├── io_utils.py             # Baca CSV, resolusi params, konversi satuan
│   ├── validators.py           # Validasi input fail-fast
│   ├── math_engine.py          # Rumus murni (numpy) — tanpa pandas/matplotlib
│   ├── domain_engine.py        # build_master_output, build_envelope
│   ├── renderer.py             # Diagram matplotlib → PNG (untuk CLI)
│   ├── reporter.py             # Laporan PDF Typst + SUMMARY.md
│   ├── provenance.py           # run_manifest.json + hashing input
│   ├── plotly_viz.py           # Diagram Plotly interaktif (untuk Streamlit)
│   ├── state_manager.py        # Simpan/muat proyek JSON (untuk Streamlit)
│   └── cli.py                  # Entry point CLI (orkestrator)
├── tests/                      # Uji unit, validasi, integrasi, golden-file
│   ├── data/                   # Fixture test (terpisah dari input/)
│   └── golden/                 # Hasil acuan untuk regression test
├── requirements.txt            # deps untuk deploy Streamlit Cloud
└── pyproject.toml
```

Prinsip: `math_engine.py` murni (tidak impor pandas/matplotlib/argparse); `renderer.py` tidak melakukan kalkulasi; `cli.py` hanya orkestrator. Satu modul = satu tanggung jawab.

---

## 12. Testing & verifikasi (V&V)

```bash
pytest              # menjalankan seluruh 33 test
ruff check src      # linting
mypy                # type checking
```

Cakupan verifikasi:

- **Validation cases** — hasil dibandingkan dengan **hitungan tangan** untuk grup 4-tiang simetris (mis. `P1 aksial = 714.88 kN`), memakai `np.isclose` (bukan `==`).
- **Golden-file regression** — `tests/golden/*.csv` dikunci; setiap perubahan yang menggeser angka akan terdeteksi.
- **Fail-fast** — memastikan input rusak benar-benar `raise`, bukan menghasilkan NaN diam-diam.
- **Integration** — menjalankan pipeline CLI end-to-end dan memeriksa semua artefak output + `run_manifest.json`.

Fixture test sengaja dipisah di `tests/data/` sehingga mengubah data di `input/` **tidak** memecahkan test.

---

## 13. Batasan & asumsi

- **Pilecap dianggap kaku sempurna** (semua tiang berbagi bidang perpindahan yang sama) — tanpa interaksi tanah-struktur atau variasi kekakuan antar tiang.
- **Berat tanah** dihitung memakai luas penuh pilecap (konservatif) — pengurangan luas pier belum diterapkan (`TODO` di `math_engine.calc_soil_weight`).
- Model bersifat elastis linier; tidak mencakup analisis daya dukung tanah atau kapasitas geoteknik tiang. **Capacity check** membandingkan gaya hasil dengan kapasitas **izin** yang Anda input (bukan menghitung kapasitas tiang itu sendiri).
- Semua tiang berbagi satu bentuk/dimensi; belum mendukung ukuran tiang campuran atau tiang miring (batter).

---

## Versi

**v0.3** — Capacity check + DCR (basis kapasitas izin, verdict OK/INADEQUATE);
koreksi product-of-inertia (Ixy) untuk grup asimetris dengan toggle; Excel
(`.xlsx`) import/export; metadata proyek di laporan PDF.

**v0.2** — Menambahkan CLI penuh (matplotlib + PDF Typst) di atas inti bersama `src/pile_forces/`, di samping aplikasi Streamlit. Satuan internal kN·m dipertahankan agar hasil identik dengan v0.1.

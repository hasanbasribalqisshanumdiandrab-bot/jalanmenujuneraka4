#!/usr/bin/env python3
"""
materi_sync.py  -  Baca PDF / gambar / PPTX -> teks (OCR) -> data pencarian -> (opsional) upload GitHub.

Tanpa backend. Cukup jalan di PC Anda. Hanya file BARU/BERUBAH yang di-OCR (cache),
jadi saat ada updatan prosesnya cepat. File kembar (isi sama) otomatis dibuang.

Pasang sekali:
    pip install pytesseract pillow python-pptx requests
    # Tesseract OCR + bahasa Indonesia:
    #   Windows: https://github.com/UB-Mannheim/tesseract/wiki  (centang "Indonesian" saat install)
    #   Linux:   sudo apt install tesseract-ocr tesseract-ocr-ind poppler-utils
    # PDF butuh poppler (pdftoppm): Windows -> https://github.com/oschwartz10612/poppler-windows (tambahkan ke PATH)

Pakai:
    python materi_sync.py                       # proses folder ./materi -> data/materi.json + data/materi.js
    python materi_sync.py --watch               # terus memantau; ada file baru -> otomatis proses
    python materi_sync.py --push --repo USER/REPO --watch
         (token GitHub lewat env GITHUB_TOKEN, izin Contents: Read & write)
"""
import argparse, hashlib, io, json, os, re, shutil, subprocess, sys, tempfile, time, base64
from datetime import datetime
from pathlib import Path

try:
    import pytesseract
    from PIL import Image, ImageOps
except ImportError:
    sys.exit("Pasang dulu: pip install pytesseract pillow python-pptx requests")

IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
HERE = Path.cwd()   # semua folder default relatif ke tempat skrip dijalankan


def natural_key(p):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", str(p))]


def sha1(b):
    return hashlib.sha1(b).hexdigest()


# ---------------------------------------------------------------- OCR
def ocr_image(img, lang, psm):
    img = ImageOps.exif_transpose(img).convert("L")
    if img.width < 1800:                       # perbesar foto kecil supaya OCR lebih akurat
        k = 1800 / img.width
        img = img.resize((int(img.width * k), int(img.height * k)), Image.LANCZOS)
    img = ImageOps.autocontrast(img)
    txt = pytesseract.image_to_string(img, lang=lang, config=f"--psm {psm}")
    return clean(txt)


def save_img(blob, path, maxw=1400):
    """Simpan gambar halaman (JPEG ringan) agar bisa ditampilkan di hasil pencarian."""
    if path.exists():
        return
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(blob))).convert("RGB")
    if im.width > maxw:
        im = im.resize((maxw, int(im.height * maxw / im.width)), Image.LANCZOS)
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, "JPEG", quality=72, optimize=True)


def clean(t):
    t = t.replace("\x0c", "\n")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


# ---------------------------------------------------------------- Pembaca sumber
def pages_from_file(path):
    """Hasilkan (halaman, bytes_gambar | None, teks_langsung | None)."""
    ext = path.suffix.lower()
    if ext in IMG_EXT:
        yield 1, path.read_bytes(), None
    elif ext == ".pdf":
        # coba teks asli dulu; kalau kosong (hasil scan) -> render halaman lalu OCR
        txts = []
        if shutil.which("pdftotext"):
            out = subprocess.run(["pdftotext", "-layout", str(path), "-"],
                                 capture_output=True, text=True).stdout
            txts = out.split("\x0c")
        if shutil.which("pdftoppm") is None:
            sys.exit("pdftoppm (poppler) tidak ditemukan; dibutuhkan untuk membaca PDF.")
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(["pdftoppm", "-r", "200", "-png", str(path), f"{td}/p"], check=True)
            for i, f in enumerate(sorted(Path(td).glob("p*.png"), key=natural_key), 1):
                native = txts[i - 1].strip() if i - 1 < len(txts) else ""
                if len(native) > 80:
                    yield i, None, native
                else:
                    yield i, f.read_bytes(), None
    elif ext == ".pptx":
        from pptx import Presentation
        from pptx.enum.shapes import MSO_SHAPE_TYPE
        prs = Presentation(str(path))

        def walk(shapes):
            for sh in shapes:
                if sh.shape_type == MSO_SHAPE_TYPE.GROUP:
                    yield from walk(sh.shapes)
                else:
                    yield sh
        for i, slide in enumerate(prs.slides, 1):
            texts, imgs = [], []
            for sh in walk(slide.shapes):
                if sh.has_text_frame and sh.text_frame.text.strip():
                    texts.append(sh.text_frame.text.strip())
                if getattr(sh, "has_table", False) and sh.has_table:
                    for r in sh.table.rows:
                        texts.append(" | ".join(c.text.strip() for c in r.cells))
                if sh.shape_type == MSO_SHAPE_TYPE.PICTURE:
                    imgs.append(sh.image.blob)
            native = "\n".join(texts)
            if imgs:
                for b in imgs:
                    yield i, b, native or None
                    native = None
            elif native:
                yield i, None, native


# ---------------------------------------------------------------- Proses
def build(args):
    src = Path(args.input)
    src.mkdir(parents=True, exist_ok=True)
    cache_f = Path(args.cache)
    cache = json.loads(cache_f.read_text("utf-8")) if cache_f.exists() else {}
    files = sorted((p for p in src.rglob("*")
                    if p.is_file() and not p.name.startswith("~")
                    and (p.suffix.lower() in IMG_EXT | {".pdf", ".pptx"})), key=natural_key)

    imgdir = Path(args.images or Path(args.out) / "img")
    items, seen, new_ocr = [], set(), 0
    for f in files:
        for page, blob, native in pages_from_file(f):
            key = sha1(blob) if blob else sha1((native or "").encode())
            if key in seen:                         # duplikat isi -> lewati
                continue
            seen.add(key)
            if key in cache:
                text = cache[key]
            else:
                text = native or ""
                if blob:
                    t = ocr_image(Image.open(io.BytesIO(blob)), args.lang, args.psm)
                    text = (native + "\n" + t).strip() if native else t
                cache[key] = text
                new_ocr += 1
                print(f"  OCR  {f.name} hal.{page}  ({len(text)} huruf)")
            if len(text) >= args.min_chars:
                it = {"id": key[:10], "sumber": f.stem, "hal": page, "teks": text}
                if blob:
                    save_img(blob, imgdir / f"{key[:10]}.jpg")
                    it["img"] = f"img/{key[:10]}.jpg"
                items.append(it)

    keep = {Path(i["img"]).name for i in items if "img" in i}
    if imgdir.exists():
        for old in imgdir.glob("*.jpg"):      # buang gambar halaman yang sudah dihapus dari materi/
            if old.name not in keep:
                old.unlink()
    cache_f.write_text(json.dumps(cache, ensure_ascii=False), "utf-8")
    data = {"dibangun": datetime.now().isoformat(timespec="seconds"),
            "jumlah": len(items), "items": items}
    return data, new_ocr


def write_outputs(data, outdir):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    body = {"jumlah": data["jumlah"], "items": data["items"]}      # tanpa 'dibangun' -> tidak ada commit sia-sia
    js = json.dumps(body, ensure_ascii=False, indent=1)
    (out / "materi.json").write_text(js, "utf-8")
    (out / "materi.js").write_text("window.MATERI = " + js + ";\n", "utf-8")
    return [out / "materi.json", out / "materi.js"]


# ---------------------------------------------------------------- Upload GitHub
def gh_put(repo, branch, token, remote_path, local_path):
    import requests
    url = f"https://api.github.com/repos/{repo}/contents/{remote_path}"
    h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    content = Path(local_path).read_bytes()
    r = requests.get(url, headers=h, params={"ref": branch}, timeout=30)
    sha = None
    if r.status_code == 200:
        sha = r.json()["sha"]
        if base64.b64decode(r.json()["content"]) == content:
            print(f"  = {remote_path} tidak berubah, dilewati")
            return False
    elif r.status_code != 404:
        sys.exit(f"GitHub error {r.status_code}: {r.text[:200]}")
    body = {"message": f"update materi {datetime.now():%Y-%m-%d %H:%M}",
            "content": base64.b64encode(content).decode(), "branch": branch}
    if sha:
        body["sha"] = sha
    r = requests.put(url, headers=h, json=body, timeout=60)
    if r.status_code not in (200, 201):
        sys.exit(f"Gagal upload {remote_path}: {r.status_code} {r.text[:200]}")
    print(f"  ↑ {remote_path} terupload")
    return True


def run_once(args):
    print(f"[{datetime.now():%H:%M:%S}] memindai {args.input} …")
    data, n = build(args)
    paths = write_outputs(data, args.out)
    print(f"  {data['jumlah']} halaman siap dicari ({n} baru di-OCR)")
    if args.push:
        token = os.environ.get("GITHUB_TOKEN")
        if not token or not args.repo:
            sys.exit("Untuk --push isi --repo USER/REPO dan env GITHUB_TOKEN.")
        for p in paths:
            gh_put(args.repo, args.branch, token, f"{args.remote_dir}/{p.name}", p)
        for p in sorted((Path(args.images or Path(args.out) / "img")).glob("*.jpg")):
            gh_put(args.repo, args.branch, token, f"{args.remote_dir}/img/{p.name}", p)


def main():
    ap = argparse.ArgumentParser(description="PDF/gambar/PPTX -> data pencarian soal")
    ap.add_argument("--input", default=str(HERE / "materi"), help="folder PDF/gambar/PPTX")
    ap.add_argument("--out", default=str(HERE / "data"), help="folder keluaran")
    ap.add_argument("--images", help="folder gambar halaman (default: <out>/img)")
    ap.add_argument("--cache", default=str(HERE / ".ocr_cache.json"))
    ap.add_argument("--lang", default="ind+eng", help="bahasa Tesseract")
    ap.add_argument("--psm", type=int, default=6, help="6=blok/tabel, 4=kolom, 3=otomatis")
    ap.add_argument("--min-chars", type=int, default=15)
    ap.add_argument("--tessdata", help="folder tessdata (opsional)")
    ap.add_argument("--tesseract-cmd", help="path tesseract.exe (opsional, Windows)")
    ap.add_argument("--watch", action="store_true", help="pantau folder, proses otomatis bila ada update")
    ap.add_argument("--interval", type=int, default=15, help="detik antar pengecekan")
    ap.add_argument("--push", action="store_true", help="upload hasil ke GitHub")
    ap.add_argument("--repo", help="USER/REPO")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--remote-dir", default="data", help="folder tujuan di repo")
    args = ap.parse_args()

    if args.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = args.tesseract_cmd
    if args.tessdata:
        os.environ["TESSDATA_PREFIX"] = args.tessdata
    try:
        langs = pytesseract.get_languages()
        if "ind" not in langs and "ind" in args.lang:
            print("! Bahasa Indonesia belum terpasang di Tesseract, pakai 'eng'.")
            args.lang = "eng"
    except Exception as e:
        sys.exit(f"Tesseract tidak ditemukan: {e}")

    run_once(args)
    if not args.watch:
        return
    print(f"Memantau {args.input} … (Ctrl+C untuk berhenti)")

    def snap():
        return sorted((str(p), p.stat().st_mtime, p.stat().st_size)
                      for p in Path(args.input).rglob("*") if p.is_file())
    last = snap()
    while True:
        time.sleep(args.interval)
        cur = snap()
        if cur != last:
            time.sleep(3)                      # tunggu file selesai disalin
            last = snap()
            run_once(args)


if __name__ == "__main__":
    main()

"""
HumanEye ML Engine — Phase 2 Training Data Preparation
Downloads all datasets and places them in the correct folder structure.

Usage:
    # Download everything (recommended — run once and wait)
    python -m ml_engine.training.data_prepare --all

    # Download specific datasets only
    python -m ml_engine.training.data_prepare --ffhq --gan-faces --asvspoof --voxceleb

    # Check what's already downloaded
    python -m ml_engine.training.data_prepare --status

Datasets that need manual steps (form/registration):
    FaceForensics++  → run: python -m ml_engine.training.data_prepare --ff-instructions
    VoxCeleb2        → run: python -m ml_engine.training.data_prepare --vox-instructions

Everything else downloads automatically.

Requirements:
    pip install requests tqdm kaggle Pillow gdown
"""

import argparse
import hashlib
import os
import sys
import time
import zipfile
import tarfile
import shutil
import logging
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Base paths ────────────────────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).parent
DATA_DIR     = SCRIPT_DIR / "data"
FF_DIR       = DATA_DIR / "faceforensics"
DFDC_DIR     = DATA_DIR / "dfdc"
FFHQ_DIR     = DATA_DIR / "ffhq" / "images"
GAN_DIR      = DATA_DIR / "gan_faces"
ASV_DIR      = DATA_DIR / "asvspoof2019" / "LA"
VOX_DIR      = DATA_DIR / "voxceleb" / "wav"


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def file_size_mb(path: Path) -> float:
    return path.stat().st_size / (1024 * 1024)


def download_file(url: str, dest: Path, desc: str = "") -> bool:
    """
    Stream-download url → dest with a tqdm progress bar.
    Returns True on success, False on failure.
    """
    try:
        import requests
        from tqdm import tqdm
    except ImportError:
        logger.error("Missing deps. Run: pip install requests tqdm")
        return False

    ensure_dir(dest.parent)
    tmp = dest.with_suffix(".tmp")

    try:
        r = requests.get(url, stream=True, timeout=30)
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))

        with open(tmp, "wb") as f, tqdm(
            desc=desc or dest.name,
            total=total,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
        ) as bar:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
                bar.update(len(chunk))

        tmp.rename(dest)
        logger.info(f"✓  {dest.name}  ({file_size_mb(dest):.1f} MB)")
        return True

    except Exception as e:
        logger.error(f"Download failed: {url}\n  {e}")
        if tmp.exists():
            tmp.unlink()
        return False


def extract_zip(zip_path: Path, dest: Path, remove_after: bool = True):
    logger.info(f"Extracting {zip_path.name} → {dest}")
    ensure_dir(dest)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(dest)
    if remove_after:
        zip_path.unlink()
    logger.info(f"✓  Extracted to {dest}")


def extract_tar(tar_path: Path, dest: Path, remove_after: bool = True):
    logger.info(f"Extracting {tar_path.name} → {dest}")
    ensure_dir(dest)
    with tarfile.open(tar_path) as t:
        t.extractall(dest)
    if remove_after:
        tar_path.unlink()
    logger.info(f"✓  Extracted to {dest}")


# ─────────────────────────────────────────────────────────────────────────────
#  DATASET 1 — FFHQ thumbnails  (real faces for GAN detector)
#  70,000 real face thumbnails (128×128)  ~2.5 GB
# ─────────────────────────────────────────────────────────────────────────────

FFHQ_GDRIVE_ID = "1WvlAIvuochQn_L_f9p3OdFdTiSLR5ovU"   # thumbnails128x128.zip

def download_ffhq():
    dest_zip = DATA_DIR / "ffhq_thumbnails.zip"

    if (FFHQ_DIR / "00000").exists():
        logger.info("FFHQ already downloaded — skipping.")
        return

    logger.info("── FFHQ thumbnails (real faces, ~2.5 GB) ──")
    try:
        import gdown
    except ImportError:
        logger.error("Run: pip install gdown")
        return

    ensure_dir(DATA_DIR)
    gdown.download(
        f"https://drive.google.com/uc?id={FFHQ_GDRIVE_ID}",
        str(dest_zip),
        quiet=False,
    )

    if dest_zip.exists():
        extract_zip(dest_zip, FFHQ_DIR.parent)
        # gdown extracts as thumbnails128x128/ — rename to images/
        extracted = FFHQ_DIR.parent / "thumbnails128x128"
        if extracted.exists() and not FFHQ_DIR.exists():
            extracted.rename(FFHQ_DIR)
        logger.info(f"✓  FFHQ saved to {FFHQ_DIR}")
    else:
        logger.error("FFHQ download failed. Try manually: https://github.com/NVlabs/ffhq-dataset")


# ─────────────────────────────────────────────────────────────────────────────
#  DATASET 2 — ThisPersonDoesNotExist  (GAN-generated faces)
#  Scrape 5,000 GAN faces  ~1.5 GB
# ─────────────────────────────────────────────────────────────────────────────

def download_gan_faces(count: int = 5000):
    ensure_dir(GAN_DIR)

    existing = list(GAN_DIR.glob("*.jpg"))
    if len(existing) >= count:
        logger.info(f"GAN faces already downloaded ({len(existing)} files) — skipping.")
        return

    start_idx = len(existing)
    logger.info(f"── GAN faces via ThisPersonDoesNotExist ({count - start_idx} to download) ──")

    try:
        import requests
        from PIL import Image
        from io import BytesIO
        from tqdm import tqdm
    except ImportError:
        logger.error("Run: pip install requests Pillow tqdm")
        return

    success = start_idx
    errors = 0

    with tqdm(total=count - start_idx, desc="GAN faces") as bar:
        for i in range(start_idx, count):
            try:
                r = requests.get(
                    "https://thispersondoesnotexist.com",
                    timeout=15,
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                r.raise_for_status()
                img = Image.open(BytesIO(r.content))
                img.save(GAN_DIR / f"{i:05d}.jpg", quality=95)
                success += 1
                errors = 0
                bar.update(1)
                time.sleep(1.0)   # 1 req/sec — be respectful

            except Exception as e:
                errors += 1
                logger.warning(f"  Skip {i}: {e}")
                if errors > 10:
                    logger.error("Too many consecutive errors — stopping GAN face download.")
                    break
                time.sleep(3)

    logger.info(f"✓  {success} GAN faces saved to {GAN_DIR}")


# ─────────────────────────────────────────────────────────────────────────────
#  DATASET 3 — ASVspoof 2019 LA  (voice clone detection)
#  Real voices + TTS/voice-conversion attacks  ~8 GB
# ─────────────────────────────────────────────────────────────────────────────

ASVSPOOF_ZENODO_URL = "https://zenodo.org/record/4837263/files/LA.zip"

def download_asvspoof():
    dest_zip = DATA_DIR / "asvspoof2019_LA.zip"

    if (ASV_DIR / "ASVspoof2019_LA_train").exists():
        logger.info("ASVspoof 2019 LA already downloaded — skipping.")
        return

    logger.info("── ASVspoof 2019 LA (voice dataset, ~8 GB) ──")
    ok = download_file(ASVSPOOF_ZENODO_URL, dest_zip, "ASVspoof 2019 LA")

    if ok and dest_zip.exists():
        extract_zip(dest_zip, ASV_DIR.parent.parent)
        logger.info(f"✓  ASVspoof saved to {ASV_DIR}")
    else:
        logger.error(
            "ASVspoof download failed. Manual fallback:\n"
            "  1. Go to https://datashares.asvspoof.org\n"
            "  2. Register (free)\n"
            f"  3. Download LA.zip and extract to {ASV_DIR.parent.parent}"
        )


# ─────────────────────────────────────────────────────────────────────────────
#  DATASET 4 — VoxCeleb1  (real voices baseline)
#  1,251 speakers, ~4.5 GB
# ─────────────────────────────────────────────────────────────────────────────

# VoxCeleb1 is split into 4 part files — combine then extract
# URLs from PyTorch torchaudio official source (no registration needed)
VOXCELEB1_PART_URLS = [
    "https://thor.robots.ox.ac.uk/~vgg/data/voxceleb/vox1a/vox1_dev_wav_partaa",
    "https://thor.robots.ox.ac.uk/~vgg/data/voxceleb/vox1a/vox1_dev_wav_partab",
    "https://thor.robots.ox.ac.uk/~vgg/data/voxceleb/vox1a/vox1_dev_wav_partac",
    "https://thor.robots.ox.ac.uk/~vgg/data/voxceleb/vox1a/vox1_dev_wav_partad",
]


def download_voxceleb():
    """
    Fully automatic. No registration, no URL needed.
    Downloads 4 part files (~1.1 GB each) and combines into one zip.
    Total: ~4.5 GB.
    """
    if VOX_DIR.exists() and any(VOX_DIR.rglob("*.wav")):
        wav_count = len(list(VOX_DIR.rglob("*.wav")))
        logger.info(f"VoxCeleb1 already downloaded ({wav_count} wav files) — skipping.")
        return

    logger.info("── VoxCeleb1 (real voices, ~4.5 GB — 4 part files) ──")
    ensure_dir(DATA_DIR)

    # Step 1: Download all 4 part files
    part_paths = []
    for i, url in enumerate(VOXCELEB1_PART_URLS):
        part_name = url.split("/")[-1]
        dest = DATA_DIR / part_name
        if dest.exists():
            logger.info(f"  Part {i+1}/4 already exists — skipping.")
        else:
            ok = download_file(url, dest, f"VoxCeleb1 part {i+1}/4")
            if not ok:
                logger.error(
                    f"Part {i+1} download failed.\n"
                    "If you see connection refused, the server may require registration.\n"
                    "Fill form at: https://www.robots.ox.ac.uk/~vgg/data/voxceleb/vox1.html\n"
                    "Then re-run with: python -m ml.training.data_prepare --voxceleb-url <url>"
                )
                return
        part_paths.append(dest)

    # Step 2: Combine parts into one zip
    combined_zip = DATA_DIR / "vox1_dev_wav.zip"
    if not combined_zip.exists():
        logger.info("Combining 4 part files into vox1_dev_wav.zip ...")
        with open(combined_zip, "wb") as out:
            for part in part_paths:
                logger.info(f"  Appending {part.name} ...")
                with open(part, "rb") as p:
                    out.write(p.read())
        logger.info(f"✓  Combined: {combined_zip} ({file_size_mb(combined_zip):.0f} MB)")

    # Step 3: Extract
    logger.info("Extracting audio files ...")
    extract_zip(combined_zip, VOX_DIR.parent, remove_after=True)

    # Step 4: Clean up part files
    for part in part_paths:
        if part.exists():
            part.unlink()

    wav_count = len(list(VOX_DIR.rglob("*.wav")))
    logger.info(f"✓  VoxCeleb1 ready: {wav_count} wav files at {VOX_DIR}")


def download_voxceleb_with_url(url: str):
    """Fallback in case auto-download fails — user provides direct URL."""
    ensure_dir(VOX_DIR)
    dest = DATA_DIR / "voxceleb1.zip"
    ok = download_file(url, dest, "VoxCeleb1")
    if ok:
        extract_zip(dest, VOX_DIR.parent)
        logger.info(f"✓  VoxCeleb1 saved to {VOX_DIR}")


# ─────────────────────────────────────────────────────────────────────────────
#  DATASET 5 — DFDC sample  (deepfake videos)
#  ~3.9 GB preview dataset via Kaggle
# ─────────────────────────────────────────────────────────────────────────────

def download_dfdc():
    if (DFDC_DIR / "train").exists() or (DFDC_DIR / "dfdc_train_part_0").exists():
        logger.info("DFDC already downloaded — skipping.")
        return

    logger.info("── DFDC preview dataset (deepfake videos, ~3.9 GB) ──")

    kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
    if not kaggle_json.exists():
        logger.warning(
            "Kaggle credentials not found. To download DFDC:\n"
            "  1. Go to https://www.kaggle.com/settings → API → Create New Token\n"
            "  2. Move the downloaded kaggle.json to ~/.kaggle/kaggle.json\n"
            "  3. Re-run this script with --dfdc\n\n"
            "Skipping DFDC for now — other datasets will still download."
        )
        return

    try:
        import kaggle
        ensure_dir(DFDC_DIR)
        kaggle.api.authenticate()
        kaggle.api.dataset_download_files(
            "selfishgene/dfdc-preview-dataset",
            path=str(DFDC_DIR),
            unzip=True,
        )
        logger.info(f"✓  DFDC saved to {DFDC_DIR}")
    except Exception as e:
        logger.error(f"DFDC download failed: {e}")
        logger.info(
            "Manual fallback:\n"
            "  pip install kaggle\n"
            "  kaggle datasets download -d selfishgene/dfdc-preview-dataset\n"
            f"  unzip dfdc-preview-dataset.zip -d {DFDC_DIR}"
        )


# ─────────────────────────────────────────────────────────────────────────────
#  DATASET 6 — FaceForensics++  (requires form submission)
#  Deepfake + real videos  ~35 GB (c23 compression)
# ─────────────────────────────────────────────────────────────────────────────

def ff_instructions():
    logger.info(
        "\n"
        "═══════════════════════════════════════════════════════\n"
        "  FaceForensics++ — Manual Download Required\n"
        "═══════════════════════════════════════════════════════\n"
        "\n"
        "Step 1: Fill the access form (auto-approved in 1–2 days)\n"
        "  https://docs.google.com/forms/d/e/1FAIpQLSdRRR3L5zAv6tQ_CKxmK4W96tAab_pfBu2EKAgQbeDVhmXagg/viewform\n"
        "\n"
        "Step 2: They email you a download script. Then run:\n"
        "  python download-FaceForensics.py \\\n"
        f"    {FF_DIR} \\\n"
        "    -d all \\\n"
        "    -c c23 \\\n"
        "    -t videos\n"
        "\n"
        "  This downloads ~35 GB. Accept all prompts.\n"
        "\n"
        "Step 3: Verify the folder structure:\n"
        f"  {FF_DIR}/original_sequences/\n"
        f"  {FF_DIR}/manipulated_sequences/Deepfakes/\n"
        f"  {FF_DIR}/manipulated_sequences/Face2Face/\n"
        f"  {FF_DIR}/manipulated_sequences/FaceSwap/\n"
        "═══════════════════════════════════════════════════════\n"
    )


def vox_instructions():
    logger.info(
        "\n"
        "═══════════════════════════════════════════════════════\n"
        "  VoxCeleb1 — Now downloads automatically!\n"
        "═══════════════════════════════════════════════════════\n"
        "\n"
        "Just run:\n"
        "  python -m ml.training.data_prepare --voxceleb\n"
        "\n"
        "Downloads 4 part files (~1.1 GB each) and combines them.\n"
        "No registration needed.\n"
        "\n"
        "If it fails (server connection refused):\n"
        "  1. Go to: https://www.robots.ox.ac.uk/~vgg/data/voxceleb/vox1.html\n"
        "  2. Register and get download URL\n"
        "  3. Run: python -m ml.training.data_prepare --voxceleb-url <URL>\n"
        "═══════════════════════════════════════════════════════\n"
    )


# ─────────────────────────────────────────────────────────────────────────────
#  STATUS CHECK
# ─────────────────────────────────────────────────────────────────────────────

def check_status():
    datasets = [
        ("FFHQ (real faces)",        FFHQ_DIR,                    "2.5 GB",  "auto"),
        ("GAN faces (fake)",         GAN_DIR,                     "1.5 GB",  "auto"),
        ("ASVspoof 2019 LA",         ASV_DIR / "ASVspoof2019_LA_train", "8 GB", "auto"),
        ("VoxCeleb1 (real voices)",  VOX_DIR,                     "4.5 GB",  "manual URL"),
        ("DFDC preview",             DFDC_DIR,                    "3.9 GB",  "Kaggle"),
        ("FaceForensics++",          FF_DIR / "original_sequences", "35 GB", "form"),
    ]

    print("\n" + "═" * 65)
    print(f"  {'Dataset':<30} {'Status':<12} {'Size':<10} {'Method'}")
    print("─" * 65)

    total_downloaded = 0
    for name, path, size, method in datasets:
        if path.exists() and any(path.rglob("*")):
            # Count files
            files = list(path.rglob("*.*"))
            status = f"✓  {len(files)} files"
            mb = sum(f.stat().st_size for f in files) / (1024**2)
            total_downloaded += mb
        else:
            status = "✗  missing"

        print(f"  {name:<30} {status:<12} {size:<10} {method}")

    print("─" * 65)
    print(f"  Total downloaded: {total_downloaded / 1024:.1f} GB")
    print("═" * 65 + "\n")

    print("To download missing datasets:")
    print("  python -m ml_engine.training.data_prepare --all\n")
    print("For datasets requiring manual steps:")
    print("  python -m ml_engine.training.data_prepare --ff-instructions")
    print("  python -m ml_engine.training.data_prepare --vox-instructions\n")


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="HumanEye Phase 2 — Download all training datasets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m ml_engine.training.data_prepare --all
  python -m ml_engine.training.data_prepare --ffhq --gan-faces
  python -m ml_engine.training.data_prepare --asvspoof --dfdc
  python -m ml_engine.training.data_prepare --status
  python -m ml_engine.training.data_prepare --ff-instructions
  python -m ml_engine.training.data_prepare --vox-instructions
  python -m ml_engine.training.data_prepare --voxceleb-url https://...
        """,
    )

    parser.add_argument("--all",            action="store_true", help="Download all auto-downloadable datasets")
    parser.add_argument("--ffhq",           action="store_true", help="FFHQ real face thumbnails (~2.5 GB)")
    parser.add_argument("--gan-faces",      action="store_true", help="Scrape GAN faces from TPDNE (~1.5 GB)")
    parser.add_argument("--gan-count",      type=int, default=5000, help="Number of GAN faces to scrape (default: 5000)")
    parser.add_argument("--asvspoof",       action="store_true", help="ASVspoof 2019 LA voice dataset (~8 GB)")
    parser.add_argument("--voxceleb",       action="store_true", help="Show VoxCeleb1 download instructions")
    parser.add_argument("--voxceleb-url",   type=str,            help="Provide direct VoxCeleb1 download URL")
    parser.add_argument("--dfdc",           action="store_true", help="DFDC preview via Kaggle (~3.9 GB)")
    parser.add_argument("--ff-instructions",action="store_true", help="Show FaceForensics++ access instructions")
    parser.add_argument("--vox-instructions",action="store_true",help="Show VoxCeleb1 URL instructions")
    parser.add_argument("--status",         action="store_true", help="Show download status of all datasets")

    args = parser.parse_args()

    # No args → show status
    if len(sys.argv) == 1:
        check_status()
        sys.exit(0)

    if args.status:
        check_status()

    if args.ff_instructions:
        ff_instructions()

    if args.vox_instructions:
        vox_instructions()

    if args.voxceleb_url:
        download_voxceleb_with_url(args.voxceleb_url)

    if args.all or args.ffhq:
        download_ffhq()

    if args.all or args.gan_faces:
        download_gan_faces(count=args.gan_count)

    if args.all or args.asvspoof:
        download_asvspoof()

    if args.all or args.dfdc:
        download_dfdc()

    if args.all or args.voxceleb:
        download_voxceleb()   # Shows instructions — can't auto-download without URL

    if args.all:
        print("\n" + "═" * 55)
        print("  Auto-downloadable datasets complete.")
        print("  For the remaining two, run:")
        print("  python -m ml_engine.training.data_prepare --ff-instructions")
        print("  python -m ml_engine.training.data_prepare --vox-instructions")
        print("═" * 55 + "\n")
        check_status()
import os, sys, json, shutil, subprocess, tempfile
from audio_separator.separator import Separator

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT_DIR, "config.json")

def get_stems_base_dir():
    cfg = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            pass
    if "stems_output_dir" not in cfg:
        cfg["stems_output_dir"] = os.path.join(ROOT_DIR, "output", "stems")
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    os.makedirs(cfg["stems_output_dir"], exist_ok=True)
    return cfg["stems_output_dir"]

raw_path = sys.argv[1] if len(sys.argv) > 1 else input("Drag & drop audio/video file here (or paste path): ")
in_path = raw_path.strip().strip('"').strip("'")

if not os.path.isfile(in_path):
    print(f"File not found: {in_path}")
    sys.exit(1)

base_name = os.path.splitext(os.path.basename(in_path))[0]
out_dir = os.path.join(get_stems_base_dir(), base_name)
os.makedirs(out_dir, exist_ok=True)
temp_dir = tempfile.mkdtemp(prefix="iso_")

def run_sep(input_file, model_name):
    sep = Separator(output_dir=temp_dir, output_format="WAV", mdx_params={"batch_size": 8, "overlap": 2})
    sep.load_model(model_filename=model_name)
    return [os.path.join(temp_dir, os.path.basename(f)) for f in sep.separate(input_file)]

try:
    print("\n[0/3] Extracting audio track with FFmpeg...")
    step0 = os.path.join(temp_dir, "step0.wav")
    subprocess.run(
        ["ffmpeg", "-y", "-i", in_path, "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", step0],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
    )

    print("\n[1/3] Removing music & heavy background noise (BS-Roformer)...")
    s1 = run_sep(step0, "model_bs_roformer_ep_317_sdr_12.9755.ckpt")
    step1 = os.path.join(temp_dir, "step1.wav")
    os.replace(next(f for f in s1 if "(Vocals)" in f), step1)

    print("\n[2/3] Removing static & room noise (UVR-DeNoise)...")
    s2 = run_sep(step1, "UVR-DeNoise.pth")
    step2 = os.path.join(temp_dir, "step2.wav")
    os.replace(next(f for f in s2 if "(No Noise)" in f), step2)
    shutil.copy2(step2, os.path.join(out_dir, f"{base_name} - 1_All_Voices_Clean.wav"))

    print("\n[3/3] Splitting foreground vs. background voices...")
    s3 = run_sep(step2, "mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt")
    lead_voice = next(f for f in s3 if "(Vocals)" in f)
    other_voices = next(f for f in s3 if "(Instrumental)" in f)

    shutil.copy2(lead_voice, os.path.join(out_dir, f"{base_name} - 2_Lead_Voice.wav"))
    shutil.copy2(other_voices, os.path.join(out_dir, f"{base_name} - 3_Secondary_Voices.wav"))

    print(f"\nDone! Clean isolated tracks saved to:\n{out_dir}")
finally:
    shutil.rmtree(temp_dir, ignore_errors=True)

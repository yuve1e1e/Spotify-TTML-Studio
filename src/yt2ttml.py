import os, re, sys, json, shutil, tempfile, difflib, argparse, subprocess, html, requests, torch, whisperx
from audio_separator.separator import Separator

torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT_DIR, "config.json")

def get_out_dir(key, default_sub):
    cfg = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            pass
    if key not in cfg:
        cfg[key] = os.path.join(ROOT_DIR, "output", default_sub)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    os.makedirs(cfg[key], exist_ok=True)
    return cfg[key]

parser = argparse.ArgumentParser()
parser.add_argument("--title", default="")
parser.add_argument("--duration", type=float, default=0.0)
parser.add_argument("--hard", action="store_true")
args = parser.parse_args()

if args.title:
    track_title = args.title.strip()
    target_dur = args.duration if args.duration > 0 else None
    hard_mode = args.hard
    raw_url = ""
else:
    raw_url = input("Paste YouTube or Spotify URL: ").strip()
    hard_mode = input("Hard mode for difficult songs? (y/N): ").strip().lower() == "y"
    track_title = None
    target_dur = None

out_dir = get_out_dir("ttml_output_dir", "ttml")
lang = "en"

def find_track_entity(obj):
    if isinstance(obj, dict):
        if "name" in obj and "artists" in obj and isinstance(obj["artists"], list) and ("duration" in obj or "duration_ms" in obj):
            return obj
        for v in obj.values():
            res = find_track_entity(v)
            if res:
                return res
    elif isinstance(obj, list):
        for item in obj:
            res = find_track_entity(item)
            if res:
                return res
    return None

if not track_title and "open.spotify.com" in raw_url and "/track/" in raw_url:
    track_id = raw_url.split("/track/")[1].split("?")[0].split("/")[0]
    print("Fetching track info & exact duration from Spotify...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"}
    s_song, s_artist = None, None
    try:
        emb = requests.get(f"https://open.spotify.com/embed/track/{track_id}", headers=headers, timeout=10).text
        m_next = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', emb, re.S)
        if m_next:
            entity = find_track_entity(json.loads(m_next.group(1)))
            if entity:
                s_song = entity.get("name")
                s_artist = ", ".join(a["name"] for a in entity.get("artists", []) if "name" in a)
                dur_ms = entity.get("duration") or entity.get("duration_ms")
                if dur_ms:
                    target_dur = float(dur_ms) / 1000.0
    except Exception:
        pass
    if not s_song:
        raise RuntimeError("Could not read Spotify track metadata.")
    track_title = f"{s_artist} - {s_song}" if s_artist else s_song

if track_title:
    dur_str = f" ({int(target_dur // 60)}:{int(target_dur % 60):02d})" if target_dur else ""
    print(f"Matching YouTube audio for: {track_title}{dur_str}")
    search_out = subprocess.check_output(
        ["yt-dlp", "--no-playlist", "--flat-playlist", "--print", "%(duration)s|%(id)s", f"ytsearch5:{track_title} audio"],
        text=True
    ).strip().splitlines()

    best_id, best_diff = None, 9999.0
    for row in search_out:
        parts = row.split("|", 1)
        if len(parts) == 2 and parts[1].strip():
            vid_id = parts[1].strip()
            try:
                diff = abs(float(parts[0]) - target_dur) if target_dur else 0.0
                if diff < best_diff:
                    best_diff, best_id = diff, vid_id
            except ValueError:
                if not best_id:
                    best_id = vid_id
    if not best_id:
        raise RuntimeError("No matching YouTube audio found.")
    url = f"https://www.youtube.com/watch?v={best_id}"
else:
    url = raw_url

title = track_title or subprocess.check_output(["yt-dlp", "--no-playlist", "--get-title", url], text=True).strip()
safe_title = "".join(c for c in title if c not in r'\/:*?"<>|').strip()
ttml_path = os.path.join(out_dir, f"{safe_title}.ttml")
temp_dir = tempfile.mkdtemp(prefix="ttml_")

def run_sep(in_wav, model_file, stem_tags, out_wav):
    sep = Separator(output_dir=temp_dir, output_format="WAV", mdx_params={"batch_size": 8, "overlap": 2})
    sep.load_model(model_filename=model_file)
    outputs = [os.path.join(temp_dir, os.path.basename(f)) for f in sep.separate(in_wav)]
    match = next((f for f in outputs if any(tag in f for tag in stem_tags) and os.path.exists(f)), None)
    if match:
        os.replace(match, out_wav)
        return out_wav
    return in_wav

synced_lrc = None
raw_lines = []
clean_query = re.sub(r"\(.*?\)|\[.*?\]|official\s*(music\s*)?video|lyrics?|audio", "", title, flags=re.I).strip()
print(f"Searching LRCLIB for: {clean_query}")
try:
    resp = requests.get("https://lrclib.net/api/search", params={"q": clean_query}, timeout=10)
    hits = resp.json() if resp.ok else []
    synced_lrc = next((h.get("syncedLyrics") for h in hits if h.get("syncedLyrics")), None)
    if synced_lrc:
        print("Found synced lyrics on LRCLIB!")
    else:
        plain = next((h.get("plainLyrics") for h in hits if h.get("plainLyrics")), None)
        if plain:
            raw_lines = [l.strip() for l in plain.splitlines() if l.strip()]
            print(f"Found {len(raw_lines)} plain lines on LRCLIB!")
except Exception as e:
    print(f"LRCLIB lookup skipped ({e})")

if not synced_lrc and not raw_lines:
    txt_path = input("No lyrics found on LRCLIB. Path to lyrics .txt (or press Enter for AI): ").strip().strip('"')
    if txt_path and os.path.exists(txt_path):
        with open(txt_path, "r", encoding="utf-8") as f:
            content = f.read()
        if re.search(r"^\[\d+:\d+", content, re.M):
            synced_lrc = content
        else:
            raw_lines = [l.strip() for l in content.splitlines() if l.strip() and not re.match(r"^\[.*\]$", l.strip())]

try:
    step0 = os.path.join(temp_dir, "step0.wav")
    subprocess.run(["yt-dlp", "--no-playlist", "-x", "--audio-format", "wav", "-o", step0, url], check=True)
    align_audio_path = step0

    try:
        print("[1/4] Isolating vocals with BS-Roformer on GPU...")
        align_audio_path = run_sep(align_audio_path, "model_bs_roformer_ep_317_sdr_12.9755.ckpt", ["(Vocals)"], os.path.join(temp_dir, "step1.wav"))

        if hard_mode:
            print("[2/4] Hard Mode: Isolating lead singer from backing vocals...")
            align_audio_path = run_sep(align_audio_path, "mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt", ["(Vocals)"], os.path.join(temp_dir, "step2.wav"))

            print("[3/4] Hard Mode: Stripping reverb & echo tails...")
            align_audio_path = run_sep(align_audio_path, "UVR-DeEcho-DeReverb.pth", ["(No Echo)", "(No Reverb)"], os.path.join(temp_dir, "step3.wav"))

            print("[4/4] Hard Mode: Removing residual noise...")
            align_audio_path = run_sep(align_audio_path, "UVR-DeNoise.pth", ["(No Noise)"], os.path.join(temp_dir, "step4.wav"))
    except Exception as e:
        print(f"Vocal processing step skipped ({e}), continuing...")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = "bfloat16" if (device == "cuda" and torch.cuda.is_bf16_supported()) else ("float16" if device == "cuda" else "int8")
    audio = whisperx.load_audio(align_audio_path)
    duration = len(audio) / 16000.0
    model_a, metadata = whisperx.load_align_model(language_code=lang, device=device, model_name="WAV2VEC2_ASR_LARGE_LV60K_960H")
    segments = []

    if synced_lrc:
        entries = []
        for line in synced_lrc.splitlines():
            m = re.match(r"^\[(\d+):(\d+(?:\.\d+)?)\]\s*(.*)$", line.strip())
            if m:
                entries.append((int(m.group(1)) * 60 + float(m.group(2)), m.group(3).strip()))
        non_empty = [(t, txt) for t, txt in entries if txt]
        if hard_mode and non_empty and abs(non_empty[-1][0] - duration) > 10.0:
            print("Hard Mode: Synced LRC length mismatches audio — re-anchoring lines via AI...")
            raw_lines = [txt for _, txt in non_empty]
        else:
            pad_max = 1.6 if hard_mode else 1.2
            for i, (t, txt) in enumerate(non_empty):
                prev_t = non_empty[i - 1][0] if i > 0 else 0.0
                next_t = non_empty[i + 1][0] if i + 1 < len(non_empty) else duration
                min_bound = (prev_t + t) / 2.0 if i > 0 else 0.0
                max_bound = (t + next_t) / 2.0 if i + 1 < len(non_empty) else duration
                pad_start = max(min_bound, t - pad_max)
                pad_end = min(max_bound, next_t + (pad_max * 0.5))
                if pad_end > pad_start:
                    segments.append({"text": txt, "start": pad_start, "end": pad_end})

    if not segments:
        vad_opts = {"vad_onset": 0.20, "vad_offset": 0.15} if hard_mode else {"vad_onset": 0.15, "vad_offset": 0.10}
        asr_opts = {
            "beam_size": 20 if hard_mode else 10,
            "best_of": 20 if hard_mode else 10,
            "patience": 4.0 if hard_mode else 2.0,
            "temperatures": [0.0, 0.2, 0.4, 0.6, 0.8, 1.0] if hard_mode else [0.0],
            "condition_on_previous_text": True,
            "initial_prompt": " ".join(raw_lines[:40]) if raw_lines else None,
            "no_speech_threshold": 0.85 if hard_mode else 1.0,
            "log_prob_threshold": None,
            "compression_ratio_threshold": 3.5 if hard_mode else 3.0,
        }
        model = whisperx.load_model("large-v3", device, compute_type=compute_type, vad_options=vad_opts, asr_options=asr_opts)
        result = model.transcribe(audio, batch_size=16, chunk_size=12 if hard_mode else 6, language=lang)

        if raw_lines and result["segments"]:
            ai_aligned = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)
            ai_words = []
            for seg in ai_aligned["segments"]:
                for w in seg.get("words", []):
                    if "start" in w and "end" in w:
                        tok = re.sub(r"[^\w']", "", w["word"].lower())
                        if tok:
                            ai_words.append((tok, w["start"], w["end"]))

            gt_words = []
            for li, line in enumerate(raw_lines):
                for raw_w in line.split():
                    tok = re.sub(r"[^\w']", "", raw_w.lower())
                    if tok:
                        gt_words.append((li, tok))

            if ai_words and gt_words:
                ai_toks = [w[0] for w in ai_words]
                gt_toks = [w[1] for w in gt_words]
                anchored = [None] * len(gt_words)
                sm = difflib.SequenceMatcher(None, ai_toks, gt_toks, autojunk=False)
                for tag, i1, i2, j1, j2 in sm.get_opcodes():
                    if tag == "equal":
                        for k in range(j2 - j1):
                            anchored[j1 + k] = (ai_words[i1 + k][1], ai_words[i1 + k][2])

                idx = 0
                while idx < len(anchored):
                    if anchored[idx] is None:
                        end_idx = idx
                        while end_idx < len(anchored) and anchored[end_idx] is None:
                            end_idx += 1
                        t0 = anchored[idx - 1][1] if idx > 0 else ai_words[0][1]
                        t1 = anchored[end_idx][0] if end_idx < len(anchored) else ai_words[-1][2]
                        span = max(0.05, t1 - t0)
                        cnt = end_idx - idx
                        for k in range(cnt):
                            anchored[idx + k] = (t0 + span * (k / cnt), t0 + span * ((k + 1) / cnt))
                        idx = end_idx
                    else:
                        idx += 1

                line_bounds = {}
                for (li, _), (ws, we) in zip(gt_words, anchored):
                    if li not in line_bounds:
                        line_bounds[li] = [ws, we]
                    else:
                        line_bounds[li][0] = min(line_bounds[li][0], ws)
                        line_bounds[li][1] = max(line_bounds[li][1], we)

                sorted_lis = sorted(line_bounds.keys())
                for pos, li in enumerate(sorted_lis):
                    s_t, e_t = line_bounds[li]
                    prev_e = line_bounds[sorted_lis[pos - 1]][1] if pos > 0 else 0.0
                    next_s = line_bounds[sorted_lis[pos + 1]][0] if pos + 1 < len(sorted_lis) else duration
                    p_start = max((prev_e + s_t) / 2.0 if pos > 0 else 0.0, s_t - 0.8)
                    p_end = min((e_t + next_s) / 2.0 if pos + 1 < len(sorted_lis) else duration, e_t + 0.8)
                    if p_end > p_start:
                        segments.append({"text": raw_lines[li], "start": p_start, "end": p_end})
            else:
                step = duration / max(len(raw_lines), 1)
                segments = [{"text": line, "start": i * step, "end": (i + 1) * step} for i, line in enumerate(raw_lines)]
        elif raw_lines:
            step = duration / max(len(raw_lines), 1)
            segments = [{"text": line, "start": i * step, "end": (i + 1) * step} for i, line in enumerate(raw_lines)]
        else:
            segments = result["segments"]

    aligned = whisperx.align(segments, model_a, metadata, audio, device, return_char_alignments=False)

    def fmt(sec):
        m, s = divmod(max(0.0, sec), 60)
        return f"{int(m):02d}:{s:06.3f}"

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<tt xmlns="http://www.w3.org/ns/ttml" xmlns:ttm="http://www.w3.org/ns/ttml#metadata" xmlns:itunes="http://music.apple.com/lyric-ttml-internal" itunes:timing="Word" xml:lang="{lang}">',
        '  <head><metadata><ttm:agent type="person" xml:id="v1"/></metadata></head>',
        '  <body><div>'
    ]

    for i, seg in enumerate(aligned["segments"], 1):
        words = [w for w in seg.get("words", []) if "start" in w and "end" in w]
        if not words:
            continue
        spans = " ".join(
            f'<span begin="{fmt(w["start"])}" end="{fmt(w["end"])}">{html.escape(w["word"].strip())}</span>'
            for w in words
        )
        lines.append(f'    <p begin="{fmt(words[0]["start"])}" end="{fmt(words[-1]["end"])}" ttm:agent="v1" itunes:key="L{i}">{spans}</p>')

    lines.extend(['  </div></body>', '</tt>'])

    with open(ttml_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\nSaved word-synced TTML to: {ttml_path}")
finally:
    shutil.rmtree(temp_dir, ignore_errors=True)

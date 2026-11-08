"""대본 검수 → TTS → 무음 트리밍·-14.9 LUFS 정규화 → 1080x1920 30fps 합성 → Whisper 대조 검수"""
import argparse, json, os, re, shutil, subprocess, sys, wave, difflib
from pathlib import Path
from gtts import gTTS

ROOT = Path(__file__).resolve().parent
W = ROOT / "build"                      # 중간 파일
OUT = ROOT / "output"                   # 결과 영상·검수 리포트
IMAGE = ROOT / "input" / "scene.webp"   # 장면 이미지
W.mkdir(exist_ok=True); OUT.mkdir(exist_ok=True)
ORIGINAL = "안녕 반가워 열심히 하고 있구나 잘 할수 있어 화이팅!"
# 1) 대본 검수 결과: 띄어쓰기·문장부호 교정, 자막 단위로 분할
LINES = ["안녕! 반가워!", "열심히 하고 있구나.", "잘할 수 있어.", "화이팅!"]
VOICE, SPEED = "Google TTS (ko)", 1.12
TARGET_LUFS, TP, LRA = -14.9, -1.5, 11
GAP, HEAD, TAIL = 0.30, 0.40, 0.80
FPS, OW, OH = 30, 1080, 1920

def sh(*a): return subprocess.run(a, check=True, capture_output=True, text=True, cwd=W)
def dur(p): return float(sh("ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",str(p)).stdout)

def tts():
    for i, t in enumerate(LINES):
        gTTS(t, lang="ko").save(str(W/f"raw_{i}.mp3"))

def trim(i):
    # 앞뒤 무음 제거(-45dB 기준) 후 48kHz 모노 wav
    rev = "areverse"
    f = f"atempo={SPEED},silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02,{rev},silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02,{rev}"
    sh("ffmpeg","-y","-v","error","-i",str(W/f"raw_{i}.mp3"),"-af",f,"-ar","48000","-ac","1",str(W/f"trim_{i}.wav"))
    return dur(W/f"trim_{i}.wav")

def main(upload_dir=None, rclone_dest=None, name="twin_cheer.mp4"):
    report = {"script_original": ORIGINAL, "script_reviewed": LINES,
              "review_notes": ["'잘 할수' → '잘할 수' (띄어쓰기: '잘하다'는 한 단어, 의존명사 '수'는 띄움)",
                               "문장 경계에 문장부호 추가, 자막 4줄로 분할",
                               "'화이팅'은 표준어로 '파이팅'이지만 원문 표현을 살려 유지"]}
    tts()
    # 2) 문장별 무음 트리밍 → 타이밍 계산 → 이어붙이기
    t, cues, parts = HEAD, [], []
    sh("ffmpeg","-y","-v","error","-f","lavfi","-i","anullsrc=r=48000:cl=mono","-t",str(GAP),str(W/"gap.wav"))
    sh("ffmpeg","-y","-v","error","-f","lavfi","-i","anullsrc=r=48000:cl=mono","-t",str(HEAD),str(W/"head.wav"))
    sh("ffmpeg","-y","-v","error","-f","lavfi","-i","anullsrc=r=48000:cl=mono","-t",str(TAIL),str(W/"tail.wav"))
    parts.append("head.wav")
    for i, line in enumerate(LINES):
        d = trim(i)
        cues.append((t, t + d, line)); t += d
        parts.append(f"trim_{i}.wav")
        if i < len(LINES) - 1: parts.append("gap.wav"); t += GAP
    parts.append("tail.wav"); total = t + TAIL
    (W/"list.txt").write_text("".join(f"file '{p}'\n" for p in parts))
    sh("ffmpeg","-y","-v","error","-f","concat","-safe","0","-i",str(W/"list.txt"),"-c","copy",str(W/"voice_raw.wav"))
    # 3) 2-pass loudnorm → -14.9 LUFS
    m = sh("ffmpeg","-hide_banner","-i",str(W/"voice_raw.wav"),"-af",f"loudnorm=I={TARGET_LUFS}:TP={TP}:LRA={LRA}:print_format=json","-f","null","-").stderr
    st = json.loads(m[m.rindex("{"):m.rindex("}")+1])
    ln = (f"loudnorm=I={TARGET_LUFS}:TP={TP}:LRA={LRA}:measured_I={st['input_i']}:measured_TP={st['input_tp']}:"
          f"measured_LRA={st['input_lra']}:measured_thresh={st['input_thresh']}:offset={st['target_offset']}:linear=true")
    sh("ffmpeg","-y","-v","error","-i",str(W/"voice_raw.wav"),"-af",ln,"-ar","48000",str(W/"voice_ln.wav"))
    # 보정 패스: 피크 제한 때문에 목표에 못 미치면 게인 보정 + 리미터로 ±0.3 LU 안에 맞춤
    src = W/"voice_ln.wav"
    for k in range(4):
        e = sh("ffmpeg","-hide_banner","-i",str(src),"-af","ebur128=peak=true","-f","null","-").stderr
        cur = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1])
        if abs(cur - TARGET_LUFS) <= 0.2: break
        dst = W/f"voice_fix{k}.wav"
        sh("ffmpeg","-y","-v","error","-i",str(src),"-af",f"volume={TARGET_LUFS-cur:.2f}dB,alimiter=limit={10**(TP/20):.4f}:level=disabled","-ar","48000",str(dst))
        src = dst
    sh("ffmpeg","-y","-v","error","-i",str(src),"-c","copy",str(W/"voice.wav"))
    # 4) 자막(ASS) + 1080x1920 30fps 합성
    def ts(x): return f"{int(x//3600)}:{int(x%3600//60):02d}:{x%60:05.2f}"
    ass = ["[Script Info]","ScriptType: v4.00+",f"PlayResX: {OW}",f"PlayResY: {OH}","",
           "[V4+ Styles]","Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV",
           "Style: Sub,Gaegu,118,&H00FFFFFF,&H00A0379B,&H64000000,1,1,9,3,2,60,60,430","",
           "[Events]","Format: Layer, Start, End, Style, Text"]
    for a, b, line in cues:
        ass.append(f"Dialogue: 0,{ts(a)},{ts(b+0.15)},Sub,{{\\fad(120,80)\\t(0,160,\\fscx108\\fscy108)\\t(160,300,\\fscx100\\fscy100)}}{line}")
    (W/"subs.ass").write_text("\n".join(ass), encoding="utf-8")
    (OUT/"subs.ass").write_text("\n".join(ass), encoding="utf-8")
    n = int(round(total * FPS))
    vf = (f"[0:v]scale={OW}:{OH}:force_original_aspect_ratio=increase,crop={OW}:{OH},gblur=sigma=40,eq=brightness=0.04[bg];"
          f"[0:v]scale=2160:-2,zoompan=z='1+0.06*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s=1080x608:fps={FPS}[fg];"
          f"[bg][fg]overlay=0:(H-h)/2-140:shortest=1,subtitles=subs.ass:fontsdir=../assets/fonts,format=yuv420p[v]")
    sh("ffmpeg","-y","-v","error","-loop","1","-framerate",str(FPS),"-i",str(IMAGE),"-i",str(W/"voice.wav"),
       "-filter_complex",vf,"-map","[v]","-map","1:a","-t",f"{total:.3f}","-r",str(FPS),
       "-c:v","libx264","-preset","medium","-crf","20","-c:a","aac","-b:a","192k","-movflags","+faststart",str(OUT/"twin_cheer.mp4"))
    # 5) 결과 측정 + Whisper 대조 검수
    e = sh("ffmpeg","-hide_banner","-i",str(OUT/"twin_cheer.mp4"),"-af","ebur128=peak=true","-f","null","-").stderr
    I = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1]); TPk = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", e)[-1])
    sh("ffmpeg","-y","-v","error","-i",str(OUT/"twin_cheer.mp4"),"-ac","1","-ar","16000",str(W/"check.wav"))
    import numpy as np
    from faster_whisper import WhisperModel
    wv = wave.open(str(W/"check.wav")); a = np.frombuffer(wv.readframes(wv.getnframes()), np.int16).astype(np.float32)/32768
    segs, _ = WhisperModel("medium", device="cpu", compute_type="int8").transcribe(a, language="ko", beam_size=5)
    heard = " ".join(s.text.strip() for s in segs)
    norm = lambda s: re.sub(r"[^가-힣a-zA-Z0-9]", "", s)
    ref, hyp = norm(" ".join(LINES)), norm(heard)
    sm = difflib.SequenceMatcher(None, ref, hyp)
    cer = 1 - sm.ratio()
    diffs = [f"{op}: 대본 '{ref[i1:i2]}' / 받아쓰기 '{hyp[j1:j2]}'" for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal"]
    probe = json.loads(sh("ffprobe","-v","error","-show_entries","stream=codec_type,width,height,r_frame_rate:format=duration","-of","json",str(OUT/"twin_cheer.mp4")).stdout)
    v = [s for s in probe["streams"] if s["codec_type"] == "video"][0]
    report.update({"voice": f"{VOICE}, 속도 x{SPEED}", "cues": [{"start": round(a,2), "end": round(b,2), "text": l} for a,b,l in cues],
                   "duration": round(float(probe["format"]["duration"]),2), "resolution": f"{v['width']}x{v['height']}", "fps": v["r_frame_rate"],
                   "loudness_lufs": I, "true_peak_dbfs": TPk, "whisper_text": heard, "cer": round(cer,4), "diffs": diffs,
                   "pass": abs(I - TARGET_LUFS) <= 0.5 and v["width"] == OW and v["height"] == OH and cer <= 0.05})
    # 6) 구글 드라이브 업로드
    if upload_dir or rclone_dest:
        report["upload"] = upload(OUT/"twin_cheer.mp4", name, upload_dir, rclone_dest)
    (OUT/"report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=1))


def upload(video, name, upload_dir=None, rclone_dest=None):
    """완성 영상을 구글 드라이브로 올린다.
    upload_dir : 데스크톱용 Drive 동기화 폴더(예: G:\\내 드라이브\\OUP PUT). 복사하면 Drive 앱이 올린다.
    rclone_dest: rclone 원격 경로(예: gdrive:OUP PUT). 바로 업로드하고 '링크가 있는 모든 사용자' 링크를 만든다.
    """
    result = {}
    if upload_dir:
        dst = Path(upload_dir) / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(video, dst)
        result["sync_folder"] = str(dst)
    if rclone_dest:
        if not shutil.which("rclone"):
            sys.exit("rclone이 설치되어 있지 않습니다. README의 'rclone으로 바로 업로드' 절을 따라 설치·설정하세요.")
        remote = f"{rclone_dest.rstrip('/')}/{name}"
        subprocess.run(["rclone", "copyto", str(video), remote], check=True)
        link = subprocess.run(["rclone", "link", remote], check=True, capture_output=True, text=True).stdout.strip()
        result.update({"rclone": remote, "share_link": link})
    return result

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="세로형 응원 영상 자동 편집 + 구글 드라이브 업로드")
    ap.add_argument("--upload-dir", default=os.environ.get("UPLOAD_DIR"),
                    help="Drive 동기화 폴더 경로 (환경변수 UPLOAD_DIR)")
    ap.add_argument("--rclone", default=os.environ.get("RCLONE_DEST"),
                    help="rclone 원격 경로, 예: gdrive:OUP PUT (환경변수 RCLONE_DEST)")
    ap.add_argument("--name", default="twin_cheer.mp4", help="드라이브에 올릴 파일 이름")
    a = ap.parse_args()
    main(a.upload_dir, a.rclone, a.name)

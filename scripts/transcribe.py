#!/usr/bin/env python3
"""Download + transcribe Generation Jihad episodes with faster-whisper (CPU).
Usage: python3 transcribe.py batch_XX.json [--model distil-large-v3] [--out transcripts]
Writes transcripts/<idx>_<slug>.txt (plain) and .segments.json (timestamps). Skips done episodes.
"""
import json, sys, os, subprocess, time, argparse, urllib.request
import numpy as np

GLOSSARY = ("Generation Jihad, FDD's Long War Journal. Bill Roggio, Tom Joscelyn, Caleb Weiss. Taliban, Haqqani Network, "
 "Sirajuddin Haqqani, Jalaluddin Haqqani, Khalil Haqqani, Anas Haqqani, Hibatullah Akhundzada, Mullah Omar, Mullah Yaqoob, "
 "Abdul Ghani Baradar, Ayman al-Zawahiri, Osama bin Laden, Hamza bin Laden, Saif al-Adel, Abu Muhammad al-Masri, "
 "al-Qaeda, AQIS, Tehrik-i-Taliban Pakistan, Noor Wali Mehsud, Islamic State Khorasan, ISKP, Waziristan, Kandahar, Kabul, "
 "Panjshir, Ahmad Massoud, Amrullah Saleh, Doha, Zalmay Khalilzad, Ashraf Ghani, ISI, Durand Line, Bagram, Quetta Shura, "
 "Peshawar, Sami Sadat, Edmund Fitton-Brown, UN Monitoring Team.")

def load_audio(path):
    out = subprocess.run(["ffmpeg","-loglevel","error","-i",path,"-f","s16le","-ac","1","-ar","16000","-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(out, np.int16).astype(np.float32)/32768

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("batch"); ap.add_argument("--model", default="distil-large-v3")
    ap.add_argument("--out", default="transcripts"); ap.add_argument("--audio", default="audio")
    ap.add_argument("--threads", type=int, default=os.cpu_count() or 4)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True); os.makedirs(a.audio, exist_ok=True)
    eps = json.load(open(a.batch))
    from faster_whisper import WhisperModel
    model = WhisperModel(a.model, device="cpu", compute_type="int8", cpu_threads=a.threads)
    for e in eps:
        base = f"{e['idx']:03d}_{e['slug']}"
        txt = os.path.join(a.out, base+".txt")
        if os.path.exists(txt) and os.path.getsize(txt) > 1000:
            print("skip", base); continue
        mp3 = os.path.join(a.audio, base+".mp3")
        if not os.path.exists(mp3) or os.path.getsize(mp3) < 100000:
            for attempt in range(3):
                try:
                    req = urllib.request.Request(e['audio'], headers={"User-Agent":"Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=120) as r, open(mp3,"wb") as f:
                        while True:
                            chunk = r.read(1<<20)
                            if not chunk: break
                            f.write(chunk)
                    break
                except Exception as ex:
                    print("download retry", base, ex); time.sleep(5)
        t0 = time.time()
        audio = load_audio(mp3)
        segs, info = model.transcribe(audio, beam_size=1, language="en", vad_filter=True,
                                      initial_prompt=GLOSSARY, condition_on_previous_text=False)
        out_segs = []
        for s in segs:
            out_segs.append({"start": round(s.start,2), "end": round(s.end,2), "text": s.text.strip()})
        text = "\n".join(f"[{int(s['start'])//60:03d}:{int(s['start'])%60:02d}] {s['text']}" for s in out_segs)
        header = f"# {e['title']}\n# published: {e['pub']}  duration: {e['dur']}s  idx: {e['idx']}  guid: {e['guid']}\n# {e['desc']}\n\n"
        open(txt,"w").write(header+text)
        json.dump({"episode": e, "segments": out_segs}, open(os.path.join(a.out, base+".segments.json"),"w"))
        print(f"done {base}: {len(audio)/16000/60:.1f} min audio in {time.time()-t0:.0f}s", flush=True)

if __name__ == "__main__":
    main()

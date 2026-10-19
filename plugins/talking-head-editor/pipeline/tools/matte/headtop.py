"""Median y of the top of the hair across the frames the edit uses (from the person matte, 1080x1920 = timeline coords).
Usage (from the job folder): python3 tools/matte/headtop.py MATTE.mkv [edl.json] -> headtop_<matte name>.json"""
import json, sys, subprocess, os, numpy as np, imageio_ffmpeg
MATTE = sys.argv[1]; n = os.path.splitext(os.path.basename(MATTE))[0].replace("matte_", ""); FF = imageio_ffmpeg.get_ffmpeg_exe()
E = json.load(open(sys.argv[2] if len(sys.argv) > 2 else "edl.json"))["items"]
ys = []
for it in E:
    for t in np.linspace(it["src_in"], it["src_out"], 3):
        r = subprocess.run([FF, "-nostdin", "-loglevel", "error", "-i", MATTE, "-vf", f"select=eq(n\\,{int(round(t * 30))}),format=gray",
                            "-frames:v", "1", "-f", "rawvideo", "-"], capture_output=True).stdout
        if len(r) != 1080 * 1920: continue
        m = np.frombuffer(r, np.uint8).reshape(1920, 1080)[:, 300:780] > 128
        rows = np.where(m.mean(1) > 0.05)[0]
        if len(rows): ys.append(int(rows[0]))
json.dump({"head_top": float(np.median(ys)), "samples": len(ys), "p10": float(np.percentile(ys, 10)), "p90": float(np.percentile(ys, 90))}, open(f"headtop_{n}.json", "w"))
print(n, open(f"headtop_{n}.json").read())

"""Face box per EDL piece, in TIMELINE px (job.W x job.H). One detection per take (mid-take frame, then the take's first),
shared by that take's pieces; zooms.py takes medians anyway. Frames go through job.PREVIEW_VF (the camera LUT for log
footage) so Haar sees a normal picture.
16:9 delivery: the timeline IS the full source frame, so detect on the whole frame at half size.
9:16 delivery from a 16:9 camera: the timeline centre-crops the source (Resolve scaleToCrop), so detect inside that crop.
-> transcripts/faces.json. Then look at the medians before choosing a graphics layout: the framing decides the layout,
not the last job (a face filling the top half of a 9:16 crop wants split scenes, a centred 16:9 face wants the side plate)."""
import json, subprocess, imageio_ffmpeg, numpy as np, cv2
import job
FF = imageio_ffmpeg.get_ffmpeg_exe()
def vf():
    return job.PREVIEW_VF.format(lut=job.LUT) if "{lut}" in job.PREVIEW_VF else job.PREVIEW_VF
E = json.load(open('edl.json'))
casc = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
prof = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_profileface.xml')
WIDE = job.W > job.H
if WIDE: crop, gw, gh, k = "", 960, 540, job.W / 960                       # whole frame at half size -> x2 to timeline px
else:    crop, gw, gh, k = "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,", 540, 960, job.W / 540   # 9:16 centre crop -> timeline px
takes = {}
for i, it in enumerate(E['items']):
    if it['kind'] == 'a': takes.setdefault(it['take'], []).append(i)
out = []
for tk, idx in takes.items():
    boxes = []
    for i in (idx[len(idx) // 2], idx[0]):
        it = E['items'][i]; t = (it['src_in'] + it['src_out']) / 2
        p = subprocess.run([FF, '-v', 'error', '-ss', f'{t:.2f}', '-i', str(job.source(it.get('clip'))['video']), '-frames:v', '1',
                            '-vf', f"{vf()},{crop}scale={gw}:{gh}", '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], capture_output=True)
        g = np.frombuffer(p.stdout, np.uint8)[:gw * gh].reshape(gh, gw)
        fs = casc.detectMultiScale(g, 1.1, 5, minSize=(60, 60))
        if len(fs) == 0: fs = prof.detectMultiScale(g, 1.1, 5, minSize=(60, 60))
        if len(fs): x, y, w, h = max(fs, key=lambda b: b[2] * b[3]); boxes.append([x * k, y * k, w * k, h * k])
        if boxes: break
    for i in idx:
        if boxes:
            b = np.median(np.array(boxes), 0).tolist()
            out.append({'i': i, 'take': tk, 'cx': round(b[0] + b[2] / 2), 'cy': round(b[1] + b[3] / 2), 'w': round(b[2]), 'chin': round(b[1] + b[3]), 'n': len(boxes)})
        else: out.append({'i': i, 'take': tk, 'cx': None})
json.dump(out, open('transcripts/faces.json', 'w'), indent=0)
F = [o for o in out if o['cx']]
print(len(F), 'of', len(out), 'pieces with a face')
if F:
    med = lambda key: int(np.median([o[key] for o in F]))
    print(f"median face: cx {med('cx')} cy {med('cy')} width {med('w')} chin {med('chin')} (timeline {job.W}x{job.H})")

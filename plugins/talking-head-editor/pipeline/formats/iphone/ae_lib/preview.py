"""Overlay each rendered scene on the (HLG-previewed) footage at chosen record times -> qc/gfx_preview.jpg"""
import json, subprocess, sys, imageio_ffmpeg, os
sys.path.insert(0, '.'); import job
from PIL import Image
FF = imageio_ffmpeg.get_ffmpeg_exe(); E = json.load(open('edl.json'))['items']; G = json.load(open('graphics/graphics_timing.json'))
def src_at(t):
    for it in E:
        if it['rec_in'] <= t < it['rec_out']: return job.source(it.get('clip'))['video'], it['src_in'] + (t - it['rec_in'])
    it = E[-1]; return job.source(it.get('clip'))['video'], it['src_out'] - 0.05
os.makedirs('qc', exist_ok=True); tiles = []
pts = [float(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else []
if not pts:
    for g in G: pts += [g['start'] + (g['end'] - g['start']) * f for f in (0.45, 0.9)]
for k, t in enumerate(pts):
    v, st = src_at(t); g = next((g for g in G if g['start'] <= t < g['end']), None)
    args = [FF, '-v', 'error', '-y', '-ss', f'{st:.3f}', '-i', str(v)]
    if g: args += ['-ss', f'{t - g["start"]:.3f}', '-i', f'graphics/{g["id"]}.mov', '-filter_complex', f'[0:v]{job.PREVIEW_VF},scale=1080:1920[b];[b][1:v]overlay=0:0,scale=270:480']
    else: args += ['-vf', f'{job.PREVIEW_VF},scale=270:480']
    subprocess.run(args + ['-frames:v', '1', f'qc/_p{k}.png'], check=True); tiles.append(Image.open(f'qc/_p{k}.png').convert('RGB'))
cols = min(6, len(tiles)); rows = (len(tiles) + cols - 1) // cols; im = Image.new('RGB', (270 * cols, 480 * rows))
for k, t in enumerate(tiles): im.paste(t, ((k % cols) * 270, (k // cols) * 480))
im.save('qc/gfx_preview.jpg', quality=85); [os.remove(f'qc/_p{k}.png') for k in range(len(tiles))]; print('qc/gfx_preview.jpg', len(tiles), 'tiles')

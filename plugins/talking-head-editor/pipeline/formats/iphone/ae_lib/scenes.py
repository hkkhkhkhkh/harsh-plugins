"""Scene list for an iPhone 9:16 job, cued to spoken words on the record timeline. The `if job.TAG == ...` blocks below are the
worked example (three phone ads for a nutrition course): copy the pattern into a block for your own job.TAG.
Run inside the job folder: writes ae/graphics.jsx (lib + scenes), graphics/graphics_timing.json,
graphics/inserts_timing.json (B-roll) and graphics/zones.json (split/full intervals: captions move out of the way there)."""
import json, os, re, sys
sys.path.insert(0, '.')
import job
HERE = os.getcwd(); LIB = os.path.join(os.path.dirname(__file__), 'lib.jsx')
BROLL = os.path.join(HERE, 'broll'); ASSETS = os.path.join(HERE, 'assets')   # job-local B-roll and stills
W = json.load(open('transcripts/rec_words.json')); E = json.load(open('edl.json'))['items']
def norm(s): return re.sub(r"[^a-z0-9&%]", "", s.lower())
def at(word, take, nth=0):
    hits = [w for w in W if w['take'] == take and norm(w['w']).startswith(norm(word))]
    if len(hits) <= nth: raise SystemExit(f"cue word {word!r} (#{nth}) not found in take {take}: {[w['w'] for w in W if w['take']==take]}")
    return hits[nth]['s']
def span(take):
    tp = [it for it in E if it.get('take') == take]; return tp[0]['rec_in'], tp[-1]['rec_out']
S, I = [], []   # scenes, inserts
import wave
RISER = (lambda w: w.getnframes() / w.getframerate())(wave.open('audio/sd/riser.wav'))
def ins(name, a, b, off=0.5): I.append({"file": os.path.join(BROLL, f"{name}.mov"), "start": round(a, 3), "end": round(b, 3), "src_off": off})
def sc(**k): k['start'] = round(k['start'], 3); k['end'] = round(k['end'], 3); S.append(k)

# v5 (27 Sep, his notes): calm and depictive. No stickers (chips, seals, badges, ribbons, kicker labels), no B-roll flashes,
# some panels full screen, and no gap under 2.5 s between graphics (short flicks of A-roll looked messy).
def mineral(take):
    sc(id=f"mineral_t{take}", type="mineral", start=span(take)[0], end=span(take)[1],
       cues={"oxide": at('oxide', take), "bis": at('bisglycinate', take), "iron": at('iron', take), "iron2": at('bisglycinate', take, 1)})
def rxpad(t_rough, t_less, t_blame):
    sc(id="rxpad", type="rxpad", start=span(t_rough)[0], end=span(t_blame)[0] + 2.2,
       lines=[["Lose weight", at('lose', t_rough)], ["Eat more fibre", at('fiber', t_rough)], ["Work out more", at('work', t_rough)]], cues={})

if job.TAG == "IMG3389":
    mineral(2); rxpad(4, 5, 6)
    sc(id="stack_ef", type="split", variant="stack", full=True, title="What Evidence First teaches", start=span(7)[0], end=span(9)[1],
       items=[["Research-backed", at('research', 7)], ["Applied", at('practical', 8)], ["Explainable", at('explain', 9)]], cues={})
    sc(id="checklist", type="split", variant="checklist", title="By the end of the course", start=span(10)[0], end=span(12)[1],
       items=[["A thorough diet plan", at('diet', 10)], ["A supplementation protocol", at('supplementation', 11)], ["A plan that works", at('prescribe', 12)]], cues={})
    sc(id="steps_qa", type="split", variant="steps", title="Your cases, worked live", start=span(13)[0], end=span(15)[1],
       items=[["Bring your\npatients", at('patients', 13)], ["Build the\ndiet plan", at('create', 14)], ["Guidance on\nyour cases", at('guidance', 14)]], cues={})
    sc(id="cta", type="cta", text="Click the link below", start=span(18)[0], end=span(18)[1], cues={"in": at('click', 18) + 0.05})

if job.TAG == "IMG3390":
    sc(id="mech", type="split", variant="mech", full=True, title="The mechanism behind every plan", start=span(4)[0], end=span(4)[1],
       items=[["Food", at('scientific', 4)], ["Metabolism", at('mechanisms', 4)], ["Your\nplan", at('plans', 4)]], cues={})
    sc(id="steps_qa", type="split", variant="steps", title="Your patients, worked live", start=span(5)[0], end=span(6)[1],
       items=[["Bring your\npatients", at('patients', 5)], ["Create the\nplan", at('create', 6)], ["Alter it\nwith us", at('alter', 6)]], cues={})
    sc(id="bonus", type="split", variant="bonus", title="Included", start=span(7)[0], end=span(8)[1], cues={"a": at('bonus', 7), "b": at('medical', 8)})
    sc(id="twocol", type="split", variant="twocol", full=True, title="What we focus on", start=span(11)[0], end=span(13)[1],
       cues={"a": at('basic', 11), "strike": at('theory', 11), "b": at('practical', 12)})
    sc(id="cta", type="cta", text="Click the link below", start=span(16)[0], end=span(16)[1], cues={"in": at('click', 16) + 0.05})

if job.TAG == "IMG3391":
    sc(id="ladder", type="split", variant="ladder", title="Not four separate courses", start=span(3)[0], end=span(5)[1],
       items=[["Basic nutrition", at('basic', 4)], ["Advanced nutrition", at('advanced', 4)], ["Supplementation", at('supplementation', 4)], ["Special populations", at('special', 4)]],
       cues={"strike": span(4)[1] - 0.35, "collapse": at('all', 5), "bonus": at('bonus', 5)})
    sc(id="phone", type="phone", image=os.path.join(ASSETS, 'site_520.png'), from_=3280, to=3480, label="learnevidence.com", start=span(6)[0], end=span(6)[1], cues={})
    S[-1]['from'] = S[-1].pop('from_')
    p7 = span(7)[0]
    sc(id="price", type="price", start=p7, end=span(7)[1], cues={"in": p7 + 0.05, "annual": p7 + 0.15, "monthly": at('monthly', 7)})
    sc(id="cta", type="cta", text="Click the link below", start=span(8)[0], end=span(8)[1], cues={"in": at('click', 8) + 0.05})

S.sort(key=lambda s: s['start'])
ZT = ('split', 'mineral', 'rxpad', 'phone')
for x, y in zip(S, S[1:]):   # close short gaps between screen-filling graphics, then cut straight across instead of wiping
    if x['type'] in ZT and y['type'] in ZT and y['start'] - x['end'] < 2.5: x['end'] = y['start']
for x, y in zip(S, S[1:]):
    if x['type'] in ZT and y['type'] in ZT and abs(y['start'] - x['end']) < 0.05: x['hard_out'] = True; y['hard_in'] = True

ONLY = [x for x in os.environ.get('ONLY', '').split(',') if x]
SFX = []
def hit(t, name, g): SFX.append({"t": round(t, 3), "sfx": name, "gain_db": g + getattr(job, "SFX_TRIM_DB", 0)})
for s in S:
    c = s.get('cues', {}); ty = s['type']
    if ty == 'title': hit(c['in'] - 0.06, 'impact', -15); hit(c['in'] - 0.12, 'whoosh_soft', -18)
    if ty == 'chips':
        for it in s['items']: hit(it[1] - 0.02, 'pop', -19)
        if s.get('sub'): hit(s['sub'][1] - 0.02, 'pop', -21)
    if ty == 'mineral':
        if not s.get('hard_in'): hit(s['start'] - 0.1, 'whoosh_soft', -16)
        for k in ('oxide', 'bis', 'iron', 'iron2'): hit(c[k] - 0.02, 'pop', -20)
    if ty == 'rxpad':
        if not s.get('hard_in'): hit(s['start'] - 0.1, 'whoosh_soft', -16)
        for ln in s['lines']: hit(ln[1] + 0.43, 'strike', -17)
    if ty == 'split':
        if not s.get('hard_in'): hit(s['start'] - 0.08, 'whoosh_soft', -17)
        for it in s.get('items', []): hit(it[1] - 0.02, 'pop', -20)
        if 'strike' in c: hit(c['strike'], 'strike', -17)
        if 'collapse' in c: hit(c['collapse'] - 0.03, 'impact', -19)
        if 'a' in c and s.get('variant') in ('twocol', 'bonus'): hit(c['a'] - 0.02, 'pop', -20)
        if 'b' in c: hit(c['b'] - 0.02, 'pop', -20)
        if 'bonus' in c: hit(c['bonus'] - 0.02, 'pop', -20)
    if ty == 'seal': hit(c['in'] - 0.03, 'impact', -14)
    if ty == 'price': hit(c['in'] - 0.1, 'whoosh_soft', -17); hit(c['annual'] - 0.03, 'impact', -19)
    if ty == 'cta': hit(c['in'] - 0.05, 'pop', -17)
    if ty == 'badge': hit(c['in'] - 0.1, 'whoosh_soft', -17); hit(c['in'] + 0.3, 'pop', -19)
    if ty == 'phone' and not s.get('hard_in'): hit(s['start'] - 0.1, 'whoosh_soft', -16)
for i in I: hit(i['start'] - 0.15, 'fastwhoosh', -21); hit(i['end'] - 0.1, 'fastwhoosh', -23)
os.makedirs('audio', exist_ok=True); json.dump(sorted(SFX, key=lambda h: h['t']), open('audio/sfx_plan.json', 'w'), indent=0)
os.makedirs('graphics', exist_ok=True); os.makedirs('ae', exist_ok=True)
json.dump([{"id": s['id'], "start": s['start'], "end": s['end'], "type": s['type'], "variant": s.get('variant'), "cues": s.get('cues', {})} for s in S], open('graphics/graphics_timing.json', 'w'), indent=1)
json.dump(I, open('graphics/inserts_timing.json', 'w'), indent=1)
zones = [{"kind": "split" if s['type'] == 'split' and not s.get('full') else "full", "start": s['start'], "end": s['end'],
          "hard_in": bool(s.get('hard_in')), "hard_out": bool(s.get('hard_out'))} for s in S if s['type'] in ZT]
json.dump(zones, open('graphics/zones.json', 'w'), indent=1)
out = os.path.abspath('graphics') + '/'
if ONLY: out_aep = 'partial'
errsave = "try { app.project.save(new File(" + json.dumps(out) + " + 'ERR_' + __R.replace(/[^A-Za-z0-9 _.-]/g, '_').substr(0, 150) + '.aep')); } catch (e3) {}"
jsx = open(LIB).read() + "\nvar __R = 'OK'; try { build(" + json.dumps([x for x in S if not ONLY or x['id'] in ONLY]) + ", " + json.dumps(out) + ", " + str(job.FPS) + ", " + json.dumps("graphics_partial.aep" if ONLY else "graphics.aep") + "); } catch (e) { __R = 'ERR ' + e.toString() + ' line ' + e.line; try { app.endSuppressDialogs(false); } catch (e2) {} " + errsave + " }\n__R;\n"
open('ae/graphics.jsx', 'w').write(jsx)
for s in S: print(f"{s['start']:7.2f}-{s['end']:7.2f} {s['type']:8s} {s['id']}")
print(len(I), 'inserts:', [(i['file'].split('/')[-1], round(i['start'], 2), round(i['end'], 2)) for i in I])

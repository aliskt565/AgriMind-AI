"""Build unified records, near-duplicate clusters (group-aware split), and a uint8 224x224 memmap cache."""
import glob, json, os, random, numpy as np
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
from hashes import hash_file, popcount64

D = '/home/claude/data'
PV_MAP = {
 "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot": "Corn___Gray_Leaf_Spot",
 "Corn_(maize)___Common_rust_": "Corn___Common_Rust",
 "Corn_(maize)___Northern_Leaf_Blight": "Corn___Northern_Leaf_Blight",
 "Corn_(maize)___healthy": "Corn___Healthy",
 "Potato___Early_blight": "Potato___Early_Blight",
 "Potato___Late_blight": "Potato___Late_Blight",
 "Potato___healthy": "Potato___Healthy"}
PD_MAP = {"Corn Gray leaf spot": "Corn___Gray_Leaf_Spot", "Corn rust leaf": "Corn___Common_Rust",
          "Corn leaf blight": "Corn___Northern_Leaf_Blight",
          "Potato leaf early blight": "Potato___Early_Blight", "Potato leaf late blight": "Potato___Late_Blight"}
GE_MAP = {"Cercospora_leaf_spot Gray_leaf_spot": "Corn___Gray_Leaf_Spot", "Common_rust": "Corn___Common_Rust",
          "Northern_Leaf_Blight": "Corn___Northern_Leaf_Blight", "healthy": "Corn___Healthy"}
CLASSES = ["Corn___Common_Rust","Corn___Gray_Leaf_Spot","Corn___Healthy","Corn___Northern_Leaf_Blight",
           "Potato___Early_Blight","Potato___Healthy","Potato___Late_Blight"]

recs = []
for k, v in PV_MAP.items():
    for p in sorted(glob.glob(f'{D}/pv/raw/color/{k}/*')):
        recs.append(dict(path=p, label=v, source='plantvillage'))
for s in ('train', 'test'):
    for k, v in PD_MAP.items():
        for p in sorted(glob.glob(f'{D}/PlantDoc-Dataset-master/{s}/{k}/*')):
            recs.append(dict(path=p, label=v, source='plantdoc'))
for k, v in GE_MAP.items():
    for p in sorted(glob.glob(f'{D}/gitergo/Natural_environment/*/{k}/*')):
        recs.append(dict(path=p, label=v, source='gitergo_field'))
print('records', len(recs))

with ThreadPoolExecutor(2) as ex:
    res = list(ex.map(hash_file, [r['path'] for r in recs]))
keep = [i for i, r in enumerate(res) if r[1] is not None]
recs = [recs[i] for i in keep]; res = [res[i] for i in keep]
H = np.array([r[1] for r in res], dtype=np.uint64); HF = np.array([r[2] for r in res], dtype=np.uint64)
n = len(recs); print('hashed', n)

parent = list(range(n))
def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]; x = parent[x]
    return x
pairs = 0; cross_label = 0
for i in range(n):
    d = np.minimum(popcount64(H[i+1:] ^ H[i]), popcount64(H[i+1:] ^ HF[i]))
    for j in np.where(d <= 5)[0] + i + 1:
        if recs[i]['label'] != recs[j]['label']:
            cross_label += 1; continue
        a, b = find(i), find(int(j))
        if a != b: parent[a] = b
        pairs += 1
print('near-dup pairs (same label)', pairs, '| cross-label conflicts skipped', cross_label)

groups = defaultdict(list)
for i in range(n): groups[find(i)].append(i)
print('groups', len(groups), 'largest', max(len(g) for g in groups.values()))

# group-aware stratified split by (source, label): 80/10/10
rng = random.Random(42)
strata = defaultdict(list)
for g in groups.values():
    r0 = recs[g[0]]
    srcs = {recs[i]['source'] for i in g}
    key = ('mixed' if len(srcs) > 1 else r0['source'], r0['label'])
    strata[key].append(g)
for key, gl in strata.items():
    gl.sort(key=lambda g: g[0]); rng.shuffle(gl)
    tot = sum(len(g) for g in gl); run = 0
    for g in gl:
        sp = 'train' if run < 0.8 * tot else ('val' if run < 0.9 * tot else 'test')
        for i in g: recs[i]['split'] = sp
        run += len(g)
for i, r in enumerate(recs): r['group'] = int(find(i))

# cache
os.makedirs('/home/claude/proj/cache', exist_ok=True)
X = np.lib.format.open_memmap('/home/claude/proj/cache/X.npy', mode='w+', dtype=np.uint8, shape=(n, 224, 224, 3))
def load(i):
    im = Image.open(recs[i]['path']); im.draft('RGB', (448, 448))
    return i, np.asarray(im.convert('RGB').resize((224, 224), Image.BILINEAR))
with ThreadPoolExecutor(2) as ex:
    for i, a in ex.map(load, range(n)): X[i] = a
X.flush()
for r in recs: r['y'] = CLASSES.index(r['label'])
json.dump(recs, open('/home/claude/proj/cache/records.json', 'w'))
from collections import Counter
c = Counter((r['source'], r['split']) for r in recs)
for k in sorted(c): print(k, c[k])

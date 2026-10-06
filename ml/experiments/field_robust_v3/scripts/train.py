#!/usr/bin/env python3
"""AgriMind V2 field-robust training. MobileNetV2 -> GAP -> Dense128 -> Dropout -> Dense7 (same head as v2-alpha).
Usage: python train.py --name modelB --use_gitergo 1
Selection uses VAL only. TEST is touched once at the end. Metrics always reported per source."""
import argparse, json, math, os, time, numpy as np, tensorflow as tf
from tensorflow import keras
ap = argparse.ArgumentParser()
ap.add_argument('--name', required=True); ap.add_argument('--use_gitergo', type=int, default=0)
ap.add_argument('--s1_epochs', type=int, default=3); ap.add_argument('--s2_epochs', type=int, default=7)
ap.add_argument('--unfreeze', type=int, default=80); ap.add_argument('--field_w', type=float, default=3.0)
a = ap.parse_args()
SEED = 42; tf.random.set_seed(SEED); np.random.seed(SEED)
C = '/home/claude/proj/cache'; OUT = f'/home/claude/proj/out/{a.name}'; os.makedirs(OUT, exist_ok=True)
R = json.load(open(f'{C}/records.json')); X = np.load(f'{C}/X.npy', mmap_mode='r')
N_CLS = 7; FIELD = {'plantdoc', 'gitergo_field'}
def idx(split, srcs=None):
    return [i for i, r in enumerate(R) if r['split'] == split and (srcs is None or r['source'] in srcs)]
train_srcs = {'plantvillage', 'plantdoc'} | ({'gitergo_field'} if a.use_gitergo else set())
tr = idx('train', train_srcs); va = idx('val', train_srcs)
print('train', len(tr), 'val', len(va), flush=True)
cnt = np.bincount([R[i]['y'] for i in tr], minlength=N_CLS)
cw = len(tr) / (N_CLS * np.maximum(cnt, 1)); cw = np.clip(cw, 0.4, 4.0)
def w_of(i): return cw[R[i]['y']] * (a.field_w if R[i]['source'] in FIELD else 1.0)

def gen(ids, shuffle):
    ids = list(ids)
    def g():
        order = np.random.permutation(len(ids)) if shuffle else range(len(ids))
        for k in order:
            i = ids[k]; yield X[i], R[i]['y'], w_of(i) if shuffle else 1.0
    return g
sig = (tf.TensorSpec((224, 224, 3), tf.uint8), tf.TensorSpec((), tf.int32), tf.TensorSpec((), tf.float32))

def augment(img, y, w):
    img = tf.cast(img, tf.float32) / 255.0
    # random scale/crop + aspect jitter (phone framing differs a lot)
    s = tf.random.uniform([], 0.55, 1.0); ar = tf.random.uniform([], 0.8, 1.25)
    ch = tf.cast(224 * s, tf.int32); cw_ = tf.minimum(224, tf.cast(224 * s * ar, tf.int32))
    img = tf.image.random_crop(img, [ch, cw_, 3]); img = tf.image.resize(img, (224, 224))
    img = tf.image.random_flip_left_right(img); img = tf.image.random_flip_up_down(img)
    k = tf.random.uniform([], 0, 4, tf.int32); img = tf.image.rot90(img, k)
    img = tf.image.random_brightness(img, 0.25); img = tf.image.random_contrast(img, 0.7, 1.35)
    img = tf.image.random_saturation(img, 0.6, 1.4); img = tf.image.random_hue(img, 0.04)
    # random gamma + colour cast (sun/shade/white-balance)
    img = tf.clip_by_value(img, 0, 1) ** tf.random.uniform([], 0.75, 1.35)
    img = img * tf.random.uniform([1, 1, 3], 0.9, 1.1)
    img = tf.clip_by_value(img, 0, 1)
    if tf.random.uniform([]) < 0.5:
        img = tf.image.random_jpeg_quality(tf.cast(img * 255, tf.uint8), 25, 85); img = tf.cast(img, tf.float32) / 255.0
    if tf.random.uniform([]) < 0.3:  # blur (focus/motion)
        kx = tf.constant([1., 4., 6., 4., 1.]) / 16.0; kk = kx[:, None] * kx[None, :]
        kk = tf.tile(kk[:, :, None, None], [1, 1, 3, 1])
        img = tf.nn.depthwise_conv2d(img[None], kk, [1, 1, 1, 1], 'SAME')[0]
    if tf.random.uniform([]) < 0.35:  # random erasing (occlusion)
        eh = tf.random.uniform([], 30, 90, tf.int32); ew = tf.random.uniform([], 30, 90, tf.int32)
        y0 = tf.random.uniform([], 0, 224 - eh, tf.int32); x0 = tf.random.uniform([], 0, 224 - ew, tf.int32)
        m = tf.pad(tf.zeros([eh, ew, 1]), [[y0, 224 - eh - y0], [x0, 224 - ew - x0], [0, 0]], constant_values=1.0)
        img = img * m + (1 - m) * tf.random.uniform([1, 1, 3])
    img = tf.clip_by_value(img, 0, 1) * 255.0
    return keras.applications.mobilenet_v2.preprocess_input(img), tf.one_hot(y, N_CLS) * 0.9 + 0.1 / N_CLS, w
def plain(img, y, w):
    img = keras.applications.mobilenet_v2.preprocess_input(tf.cast(img, tf.float32))
    return img, tf.one_hot(y, N_CLS), w
def ds(ids, train, bs=32):
    d = tf.data.Dataset.from_generator(gen(ids, train), output_signature=sig)
    d = d.map(augment if train else plain, num_parallel_calls=1)
    return d.batch(bs).prefetch(2)

base = keras.applications.MobileNetV2(input_shape=(224, 224, 3), include_top=False, weights='/home/claude/proj/weights/mobilenet_v2_weights_tf_dim_ordering_tf_kernels_1.0_224_no_top.h5')
base.trainable = False
inp = keras.Input((224, 224, 3)); x = base(inp, training=False); x = keras.layers.GlobalAveragePooling2D()(x)
x = keras.layers.Dense(128, activation='relu')(x); x = keras.layers.Dropout(0.3)(x)
model = keras.Model(inp, keras.layers.Dense(N_CLS, activation='softmax')(x))

def predict(ids):
    P = model.predict(ds(ids, False, 64), verbose=0); return P
def src_acc(ids):
    P = predict(ids); y = np.array([R[i]['y'] for i in ids]); pr = P.argmax(1)
    out = {}
    for s in sorted({R[i]['source'] for i in ids}):
        m = np.array([R[i]['source'] == s for i in ids]); out[s] = float((pr[m] == y[m]).mean()); out[s + '_n'] = int(m.sum())
    return out
field_val = [i for i in va if R[i]['source'] in FIELD]
HP = f'{OUT}/history.json'; BP = f'{OUT}/best.json'
hist = json.load(open(HP)) if os.path.exists(HP) else []
best = json.load(open(BP)) if os.path.exists(BP) else {'score': -1}
n_done = len(hist); counter = 0
if n_done and os.path.exists(f'{OUT}/last.weights.h5'):
    model.load_weights(f'{OUT}/last.weights.h5'); print('RESUMED after', n_done, 'epochs', flush=True)
def run_stage(epochs, lr, tag):
    global best, counter
    model.compile(keras.optimizers.Adam(lr), 'categorical_crossentropy', metrics=['accuracy'])
    for ep in range(epochs):
        counter += 1
        if counter <= n_done: continue
        t = time.time(); h = model.fit(ds(tr, True), epochs=1, verbose=0)
        v = src_acc(va); fv = [v[k] for k in v if k in FIELD]; score = float(np.mean(fv)) if fv else v['plantvillage']
        hist.append(dict(stage=tag, epoch=ep + 1, loss=float(h.history['loss'][0]), val=v, score=score, sec=round(time.time() - t)))
        print(tag, ep + 1, hist[-1], flush=True)
        model.save_weights(f'{OUT}/last.weights.h5')
        if score > best['score']:
            best = {'score': score, 'tag': tag, 'epoch': ep + 1}; model.save_weights(f'{OUT}/best.weights.h5'); json.dump(best, open(BP, 'w'))
        json.dump(hist, open(HP, 'w'), indent=1)
run_stage(a.s1_epochs, 1e-3, 's1')
base.trainable = True
for l in base.layers[:-a.unfreeze]: l.trainable = False
for l in base.layers:
    if isinstance(l, keras.layers.BatchNormalization): l.trainable = False
run_stage(a.s2_epochs, 3e-5, 's2')
model.load_weights(f'{OUT}/best.weights.h5'); print('best', best, flush=True)

# ---- final TEST (touched once) ----
def wilson(k, n, z=1.96):
    if n == 0: return [0, 0]
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [round((c - r) / d, 4), round((c + r) / d, 4)]
te = idx('test'); P = predict(te); y = np.array([R[i]['y'] for i in te]); pr = P.argmax(1)
rep = {'model': a.name, 'trained_on': sorted(train_srcs), 'best_val': best, 'test': {}}
for s in ['plantvillage', 'plantdoc', 'gitergo_field']:
    m = np.array([R[i]['source'] == s for i in te]); k = int((pr[m] == y[m]).sum()); n = int(m.sum())
    rep['test'][s] = dict(n=n, correct=k, acc=round(k / n, 4), ci95=wilson(k, n))
fm = np.array([R[i]['source'] in FIELD for i in te]); k = int((pr[fm] == y[fm]).sum()); n = int(fm.sum())
rep['test']['all_field_combined'] = dict(n=n, correct=k, acc=round(k / n, 4), ci95=wilson(k, n))
from sklearn.metrics import confusion_matrix
CL = ["CornRust", "CornGLS", "CornHealthy", "CornNLB", "PotEB", "PotHealthy", "PotLB"]
for s in ['plantdoc', 'gitergo_field']:
    m = np.array([R[i]['source'] == s for i in te])
    rep['test'][s]['per_class_recall'] = {CL[c]: [int((pr[m & (y == c)] == c).sum()), int((m & (y == c)).sum())] for c in range(N_CLS)}
    rep['test'][s]['confusion'] = confusion_matrix(y[m], pr[m], labels=list(range(N_CLS))).tolist()
json.dump(rep, open(f'{OUT}/test_report.json', 'w'), indent=1); print(json.dumps(rep['test'], indent=1))
model.save(f'{OUT}/{a.name}.keras'); np.save(f'{OUT}/test_probs.npy', P)

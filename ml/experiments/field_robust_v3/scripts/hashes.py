import glob, os, json, numpy as np
from PIL import Image
from concurrent.futures import ThreadPoolExecutor

def dhash_bits(img, n=8):
    g = img.convert('L').resize((n+1, n), Image.BILINEAR)
    a = np.asarray(g, dtype=np.int16)
    return (a[:, 1:] > a[:, :-1]).flatten()

def pack(bits):
    return int(''.join('1' if b else '0' for b in bits), 2)

def hash_file(p):
    try:
        im = Image.open(p); im.draft('RGB', (128, 128)); im = im.convert('RGB')
        h = pack(dhash_bits(im))
        hf = pack(dhash_bits(im.transpose(Image.FLIP_LEFT_RIGHT)))
        return p, h, hf
    except Exception as e:
        return p, None, None

def popcount64(x):
    x = x - ((x >> 1) & 0x5555555555555555)
    x = (x & 0x3333333333333333) + ((x >> 2) & 0x3333333333333333)
    x = (x + (x >> 4)) & 0x0f0f0f0f0f0f0f0f
    return (x * 0x0101010101010101 & 0xffffffffffffffff) >> 56

if __name__ == '__main__':
    base = '/home/claude/data/gitergo/Natural_environment'
    files = sorted(glob.glob(base + '/*/*/*'))
    with ThreadPoolExecutor(2) as ex:
        res = list(ex.map(hash_file, files))
    res = [r for r in res if r[1] is not None]
    H = np.array([r[1] for r in res], dtype=np.uint64)
    HF = np.array([r[2] for r in res], dtype=np.uint64)
    split = np.array([r[0].split('/')[-3] for r in res])
    tr = np.where(split == 'train')[0]; te = np.where(split == 'test')[0]
    leaked = 0
    for i in te:
        d = np.minimum(popcount64(H[tr] ^ H[i]), popcount64(H[tr] ^ HF[i]))
        if d.min() <= 6: leaked += 1
    print('test images', len(te), 'with near-dup (<=6 bits) in train:', leaked)
    # within-train dup rate
    dupe_in_train = 0
    for k, i in enumerate(tr[:600]):
        d = np.minimum(popcount64(H[tr] ^ H[i]), popcount64(H[tr] ^ HF[i])); d[k] = 99
        if d.min() <= 6: dupe_in_train += 1
    print('of first 600 train imgs, with near-dup elsewhere in train:', dupe_in_train)

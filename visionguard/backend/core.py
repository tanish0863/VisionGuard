"""Corruptions, matching and metrics. No model dependency, so it is fast to test."""
import cv2
import numpy as np

KINDS = ["blur", "brightness", "noise", "rotation", "jpeg", "occlusion"]


def corrupt(img, kind, s, seed=42):
    """Return (corrupted BGR image, 2x3 affine matrix or None). s in [0,1]; same seed -> same output."""
    h, w = img.shape[:2]
    rng = np.random.default_rng(seed)
    if s <= 0:
        return img.copy(), None
    if kind == "blur":
        k = int(s * 40) * 2 + 1
        return cv2.GaussianBlur(img, (k, k), 0), None
    if kind == "brightness":
        return np.clip(img * (1 - 0.9 * s), 0, 255).astype(np.uint8), None
    if kind == "noise":
        return np.clip(img + rng.normal(0, s * 90, img.shape), 0, 255).astype(np.uint8), None
    if kind == "rotation":
        m = cv2.getRotationMatrix2D((w / 2, h / 2), s * 45, 1.0)
        return cv2.warpAffine(img, m, (w, h)), m
    if kind == "jpeg":
        _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, max(2, int(95 - s * 93))])
        return cv2.imdecode(buf, cv2.IMREAD_COLOR), None
    if kind == "occlusion":  # black square covering s*50% of the image area
        side = (s * 0.5) ** 0.5
        bw, bh = int(w * side), int(h * side)
        x, y = int(rng.integers(0, max(1, w - bw))), int(rng.integers(0, max(1, h - bh)))
        out = img.copy()
        out[y:y + bh, x:x + bw] = 0
        return out, None
    raise ValueError(f"unknown corruption: {kind}")


def warp_box(box, m, w, h):
    """Move a normalized box through the same affine transform as the image (rotation only)."""
    x1, y1, x2, y2 = box[0] * w, box[1] * h, box[2] * w, box[3] * h
    pts = np.array([[x1, y1, 1], [x2, y1, 1], [x2, y2, 1], [x1, y2, 1]]) @ m.T
    xs, ys = np.clip(pts[:, 0] / w, 0, 1), np.clip(pts[:, 1] / h, 0, 1)
    return [float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())]


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def compare(base, alt, thr=0.5):
    """Match baseline detections to altered ones by class + IoU (greedy, highest confidence first)."""
    used, matched, unmatched = set(), [], []
    for i in sorted(range(len(base)), key=lambda k: -base[k]["conf"]):
        cand = [(iou(base[i]["box"], a["box"]), j) for j, a in enumerate(alt)
                if j not in used and a["label"] == base[i]["label"]]
        best = max(cand, default=(0, None))
        if best[1] is not None and best[0] >= thr:
            used.add(best[1])
            matched.append((i, best[1]))
        else:
            unmatched.append(i)
    failures = []
    for i in unmatched:  # same place, different class -> class change; otherwise the object was lost
        b = base[i]
        cand = [(iou(b["box"], a["box"]), j) for j, a in enumerate(alt) if j not in used]
        best = max(cand, default=(0, None))
        if best[1] is not None and best[0] >= thr:
            used.add(best[1])
            failures.append({"kind": "class_changed", "label": b["label"], "conf": b["conf"],
                             "box": b["box"], "to": alt[best[1]]["label"]})
        else:
            failures.append({"kind": "lost", "label": b["label"], "conf": b["conf"], "box": b["box"]})
    for j, a in enumerate(alt):
        if j not in used:
            failures.append({"kind": "spurious", "label": a["label"], "conf": a["conf"], "box": a["box"]})
    deltas = [alt[j]["conf"] - base[i]["conf"] for i, j in matched]
    count = lambda k: sum(f["kind"] == k for f in failures)
    return {
        "retention": len(matched) / len(base) if base else None,
        "conf_change": float(np.mean(deltas)) if deltas else None,
        "lost": count("lost"), "class_changes": count("class_changed"), "spurious": count("spurious"),
        "failures": failures,
    }


def report_md(run):
    c = run["config"]
    pct = lambda v: "-" if v is None else f"{v * 100:.0f}%"
    dlt = lambda v: "-" if v is None else f"{v:+.3f}"
    rows = "\n".join(
        f"| {l['severity'] * 100:.0f}% | {len(l['detections'])} | {pct(l['retention'])} | {dlt(l['conf_change'])} | "
        f"{l['lost']} | {l['class_changes']} | {l['spurious']} | {l['latency_ms']:.0f} ms |" for l in run["levels"])
    return (f"# VisionGuard report {run['id']}\n\nModel: {run['model']}  \nCondition: {c['corruption']}  \n"
            f"Severity levels: {c['levels']}  \nIoU threshold: {c['iou']}  \nSeed: {c['seed']}  \nImage: {c['filename']}\n\n"
            "| Severity | Detections | Retention | Confidence change | Lost | Class changed | Spurious | Latency |\n"
            "|---|---|---|---|---|---|---|---|\n" + rows +
            "\n\nValues are measured on this single image. Retention is not accuracy; confidence is not correctness.\n")

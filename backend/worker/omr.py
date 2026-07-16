"""OMR determinístico do cartão-resposta (server-side, escala para lote).

Replica o pipeline do OpenCV.js do frontend:
  1. alinha a foto à imagem de referência do template via ORB + homografia
     (corrige posição, rotação, zoom e perspectiva);
  2. binariza (threshold adaptativo);
  3. mede o preenchimento de cada bolha nas posições (normalizadas) do template;
  4. decide a alternativa por questão (branco '-', única letra, ou '*' múltiplas).

Depende de opencv-python-headless + numpy (layer dedicada). Import feito de forma
tardia pelo worker para não afetar as demais capacidades.
"""
import cv2
import numpy as np

_MAXW = 1000


def _decode(image_bytes):
    arr = np.frombuffer(image_bytes, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def _scale(img, maxw=_MAXW):
    h, w = img.shape[:2]
    s = min(1.0, maxw / float(w))
    return cv2.resize(img, (int(w * s), int(h * s))) if s < 1.0 else img


def _align(photo, ref):
    """Alinha `photo` ao referencial de `ref` (ORB + homografia). Retorna a imagem
    reprojetada no tamanho de `ref`, ou None se não houver casamento suficiente."""
    g1 = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY)
    g2 = cv2.cvtColor(photo, cv2.COLOR_BGR2GRAY)
    orb = cv2.ORB_create(1500)
    k1, d1 = orb.detectAndCompute(g1, None)
    k2, d2 = orb.detectAndCompute(g2, None)
    if d1 is None or d2 is None or len(k1) < 10 or len(k2) < 10:
        return None
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = sorted(bf.match(d2, d1), key=lambda m: m.distance)  # query=foto, train=ref
    good = matches[:max(15, int(len(matches) * 0.3))]
    if len(good) < 15:
        return None
    src = np.float32([k2[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([k1[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    hmat, _ = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
    if hmat is None:
        return None
    rh, rw = ref.shape[:2]
    return cv2.warpPerspective(photo, hmat, (rw, rh)), len(good)


def detect_qr(image_bytes):
    """Lê o primeiro QR code da imagem e retorna o texto (ex.: 'id001...'), ou ''.

    Testa a imagem original e versões AMPLIADAS (QR pequeno em foto de baixa resolução
    costuma falhar sem upscale) + fallback multi.
    """
    img = _decode(image_bytes)
    if img is None:
        return ""
    det = cv2.QRCodeDetector()
    h, w = img.shape[:2]
    variants = [img]
    for target_w in (1600, 2600):
        if w < target_w:
            sc = target_w / float(w)
            variants.append(cv2.resize(img, (int(w * sc), int(h * sc)),
                                       interpolation=cv2.INTER_CUBIC))
    for v in variants:
        try:
            data, _pts, _s = det.detectAndDecode(v)
            if data:
                return data.strip()
        except Exception:  # noqa: BLE001
            pass
        try:
            ok, datas, _pts, _s = det.detectAndDecodeMulti(v)
            if ok and datas:
                for d in datas:
                    if d:
                        return d.strip()
        except Exception:  # noqa: BLE001
            pass
    return ""


def read_answersheet(image_bytes, template, ref_bytes=None):
    """Lê o cartão e devolve (answers, meta).

    answers: lista de {questao, marcada, marcadas}
    meta:    {aligned: bool, matches: int, width, height}
    """
    photo = _decode(image_bytes)
    if photo is None:
        raise ValueError("Não foi possível decodificar a imagem enviada.")
    base, aligned, matches = None, False, 0
    if ref_bytes:
        ref = _decode(ref_bytes)
        if ref is not None:
            res = _align(_scale(photo), _scale(ref))
            if res is not None:
                base, matches = res[0], res[1]
                aligned = True
    if base is None:
        base = _scale(photo)

    gray = cv2.cvtColor(base, cv2.COLOR_BGR2GRAY)
    binimg = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 25, 10)
    h, w = binimg.shape[:2]
    sens = float(template.get("sensitivity", 50) or 50) / 100.0
    letters = [str(x) for x in (template.get("letters") or [])]
    default_alt = int(template.get("alternatives", 5) or 5)

    def letter(c):
        return letters[c] if c < len(letters) else chr(65 + c)

    answers = []
    for b in (template.get("blocks") or []):
        alt = int(b.get("alternatives") or default_alt)
        qs = int(b.get("questions") or 0)
        first = int(b.get("firstQuestion") or 1)
        rect = b.get("rect") or {}
        bx = float(rect.get("x", 0)) * w
        by = float(rect.get("y", 0)) * h
        bw = float(rect.get("w", 0)) * w
        bh = float(rect.get("h", 0)) * h
        if qs <= 0 or alt <= 0 or bw <= 0 or bh <= 0:
            continue
        for r in range(qs):
            marked = []
            for c in range(alt):
                cx = bx + bw * (c + 0.5) / alt
                cy = by + bh * (r + 0.5) / qs
                rad = max(4.0, min(bw / alt, bh / qs) * 0.32)
                x0, y0 = max(0, int(cx - rad)), max(0, int(cy - rad))
                x1, y1 = min(w, int(cx + rad)), min(h, int(cy + rad))
                roi = binimg[y0:y1, x0:x1]
                filled = (float(np.count_nonzero(roi)) / roi.size) if roi.size else 0.0
                if filled >= sens:
                    marked.append(c)
            if len(marked) == 1:
                answers.append({"questao": first + r, "marcada": letter(marked[0]), "marcadas": []})
            elif len(marked) >= 2:
                answers.append({"questao": first + r, "marcada": "*",
                                "marcadas": [letter(c) for c in marked]})
            else:
                answers.append({"questao": first + r, "marcada": "-", "marcadas": []})
    return answers, {"aligned": aligned, "matches": matches, "width": w, "height": h}

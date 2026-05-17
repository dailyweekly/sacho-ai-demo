"""칭호(tier) 4종 일러스트 sticker sheet 분할 → 개별 PNG 저장.

사용:
    1) 받은 sticker sheet 이미지를 ``assets/_tier_sheet.png`` 로 저장
    2) python -m scripts._split_tier_sheet
    3) 자동으로 assets/c_tier_<name>.png 4개 생성

레이아웃 (2 col × 3 row):
    [master 정면]  [master 3/4]      ← row 0
    [companion L]  [companion R]     ← row 1
    [apprentice]   [novice]          ← row 2

기본 선택 (primary):
    - master:     row 0 col 0
    - companion:  row 1 col 0
    - apprentice: row 2 col 0
    - novice:     row 2 col 1

alt 변형 (col 1 의 동작):
    - master_alt, companion_alt 도 저장 (향후 옵션)
"""
from __future__ import annotations
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("[ERROR] Pillow 미설치. pip install pillow")
    sys.exit(1)

ASSETS = Path(__file__).resolve().parents[1] / "assets"
SRC = ASSETS / "_tier_sheet.png"

if not SRC.exists():
    print(f"[ERROR] {SRC} 없음.")
    print("        sticker sheet 를 해당 경로에 저장 후 재실행:")
    print(f"        {SRC}")
    sys.exit(2)


def crop_tile(img: Image.Image, col: int, row: int,
              n_cols: int = 2, n_rows: int = 3) -> Image.Image:
    """N×M 그리드의 한 칸을 잘라냄."""
    W, H = img.size
    cw, rh = W // n_cols, H // n_rows
    box = (col * cw, row * rh, (col + 1) * cw, (row + 1) * rh)
    return img.crop(box)


def trim_beige(img: Image.Image, threshold: int = 240) -> Image.Image:
    """상하좌우 단색(베이지) 마진을 자동 트리밍.

    near-white pixels (모든 RGB > threshold) 를 배경으로 보고 가장자리 제거.
    """
    img = img.convert("RGBA")
    pixels = img.load()
    W, H = img.size
    min_x, min_y, max_x, max_y = W, H, 0, 0
    for y in range(H):
        for x in range(W):
            r, g, b, a = pixels[x, y]
            if a > 10 and not (r > threshold and g > threshold - 10
                               and b > threshold - 30):
                if x < min_x: min_x = x
                if y < min_y: min_y = y
                if x > max_x: max_x = x
                if y > max_y: max_y = y
    if min_x >= max_x or min_y >= max_y:
        return img
    pad = 8
    box = (
        max(0, min_x - pad), max(0, min_y - pad),
        min(W, max_x + pad), min(H, max_y + pad),
    )
    return img.crop(box)


def main() -> None:
    src = Image.open(SRC).convert("RGBA")
    W, H = src.size
    print(f"[INFO] sheet: {W}x{H}")

    spec = [
        (0, 0, "c_tier_master.png"),
        (1, 0, "c_tier_master_alt.png"),
        (0, 1, "c_tier_companion.png"),
        (1, 1, "c_tier_companion_alt.png"),
        (0, 2, "c_tier_apprentice.png"),
        (1, 2, "c_tier_novice.png"),
    ]

    for col, row, fname in spec:
        tile = crop_tile(src, col, row)
        tile = trim_beige(tile)
        out = ASSETS / fname
        tile.save(out, "PNG")
        print(f"  [SAVE] {fname}  ({tile.size[0]}x{tile.size[1]})")

    print()
    print("[DONE] 6 PNG 생성 (4 tier + 2 alt)")
    print("       Streamlit 캐시 무시 새로고침 시 자동 적용")


if __name__ == "__main__":
    main()

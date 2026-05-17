"""코스 thumbnail 8종 sticker sheet 분할 → 개별 PNG 저장.

사용:
    1) assets/_course_sheet.png 로 저장
    2) python -m scripts._split_course_sheet
    3) assets/course_<id>.png 8 + 1(폴백) = 9 개 생성

레이아웃 (4 col × 2 row):
    [정동]  [광화문]  [경복궁]  [덕수궁]    ← row 0
    [북촌]  [경주]    [단양]    [종로]      ← row 1

매핑:
    정동   → course_jeongdong.png
    광화문 → course_ghm_secrets.png
    경복궁 → course_gbg_inside.png
    덕수궁 → course_dsg_inside.png
    북촌   → course_bukchon_kpdh.png   (jongno_kculture 폴백)
    경주   → course_gyeongju_5.png
    단양   → course_danyang_palgyeong.png
    종로   → course_jongno_palaces.png
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
SRC = ASSETS / "_course_sheet.png"

if not SRC.exists():
    print(f"[ERROR] {SRC} 없음.")
    print(f"        코스 시트를 해당 경로에 저장 후 재실행")
    sys.exit(2)

LAYOUT = [
    (0, 0, "course_jeongdong.png"),
    (1, 0, "course_ghm_secrets.png"),
    (2, 0, "course_gbg_inside.png"),
    (3, 0, "course_dsg_inside.png"),
    (0, 1, "course_bukchon_kpdh.png"),
    (1, 1, "course_gyeongju_5.png"),
    (2, 1, "course_danyang_palgyeong.png"),
    (3, 1, "course_jongno_palaces.png"),
]


def crop_tile(img: Image.Image, col: int, row: int,
              n_cols: int = 4, n_rows: int = 2) -> Image.Image:
    W, H = img.size
    cw, rh = W // n_cols, H // n_rows
    box = (col * cw, row * rh, (col + 1) * cw, (row + 1) * rh)
    return img.crop(box)


def main() -> None:
    src = Image.open(SRC).convert("RGBA")
    W, H = src.size
    print(f"[INFO] sheet: {W}x{H}")

    for col, row, fname in LAYOUT:
        tile = crop_tile(src, col, row)
        out = ASSETS / fname
        tile.save(out, "PNG")
        print(f"  [SAVE] {fname}  ({tile.size[0]}x{tile.size[1]})")

    # jongno_kculture (K-콘텐츠 종로) — bukchon_kpdh 복사 (유사 K-content)
    fb_src = ASSETS / "course_bukchon_kpdh.png"
    fb_dst = ASSETS / "course_jongno_kculture.png"
    if fb_src.exists():
        fb_dst.write_bytes(fb_src.read_bytes())
        print(f"  [COPY] course_jongno_kculture.png  ← bukchon_kpdh (폴백)")

    print()
    print("[DONE] 8 + 1 = 9 코스 썸네일")
    print("       코스 picker preview + 진행 헤더 자동 반영")


if __name__ == "__main__":
    main()

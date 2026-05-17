"""PWA 아이콘 + OG 이미지 리사이즈 — assets 폴더에 직접 저장.

사용:
    1) assets/_pwa_icon.png — PWA 원본 (정사각, ≥512x512 권장)
    2) assets/og_share.png — OG 공유 이미지 (그대로, 리사이즈 없음)
    3) python -m scripts._resize_pwa_icon
    4) assets/icon_apple_180.png 자동 생성 (iOS apple-touch-icon)

OG 이미지는 그대로 사용 (1200x630 권장). 별도 리사이즈 없이 GitHub raw 로
직접 호스팅. app.py 의 JS 가 _GH_RAW URL 로 참조.
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
PWA_SRC = ASSETS / "_pwa_icon.png"
OG_SRC = ASSETS / "og_share.png"


def main() -> None:
    # PWA 아이콘 — 180x180 apple-touch-icon (불투명 베이지 배경)
    if not PWA_SRC.exists():
        print(f"[SKIP] {PWA_SRC} 없음 — PWA 아이콘 미생성")
    else:
        src = Image.open(PWA_SRC).convert("RGBA")
        W, H = src.size
        print(f"[INFO] PWA 원본: {W}x{H}")
        # 정사각 보장 (아니면 중앙 크롭)
        if W != H:
            side = min(W, H)
            left = (W - side) // 2
            top = (H - side) // 2
            src = src.crop((left, top, left + side, top + side))
            print(f"        → 중앙 크롭 {side}x{side}")
        # iOS apple-touch-icon: 180x180, 불투명 RGB (alpha 불가)
        resized = src.resize((180, 180), Image.LANCZOS)
        bg = Image.new("RGB", (180, 180), "#FBF1DD")
        if resized.mode == "RGBA":
            bg.paste(resized, mask=resized.split()[-1])
        else:
            bg.paste(resized)
        out = ASSETS / "icon_apple_180.png"
        bg.save(out, "PNG", optimize=True)
        print(f"  [SAVE] {out.name} (180x180)")

    # OG 이미지 — 그대로 (별도 리사이즈 없음)
    if not OG_SRC.exists():
        print(f"[SKIP] {OG_SRC} 없음 — OG 이미지 미설정")
    else:
        og = Image.open(OG_SRC)
        print(f"[INFO] OG 이미지: {og.size}  ({OG_SRC.name})")
        print(f"        그대로 사용 — github raw 직접 호스팅")

    print()
    print("[DONE] 다음 단계:")
    print("  git add assets/icon_apple_180.png assets/og_share.png "
          "assets/_pwa_icon.png")
    print("  git commit -m 'assets: OG share + Apple touch icon'")
    print("  git push  → SNS/iOS 자동 인식")


if __name__ == "__main__":
    main()

"""capture_NN_1.png + capture_NN_2.png + ... 을 세로로 stitching → capture_NN.png.

사용자가 큰 화면을 영역별로 나눠 캡처한 경우 자동 병합.
"""
from __future__ import annotations

import sys
from pathlib import Path
from collections import defaultdict

from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")

CAPTURE_DIR = Path(
    r"C:\Users\User\Desktop\세종대\2026-1학기\Capstone\경진대회 최종발표\캡처"
)


def stitch_vertical(images: list[Image.Image]) -> Image.Image:
    """이미지 리스트를 세로로 이어 붙임 (폭은 최대값 기준)."""
    max_w = max(img.width for img in images)
    total_h = sum(img.height for img in images)
    canvas = Image.new("RGB", (max_w, total_h), (255, 255, 255))
    y = 0
    for img in images:
        # 가운데 정렬
        x = (max_w - img.width) // 2
        canvas.paste(img, (x, y))
        y += img.height
    return canvas


def main() -> None:
    # capture_NN_M.png 패턴 그룹핑
    groups: dict[int, list[Path]] = defaultdict(list)
    for f in CAPTURE_DIR.glob("capture_*_*.png"):
        # capture_04_1.png → num=4, part=1
        parts = f.stem.split("_")
        if len(parts) >= 3 and parts[1].isdigit() and parts[2].isdigit():
            num = int(parts[1])
            part = int(parts[2])
            groups[num].append((part, f))

    if not groups:
        print("나뉜 캡처 (capture_NN_M.png) 없음 — 모든 캡처가 단일 파일")
        return

    print(f"합칠 그룹 {len(groups)} 개:\n")
    for num in sorted(groups):
        parts = sorted(groups[num])
        files = [p[1] for p in parts]
        print(f"  ━ capture_{num:02d} ({len(files)} 장 합침)")
        for part, f in parts:
            print(f"     - {f.name}")
        # 이미지 로드 + 합치기
        images = [Image.open(str(f)) for f in files]
        merged = stitch_vertical(images)
        out_path = CAPTURE_DIR / f"capture_{num:02d}.png"
        merged.save(str(out_path), "PNG", optimize=True)
        print(f"     → {out_path.name} ({merged.size[0]}x{merged.size[1]})")
        print()

    print("✅ 합치기 완료. 이제 python scripts/capture_helper.py fill 재실행 가능")


if __name__ == "__main__":
    main()

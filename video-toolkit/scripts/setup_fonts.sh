#!/usr/bin/env bash
# 폰트 내려받기 (모두 SIL Open Font License 1.1 — 상업적 영상·썸네일 사용 가능, 폰트 파일 자체 판매 금지)
#  - Pretendard (orioncactus/pretendard)  : 자막·화면 텍스트
#  - Black Han Sans (Google Fonts)        : 썸네일 대형 카피
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p fonts
VER=1.3.9
if [ ! -f fonts/Pretendard-Bold.otf ]; then
  curl -fsSL -o /tmp/pretendard.zip "https://github.com/orioncactus/pretendard/releases/download/v${VER}/Pretendard-${VER}.zip"
  unzip -j -o -q /tmp/pretendard.zip "public/static/Pretendard-Bold.otf" "public/static/Pretendard-Black.otf" \
    "public/static/Pretendard-Medium.otf" "LICENSE.txt" -d fonts/
  mv -f fonts/LICENSE.txt fonts/Pretendard-LICENSE.txt
  rm -f /tmp/pretendard.zip
fi
if [ ! -f fonts/BlackHanSans-Regular.ttf ]; then
  curl -fsSL -o fonts/BlackHanSans-Regular.ttf "https://raw.githubusercontent.com/google/fonts/main/ofl/blackhansans/BlackHanSans-Regular.ttf"
  curl -fsSL -o fonts/BlackHanSans-OFL.txt "https://raw.githubusercontent.com/google/fonts/main/ofl/blackhansans/OFL.txt"
fi
ls -1 fonts

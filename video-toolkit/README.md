# video-toolkit

[`video-preset.md`](../video-preset.md)의 규칙을 그대로 구현한 영상 제작 파이프라인입니다.
`project.yaml`(대본·화면 지시)과 `sources.csv`(출처)를 넣으면 다음 파일이 만들어집니다.

- 영상(mp4)
- 썸네일(누끼 합성)
- SRT 자막
- 제목·설명란

## 1. 설치

필요한 것: **Python 3.10 이상**, **ffmpeg**

```bash
# ffmpeg
#   macOS:   brew install ffmpeg
#   Ubuntu:  sudo apt install ffmpeg
#   Windows: winget install Gyan.FFmpeg   (설치 후 터미널 재시작)

cd video-toolkit
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
bash scripts/setup_fonts.sh                            # Windows는 Git Bash에서 실행하거나 아래 "폰트"를 보고 수동 설치
```

누끼 모델(`isnet-general-use`, 약 180MB)은 썸네일이나 `cutout` 요소를 처음 쓸 때 `~/.rembg/`에 자동으로 내려받아집니다.

## 2. 샘플 실행

```bash
python examples/sample/make_placeholders.py                       # 임시 이미지 생성
python make.py check  examples/sample                             # 팩트 검증 오류가 나는 것이 정상 (샘플 수치는 status: example)
python make.py render examples/sample --preview --allow-unverified   # 960×540 미리보기 (약 20초)
python make.py thumb  examples/sample
```
결과는 `examples/sample/out/` 폴더에 저장됩니다.
- `preview.mp4`: 미리보기 영상
- `thumbnail.jpg`: 썸네일
- `subtitles.srt`: 자막
- `title.txt`, `description.txt`: 제목·설명란

## 3. 새 영상 만들기

```bash
cp -r templates my-project            # project.yaml, sources.csv, assets/licenses.csv 뼈대
# 1) 자료를 모아 sources.csv에 claim 등록
# 2) project.yaml 작성 (meta, scenes, thumbnail)
# 3) 사진·음원을 my-project/assets/ 에 넣고 licenses.csv에 기록
# 4) 검증을 마친 claim은 status를 verified로, checked_by에 이름 기입
python make.py check  my-project
python make.py render my-project --preview     # 타이밍·화면 점검
python make.py all    my-project               # 본 렌더(1080p 30fps) + 썸네일 + 제목·설명·SRT
```

| 명령 | 하는 일 |
|---|---|
| `check` | 팩트 검증 상태, 출처, 라이선스, 문장 길이, 과장 표현, 예상 길이, 썸네일 문구 검사 |
| `tts` | 장면별 나레이션 합성 + 분당 350음절로 속도 보정 (캐시되므로 바뀐 장면만 다시 합성) |
| `render` | check → tts → 음성 믹스(배경음악 덕킹, −14 LUFS) → 영상 렌더 → 제목·설명·SRT |
| `thumb` | 썸네일 (주요 피사체 자동 누끼 + 테두리·그림자 합성) |
| `publish` | 제목·설명란·SRT만 다시 생성 |
| `all` | render + thumb |

옵션
- `--preview`: 절반 해상도, 15fps, 빠른 인코딩
- `--allow-unverified`: 검증 안 된 claim을 경고로만 처리합니다. 미리보기 전용이며, 이 옵션으로 만든 영상은 업로드하지 않습니다.

## 4. 설정

- 공통 설정: `config/preset.yaml`
  - 채널명·로고, 색, 폰트, 자막 크기·글자 수, 모션 곡선·시간, TTS, 음량, 썸네일
- 프로젝트별 변경: `project.yaml`의 `overrides:`에 같은 키를 적으면 덮어씁니다.

```yaml
overrides:
  channel: {name: "내채널", logo: assets/logo.png}
  tts: {provider: google, voice: ko-KR-Neural2-C, pronunciation: {HUG: 허그}}
  audio: {bgm: assets/music/bed.mp3, bgm_db: -22}
```

- 진행률바와 마지막 화면의 관련 영상 프레임은 넣지 않습니다. 설정에 `false`로 적혀 있고 렌더러에도 구현하지 않았습니다.

## 5. TTS

| provider | 준비 |
|---|---|
| `edge` (기본) | 추가 준비 없음. 인터넷이 필요합니다. 무료 비공식 서비스이므로 **수익 채널에서 쓰기 전에 약관을 확인**하세요. |
| `google` | `pip install google-cloud-texttospeech`, GCP에서 Text-to-Speech API 활성화, `export GOOGLE_APPLICATION_CREDENTIALS=키.json`. 음성 예: `ko-KR-Neural2-A/B/C`, `ko-KR-Chirp3-HD-*` |
| `file` | 직접 녹음한 파일을 `my-project/voice/<장면id>.wav`(또는 mp3·m4a)로 넣습니다. |
| `silent` | 무음. 화면·타이밍만 볼 때 씁니다. |

- 사내 프록시 환경에서 `edge`가 인증서 오류를 내면 프록시 CA를 신뢰하도록 설정하거나 `google` provider를 쓰세요.
- 한국어 상업용 TTS로는 네이버 클로바 보이스(NCP)도 있습니다. 쓰려면 `vp/tts.py`에 같은 형태의 함수를 추가하면 됩니다.

## 6. 폰트

`scripts/setup_fonts.sh`가 `fonts/` 폴더에 내려받습니다. 둘 다 **SIL OFL 1.1** 라이선스라 영상·썸네일에 상업적으로 쓸 수 있습니다. 폰트 파일 자체를 판매하는 것은 금지입니다.

| 용도 | 폰트 | 수동 설치 |
|---|---|---|
| 자막·화면 | Pretendard Bold / Black / Medium | https://github.com/orioncactus/pretendard/releases → `public/static/*.otf` |
| 썸네일 대형 카피 | Black Han Sans | https://fonts.google.com/specimen/Black+Han+Sans |

다른 폰트를 쓰려면 `preset.yaml`의 `fonts:` 경로를 바꾸세요. 상업적 사용이 허용된 폰트인지 반드시 확인해야 합니다.

## 7. 배경음악·효과음

음원은 직접 받아 `assets/music/`에 넣고, **`assets/licenses.csv`에 출처·라이선스를 기록**합니다. 레퍼런스 영상의 음원은 쓰지 않습니다.

| 출처 | 메모 |
|---|---|
| YouTube 오디오 보관함 (YouTube 스튜디오 → 오디오 보관함) | YouTube 업로드용으로 무료. 곡마다 "저작자 표시 필요" 여부를 확인하세요. |
| 공유마당 (한국저작권위원회) | 곡마다 이용 조건(CC 종류, 만료 저작물 등)이 다릅니다. |
| 유료 구독 (Artlist, Epidemic Sound 등) | 구독 기간·채널 등록 조건을 확인하세요. Content ID 오탐이 생기면 라이선스 증빙을 제출합니다. |
| 직접 제작 | 가장 안전합니다. |

- 권장: 가사 없는 로파이·미니멀 비트, BPM 85~110, 3분 이상 루프 가능한 곡
- 음량은 자동 처리됩니다: 배경음악 −20dB, 나레이션 구간 덕킹, 최종 −14 LUFS

## 8. 폴더 구조

```
video-toolkit/
  make.py               CLI
  config/preset.yaml    공통 설정
  vp/                   파이프라인 코드
    easing.py           가속·감속 곡선 (linear 미사용)
    elements.py         모션그래픽 요소 10종
    render.py           프레임 합성 → ffmpeg
    tts.py, audio.py    음성 합성·속도 보정·믹스
    cutout.py           누끼 (rembg)
    thumbnail.py        썸네일
    check.py            팩트·라이선스·규칙 검사
    publish.py          SRT·제목·설명란
  scripts/setup_fonts.sh
  templates/            새 프로젝트 뼈대
  examples/sample/      동작 확인용 샘플 (수치는 예시)
```

## 9. 문제 해결

- `폰트를 열 수 없습니다` → `bash scripts/setup_fonts.sh`를 실행하세요.
- `ffmpeg 인코딩 실패` → `ffmpeg -version`이 실행되는지 확인하세요.
- 렌더가 느릴 때 → `--preview`로 먼저 점검하세요. 본 렌더는 1분 분량에 1~2분 정도 걸립니다(CPU에 따라 다름).
- 누끼 경계가 거칠 때 → `preset.yaml`의 `thumbnail.rembg_model`을 바꿔 보세요. 인물이면 `u2net_human_seg`가 맞습니다. 그래도 거칠면 수동으로 따낸 PNG를 넣으세요.

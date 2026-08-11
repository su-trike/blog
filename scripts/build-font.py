#!/usr/bin/env python3
"""본문 글꼴 빌드 — 마루 부리 OTF → 웹용 woff2

원본 OTF를 받아 static/fonts/ 에 들어갈 woff2 두 개를 만든다.
한 번 만들어 두면 다시 돌릴 일이 거의 없지만, 굵기를 늘리거나 서브셋을
손볼 때 처음부터 다시 짜지 않으려고 남긴다.

    python3 scripts/build-font.py [원본_OTF_폴더]

원본은 저장소에 두지 않는다. 네이버 배포 페이지에서 받는다.
    https://hangeul.naver.com/font

## 라이선스 때문에 하는 일 (SIL OFL 1.1)

포맷 변환과 서브셋은 라이선스가 말하는 '수정본'에 해당한다
("by changing formats", "by deleting ... any of the components").
수정본에는 두 조항이 붙는다.

- §3 예약 글꼴 이름 금지 — 'MaruBuri'가 예약 목록에 있으므로
  글꼴 내부 name 테이블까지 'Onioni Serif'로 바꾼다. 자형은 건드리지 않는다.
- §2 저작권 안내와 라이선스 전문 동봉 — 원본 OTF에는 라이선스
  메타데이터(nameID 13/14)가 비어 있다. 여기서 채워 넣고,
  사람이 읽을 전문은 static/fonts/OFL.txt 로 따로 배포한다.

필요한 것: pip install fonttools brotli
"""

import subprocess
import sys
from pathlib import Path

try:
    from fontTools.ttLib import TTFont
except ImportError:
    sys.exit("fontTools가 없습니다.  pip install fonttools brotli")

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "static" / "fonts"
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Downloads" / "maruburi" / "OTF"

NEW_FAMILY = "Onioni Serif"
WEIGHTS = ("Regular", "Bold")

LICENSE_TEXT = (
    "This Font Software is licensed under the SIL Open Font License, Version 1.1. "
    "Based on MaruBuri by NAVER Corp. / NAVER Cultural Foundation Corp. "
    "Modified: converted to WOFF2 and subset for web delivery. "
    "Renamed per OFL Reserved Font Name clause."
)
LICENSE_URL = "https://scripts.sil.org/OFL"


def build_charset() -> str:
    """KS X 1001 상용 한글 + 본문에 쓰는 기호.

    한글 11,172자를 다 넣으면 굵기당 400KB를 넘는다. 실제 글에 나오는 글자는
    그 일부라, 완성형 상용 한글만 남겨 절반 이하로 줄인다.

    cp949로 인코딩했을 때 첫 바이트가 0xB0~0xC8인 것이 KS X 1001 완성형 영역이다.
    (둘째 바이트까지 걸러 2,350자로 더 줄일 수 있지만, 빠뜨렸을 때 글자가
    통째로 안 보이는 사고가 나므로 넉넉한 쪽을 택했다.)
    """
    hangul = []
    for cp in range(0xAC00, 0xD7A4):
        ch = chr(cp)
        try:
            encoded = ch.encode("cp949")
        except UnicodeEncodeError:
            continue
        if len(encoded) == 2 and 0xB0 <= encoded[0] <= 0xC8:
            hangul.append(ch)

    extra = (
        "".join(chr(c) for c in range(0x20, 0x7F))          # ASCII
        + "".join(chr(c) for c in range(0x3131, 0x3164))    # 낱자 (ㄱㄴㄷ, ㅏㅑㅓ)
        + "·…—–‘’“”「」『』【】〈〉《》※★☆○●◎△▲▽▼□■◇◆→←↑↓⇒"
        + "±×÷≤≥≠№℃㎡㎏㎜㎝㎞①②③④⑤⑥⑦⑧⑨⑩€£¥₩©®™°′″"
    )
    print(f"서브셋: 한글 {len(hangul):,}자 + 기타 {len(set(extra)):,}자")
    return "".join(hangul) + extra


def rename(src: Path, dst: Path, style: str) -> None:
    """name 테이블의 글꼴 이름을 갈아끼우고 라이선스 메타데이터를 심는다."""
    # recalcTimestamp=False — 안 끄면 저장할 때마다 head 테이블의 수정 시각이
    # 갱신되어, 같은 입력으로 돌려도 결과 파일의 바이트가 달라진다.
    # 그러면 git diff만 보고는 진짜 바뀐 것인지 알 수 없다.
    font = TTFont(src, recalcTimestamp=False)
    name = font["name"]

    # 플랫폼·언어별 레코드가 여러 벌 있다. 한글 레코드까지 전부 바꿔야
    # 어딘가에 'MaruBuri'가 남지 않는다.
    for rec in list(name.names):
        args = (rec.platformID, rec.platEncID, rec.langID)
        if rec.nameID == 1:      # 패밀리명
            name.setName(NEW_FAMILY, 1, *args)
        elif rec.nameID == 4:    # 전체 이름
            name.setName(f"{NEW_FAMILY} {style}", 4, *args)
        elif rec.nameID == 6:    # PostScript 이름 (공백 불가)
            name.setName(f"{NEW_FAMILY.replace(' ', '')}-{style}", 6, *args)
        elif rec.nameID == 16:   # 타이포그래픽 패밀리명
            name.setName(NEW_FAMILY, 16, *args)

    name.setName(LICENSE_TEXT, 13, 3, 1, 0x409)
    name.setName(LICENSE_URL, 14, 3, 1, 0x409)
    font.save(dst)
    font.close()


def main() -> int:
    missing = [w for w in WEIGHTS if not (SRC / f"MaruBuri-{w}.otf").exists()]
    if missing:
        print(f"원본을 찾을 수 없습니다: {SRC}")
        print(f"  없는 파일: {', '.join(f'MaruBuri-{w}.otf' for w in missing)}")
        print("  https://hangeul.naver.com/font 에서 받은 뒤 경로를 인자로 주십시오.")
        return 1

    charset = build_charset()
    charset_file = OUT / ".charset.tmp"
    charset_file.write_text(charset, encoding="utf-8")

    try:
        for style in WEIGHTS:
            renamed = OUT / f".{style}.tmp.otf"
            rename(SRC / f"MaruBuri-{style}.otf", renamed, style)
            subprocess.run(
                [
                    sys.executable, "-m", "fontTools.subset", str(renamed),
                    f"--text-file={charset_file}",
                    "--flavor=woff2",
                    "--layout-features=*",
                    "--desubroutinize",
                    # 이름·라이선스 레코드는 살린다. 서브셋 기본값은 이것들을 버린다.
                    "--name-IDs=0,1,2,3,4,5,6,13,14",
                    f"--output-file={OUT}/onioni-serif-{style.lower()}.woff2",
                ],
                check=True,
            )
            renamed.unlink()
    finally:
        charset_file.unlink(missing_ok=True)

    print("\n=== 생성된 파일 ===")
    failed = False
    for path in sorted(OUT.glob("onioni-serif-*.woff2")):
        font = TTFont(path)
        records = font["name"].names
        family = next(str(r) for r in records if r.nameID == 1)
        has_license = any(r.nameID == 13 for r in records)
        # §3이 막는 것은 "사용자에게 보이는 기본 글꼴 이름"이다(1·4·6·16).
        # 라이선스 설명(13)에 원본이 마루 부리임을 밝히는 것은 위반이 아니라
        # §4가 허용하는 출처 표기다. 여기를 뭉뚱그려 검사하면 멀쩡한 글꼴이
        # 위반으로 잡힌다.
        leftovers = [f"nameID {r.nameID}: {r}" for r in records
                     if r.nameID in (1, 4, 6, 16) and "MaruBuri" in str(r)]
        font.close()
        print(f"  {path.name:<28} {path.stat().st_size // 1024:>4}KB  "
              f"패밀리명={family!r}  라이선스메타={has_license}")
        for item in leftovers:
            print(f"    ✗ 예약 글꼴 이름이 남아 있습니다 — {item}")
            failed = True
        if not has_license:
            print("    ✗ 라이선스 메타데이터(nameID 13)가 비어 있습니다")
            failed = True
    if failed:
        return 1
    print("  ✓ 사용자에게 보이는 이름에 예약 글꼴 이름(MaruBuri) 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())

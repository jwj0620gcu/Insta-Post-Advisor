"""
원클릭으로 전체 연구 파이프라인 실행.
데이터 가용성에 따라 데이터 없는 단계를 자동으로 건너뜁니다.

Usage:
    python scripts/research/run_all.py [--skip-llm] [--skip-download]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PYTHON = sys.executable

STEPS = [
    ("01_normalize",           "01_import_data.py",           "데이터 가져오기 및 정제",    False),
    ("02_download",            "02_download_covers.py",       "커버 이미지 다운로드",        True),
    ("03_traditional",         "03_traditional_analysis.py",  "전통 통계 분석",              False),
    ("04_cover_vision",        "04_llm_analysis.py --covers", "커버 비주얼 분석 (omni)",     True),
    ("05_content_llm",         "04_llm_analysis.py --content","콘텐츠 패턴 분석 (pro)",      True),
    ("06_tag_llm",             "04_llm_analysis.py --tags",   "태그 전략 분석 (pro)",        True),
    ("07_persona",             "06_user_persona.py",          "사용자 페르소나",             True),
    ("08_scoring_model",       "08_build_scoring_model.py",   "평가 모델 구축",              False),
    ("09_prompts",             "09_generate_prompts.py",      "강화 프롬프트 생성",          True),
    ("10_validate",            "10_validate_model.py",        "모델 검증",                   False),
    ("11_report",              "11_final_report.py",          "최종 보고서",                 True),
]


def run_step(script: str, desc: str, skip_llm: bool, is_llm: bool) -> bool:
    if skip_llm and is_llm:
        print(f"  ⊘ 건너뜀 (--skip-llm): {desc}")
        return True

    parts = script.split()
    cmd = [PYTHON, str(SCRIPT_DIR / parts[0])] + parts[1:]

    print(f"\n{'='*60}")
    print(f"  ▶ {desc}")
    print(f"    {' '.join(cmd)}")
    print(f"{'='*60}")

    t0 = time.time()
    result = subprocess.run(cmd, cwd=str(SCRIPT_DIR.parent.parent))
    elapsed = time.time() - t0

    if result.returncode == 0:
        print(f"  ✓ 완료 ({elapsed:.1f}s)")
        return True
    else:
        print(f"  ✗ 실패 (exit={result.returncode}, {elapsed:.1f}s)")
        return False


def main():
    parser = argparse.ArgumentParser(description="전체 연구 파이프라인 실행")
    parser.add_argument("--skip-llm", action="store_true", help="모든 LLM 호출 단계 건너뜀")
    parser.add_argument("--skip-download", action="store_true", help="이미지 다운로드 건너뜀")
    parser.add_argument("--from-step", type=int, default=1, help="N번째 단계부터 시작")
    args = parser.parse_args()

    print("=" * 60)
    print("NoteRx 연구 파이프라인 — 전체 흐름")
    print("=" * 60)

    t_start = time.time()
    results = []

    for i, (name, script, desc, is_llm) in enumerate(STEPS, 1):
        if i < args.from_step:
            continue
        if args.skip_download and "download" in name:
            print(f"  ⊘ 건너뜀 (--skip-download): {desc}")
            results.append((desc, True))
            continue

        ok = run_step(script, desc, args.skip_llm, is_llm)
        results.append((desc, ok))

        if not ok and not is_llm:
            print(f"\n핵심 단계 실패, 파이프라인 중단")
            break

    # 요약
    total = time.time() - t_start
    print(f"\n{'='*60}")
    print(f"파이프라인 완료 ({total:.0f}s)")
    print(f"{'='*60}")
    for desc, ok in results:
        status = "✓" if ok else "✗"
        print(f"  {status} {desc}")


if __name__ == "__main__":
    main()

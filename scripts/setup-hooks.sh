#!/usr/bin/env bash
# AI Sherpa — pre-commit hook 활성화 스크립트
#
# 사용법: bash scripts/setup-hooks.sh
#
# 효과: .git/hooks 가 아닌 .githooks/ 디렉토리를 hook 경로로 지정.
# .githooks/ 는 git 에 포함되어 있어 모든 팀원이 같은 hook 사용 가능.

set -e

# repo 루트로 이동
cd "$(dirname "$0")/.."

git config core.hooksPath .githooks

# 실행 권한 부여 (POSIX 시스템)
if [ -x .githooks/pre-commit ] || chmod +x .githooks/pre-commit 2>/dev/null; then
  echo "✅ pre-commit hook 활성화 완료"
  echo "   core.hooksPath = $(git config core.hooksPath)"
else
  echo "⚠ pre-commit 실행 권한 설정 실패 (Windows git-bash 에서는 정상)"
fi

echo ""
echo "검사 항목:"
echo "  • .py  → SyntaxError (a8b9362 들여쓰기 회귀 방지)"
echo "  • .ts/.tsx → tsc --noEmit"
echo "  • .json → JSON 유효성"
echo ""
echo "임시 우회: git commit --no-verify  (긴급 시에만)"

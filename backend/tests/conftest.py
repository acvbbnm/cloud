"""pytest conftest — backend 패키지 import 경로 + 공용 fixture.

backend/ 디렉토리에서 pytest 실행 시 core/, db/, api/ 모듈을 import 할 수 있도록
sys.path 에 backend 추가.
"""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

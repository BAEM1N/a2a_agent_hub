"""Agent Hub Configuration."""

import os

# 로그인 필요 여부 (환경변수 AUTH_REQUIRED=false로 비활성화)
AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "true").lower() == "true"

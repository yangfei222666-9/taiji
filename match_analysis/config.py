"""配置"""
from __future__ import annotations

import os


class Settings:
    API_FOOTBALL_KEY: str = os.getenv("API_FOOTBALL_KEY", "")
    DATA_SOURCE: str = os.getenv("DATA_SOURCE", "api-football")  # "mock" | "api-football"
    API_FOOTBALL_BASE: str = "https://v3.football.api-sports.io"
    THE_ODDS_API_KEY: str = os.getenv("THE_ODDS_API_KEY", "")
    THE_ODDS_API_BASE: str = "https://api.the-odds-api.com/v4"

    def validate(self):
        if self.DATA_SOURCE == "api-football" and not self.API_FOOTBALL_KEY:
            raise RuntimeError(
                "API_FOOTBALL_KEY 环境变量未设置。\n"
                "请设置后重启：export API_FOOTBALL_KEY='your_key'\n"
                "或切换到 mock 模式：export DATA_SOURCE=mock"
            )


settings = Settings()

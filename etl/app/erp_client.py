"""Đẩy dữ liệu sạch sang ERP API (C#) theo từng batch."""
from __future__ import annotations

import os
from dataclasses import dataclass

import httpx
import pandas as pd

BATCH_SIZE = 500


@dataclass
class PushResult:
    received: int = 0
    inserted: int = 0
    skipped: int = 0


class ErpClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None, timeout: float = 30):
        self.base_url = (base_url or os.getenv("ERP_API_URL", "http://localhost:5080")).rstrip("/")
        self.api_key = api_key or os.getenv("ERP_API_KEY", "dev-api-key-change-me")
        self.timeout = timeout

    def push(self, clean: pd.DataFrame) -> PushResult:
        total = PushResult()
        items = [self._to_payload(row) for row in clean.to_dict("records")]
        with httpx.Client(base_url=self.base_url, timeout=self.timeout,
                          headers={"X-Api-Key": self.api_key}) as client:
            for start in range(0, len(items), BATCH_SIZE):
                resp = client.post("/api/material-transactions/batch", json={"items": items[start:start + BATCH_SIZE]})
                if resp.status_code == 400:
                    raise ValueError(f"ERP từ chối batch: {resp.json()}")
                resp.raise_for_status()
                body = resp.json()
                total.received += body["received"]
                total.inserted += body["inserted"]
                total.skipped += body["skipped"]
        return total

    def site_summary(self, date_from: str | None = None, date_to: str | None = None) -> list[dict]:
        params = {k: v for k, v in {"from": date_from, "to": date_to}.items() if v}
        resp = httpx.get(f"{self.base_url}/api/reports/site-summary", params=params,
                         headers={"X-Api-Key": self.api_key}, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _to_payload(r: dict) -> dict:
        # Số tiền và số lượng gửi dạng chuỗi Decimal để không bị sai số float khi qua JSON
        return {
            "site_code": r["site_code"],
            "date": r["date"].isoformat(),
            "material_code": r["material_code"],
            "material_name": r["material_name"],
            "unit": r["unit"],
            "quantity": str(r["quantity"]),
            "unit_price": str(r["unit_price"]),
            "amount": str(r["amount"]),
            "row_hash": r["row_hash"],
            "source_file": r["source_file"],
            "source_sheet": r["source_sheet"],
            "source_row": int(r["source_row"]),
        }

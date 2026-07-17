import os

from dotenv import load_dotenv
load_dotenv()

import aiohttp

WEB_API_BASE_URL = os.environ.get("WEB_API_BASE_URL", "http://localhost:5000/api")
INTERNAL_API_TOKEN = os.environ.get("INTERNAL_API_TOKEN", "dev-internal-token")

HEADERS = {"X-Internal-Token": INTERNAL_API_TOKEN, "Content-Type": "application/json"}


class ApiClient:
    """Web platforma bilan ishlaydigan yengil HTTP klient (ikkala bot ham foydalanadi)."""

    def __init__(self, base_url: str = WEB_API_BASE_URL):
        self.base_url = base_url.rstrip("/")

    async def _request(self, method: str, path: str, **kwargs):
        url = f"{self.base_url}{path}"
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            async with session.request(method, url, **kwargs) as resp:
                data = await resp.json()
                return resp.status, data

    # --- Mijoz (Bot №1) ---
    async def upsert_customer(self, telegram_id, full_name=None, phone=None, language="uz"):
        return await self._request("POST", "/customers", json={
            "telegram_id": telegram_id, "full_name": full_name, "phone": phone, "language": language
        })

    async def list_categories(self, lang="uz"):
        return await self._request("GET", f"/categories?lang={lang}")

    async def list_departments(self):
        return await self._request("GET", "/departments")

    async def list_buildings(self):
        return await self._request("GET", "/buildings")

    async def create_request(self, telegram_id, category_id, description,
                              org_department=None, org_division=None, org_is_independent=False,
                              room_number=None, address_text=None, attachments=None, building_id=None):
        return await self._request("POST", "/requests", json={
            "telegram_id": telegram_id, "category_id": category_id, "description": description,
            "org_department": org_department, "org_division": org_division,
            "org_is_independent": org_is_independent, "room_number": room_number,
            "address_text": address_text, "attachments": attachments or [], "building_id": building_id,
        })

    async def list_customer_requests(self, telegram_id):
        return await self._request("GET", f"/requests/customer/{telegram_id}")

    async def get_request(self, request_id):
        return await self._request("GET", f"/requests/{request_id}")

    async def rate_request(self, request_id, stars, comment=None, suggestion=None):
        return await self._request("POST", f"/requests/{request_id}/rate", json={
            "stars": stars, "comment": comment, "suggestion": suggestion
        })

    # --- Ijrochi (Bot №2) ---
    async def executor_tasks(self, telegram_id):
        return await self._request("GET", f"/executors/{telegram_id}/tasks")

    async def respond_assignment(self, assignment_id, decision, reason=None):
        return await self._request("POST", f"/assignments/{assignment_id}/respond", json={
            "decision": decision, "reason": reason
        })

    async def start_assignment(self, assignment_id):
        return await self._request("POST", f"/assignments/{assignment_id}/start")

    async def request_more_info(self, assignment_id, question):
        return await self._request("POST", f"/assignments/{assignment_id}/request-info", json={
            "question": question
        })

    async def complete_assignment(self, assignment_id, report_text, time_spent_minutes=None, attachments=None):
        return await self._request("POST", f"/assignments/{assignment_id}/complete", json={
            "report_text": report_text, "time_spent_minutes": time_spent_minutes,
            "attachments": attachments or [],
        })

    async def extend_assignment(self, assignment_id, extra_hours, reason):
        return await self._request("POST", f"/assignments/{assignment_id}/extend", json={
            "extra_hours": extra_hours, "reason": reason
        })


api_client = ApiClient()

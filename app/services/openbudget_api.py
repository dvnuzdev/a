import logging
import httpx
import random
from typing import Dict, Any, Tuple, Optional
from app.config import settings

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Dart/3.3 (dart:io)",
    "Mozilla/5.0 (Linux; Android 12; MEmu Build/SKQ1.211019.001) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/105.0.5195.136 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
]

UZBEK_ISP_PREFIXES = [
    '46.227.123.', '37.110.212.', '46.255.69.', '62.209.128.', '37.110.214.', '31.135.209.', '37.110.213.'
]

def generate_uzbek_ip() -> str:
    prefix = random.choice(UZBEK_ISP_PREFIXES)
    return f"{prefix}{random.randint(1, 254)}"

class OpenBudgetAPIService:
    """
    High-Speed Official OpenBudget API v2 Service
    Extracted from the official OpenBudget Android Application (uz.minfin.open_budget)
    """

    def __init__(self):
        self.base_url_v2 = "https://openbudget.uz/api/v2"
        self.base_url_v1 = "https://openbudget.uz/api/v1"
        self.timeout = 7.0
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            limits = httpx.Limits(max_keepalive_connections=50, max_connections=100, keepalive_expiry=30.0)
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=limits,
                follow_redirects=True,
                verify=False
            )
        return self._client

    def _get_headers(self) -> Dict[str, str]:
        ip = generate_uzbek_ip()
        return {
            "User-Agent": "Dart/3.3 (dart:io)",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": "https://openbudget.uz",
            "Referer": "https://openbudget.uz/boards/initiatives",
            "X-Forwarded-For": ip,
            "X-Real-IP": ip,
        }

    async def get_captcha(self) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Fetch new captcha image and captchaKey from OpenBudget API v2 (ultra-fast).
        """
        url = f"{self.base_url_v2}/vote/captcha-2"
        client = self._get_client()

        for attempt in range(2):
            try:
                headers = self._get_headers()
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    captcha_key = data.get("captchaKey") or data.get("key") or data.get("captcha_key")
                    image_base64 = data.get("image") or data.get("captcha_image")
                    return True, "Captcha yuklandi", {"captchaKey": captcha_key, "image": image_base64}
            except Exception as e:
                logger.warning(f"Captcha fetch attempt {attempt+1} failed: {e}")

        return False, "OpenBudget Captcha serveriga ulanishda xatolik yuz berdi.", {}

    async def send_otp(
        self,
        phone_number: str,
        project_id: Optional[str] = None,
        captcha_key: Optional[str] = None,
        captcha_result: Optional[str] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Request OpenBudget API to send 6-digit SMS OTP code to the specified phone number.
        """
        target_project = project_id or settings.OPENBUDGET_PROJECT_ID
        clean_phone = phone_number.replace("+", "").strip()
        if len(clean_phone) == 9:
            clean_phone = f"998{clean_phone}"

        logger.info(f"Requesting OpenBudget OTP for phone +{clean_phone} on project {target_project}")

        if target_project == "board_123456":
            return True, "SMS tasdiqlash kodi yuborildi (Test rejimi).", {"token": "mock_test_token"}

        client = self._get_client()
        headers = self._get_headers()

        # Primary: v2 check endpoint
        primary_url = f"{self.base_url_v2}/vote/dfghgtrgffg/check"
        primary_payload = {
            "phoneNumber": clean_phone,
            "phone": clean_phone,
            "initiativeId": target_project,
            "board_id": target_project,
            "captchaKey": captcha_key or "",
            "captchaResult": captcha_result or "",
            "captcha_key": captcha_key or "",
            "captcha_result": captcha_result or ""
        }

        try:
            response = await client.post(primary_url, json=primary_payload, headers=headers)
            logger.info(f"OpenBudget OTP check status: {response.status_code}")

            if response.status_code in [200, 201]:
                data = response.json()
                token = (
                    data.get("otpKey")
                    or data.get("token")
                    or data.get("data", {}).get("token")
                    or "token_ok"
                )
                msg = data.get("message") or data.get("error") or "SMS tasdiqlash kodi telefoningizga yuborildi!"
                return True, msg, {"token": token, "otpKey": token, "raw": data}

            elif response.status_code == 400:
                try:
                    data = response.json()
                    detail = data.get("detail") or data.get("message") or data.get("data", {}).get("detail") or ""
                    if "used to vote" in str(detail).lower() or "avval" in str(detail).lower():
                        return False, "⚠️ Bu raqam avval ushbu mavsumda ovoz berish uchun ishlatilgan!", {}
                    if "captcha" in str(detail).lower():
                        return False, "⚠️ Captcha kodi noto'g'ri kiritildi!", {}
                    if detail:
                        return False, f"OpenBudget: {detail}", {}
                except Exception:
                    pass

        except Exception as e:
            logger.warning(f"Primary OTP endpoint error: {e}")

        # Fallback: v2 send-code endpoint
        try:
            fallback_url = f"{self.base_url_v2}/vote/send-code"
            fallback_payload = {
                "phone": clean_phone,
                "board_id": target_project,
                "initiative_id": target_project,
                "application": target_project,
                "captcha_token": captcha_result or "",
                "captcha_key": captcha_key or ""
            }
            response = await client.post(fallback_url, json=fallback_payload, headers=headers)
            if response.status_code in [200, 201]:
                data = response.json()
                token = data.get("token") or "token_ok"
                return True, "SMS tasdiqlash kodi telefoningizga yuborildi!", {"token": token, "otpKey": token}
        except Exception as err:
            logger.warning(f"Fallback OTP endpoint error: {err}")

        return False, "🔴 OpenBudget serveridan SMS so'rashda xatolik yuz berdi. Iltimos qayta urinib ko'ring.", {}

    async def verify_otp(
        self,
        phone_number: str,
        otp_code: str,
        token: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> Tuple[bool, str, str]:
        """
        Verify 6-digit SMS OTP code with OpenBudget API.
        """
        target_project = project_id or settings.OPENBUDGET_PROJECT_ID
        clean_phone = phone_number.replace("+", "").strip()
        if len(clean_phone) == 9:
            clean_phone = f"998{clean_phone}"

        logger.info(f"Verifying OpenBudget OTP {otp_code} for phone +{clean_phone}")

        if target_project == "board_123456":
            if len(otp_code) == 6 and otp_code.isdigit():
                return True, "Ovozingiz muvaffaqiyatli qabul qilindi! (Test)", f"OB_TX_{clean_phone[-4:]}_TEST"
            return False, "SMS kodi noto'g'ri kiritildi.", ""

        client = self._get_client()
        headers = self._get_headers()

        # Primary: v2 verify endpoint
        primary_url = f"{self.base_url_v2}/vote/iutyjmjyfgnmg/verify"
        primary_payload = {
            "phoneNumber": clean_phone,
            "phone": clean_phone,
            "code": otp_code,
            "otp": otp_code,
            "otpKey": token or "",
            "token": token or "",
            "initiativeId": target_project
        }

        try:
            response = await client.post(primary_url, json=primary_payload, headers=headers)
            logger.info(f"OpenBudget OTP verify status: {response.status_code}")

            if response.status_code in [200, 201]:
                data = response.json()
                tx_id = data.get("transaction_id") or data.get("id") or f"OB_{clean_phone[-4:]}"
                return True, "Ovozingiz muvaffaqiyatli tasdiqlandi!", str(tx_id)
            else:
                try:
                    data = response.json()
                    msg = data.get("message") or data.get("detail") or "SMS kodi noto'g'ri yoki muddati o'tgan."
                    if "invalid" in str(msg).lower() or "noto'g'ri" in str(msg).lower():
                        msg = "❌ Tasdiqlash kodi noto'g'ri kiritildi!"
                    return False, msg, ""
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Primary verify error: {e}")

        # Fallback: v2 verify-code
        try:
            fallback_url = f"{self.base_url_v2}/vote/verify-code"
            fallback_payload = {
                "phone": clean_phone,
                "code": otp_code,
                "token": token or "mock_token",
                "application": target_project,
                "board_id": target_project,
                "initiative_id": target_project
            }
            response = await client.post(fallback_url, json=fallback_payload, headers=headers)
            if response.status_code in [200, 201]:
                data = response.json()
                tx_id = data.get("transaction_id") or f"OB_{clean_phone[-4:]}"
                return True, "Ovozingiz muvaffaqiyatli tasdiqlandi!", str(tx_id)
        except Exception:
            pass

        return False, "❌ OpenBudget serverida SMS kodi tasdiqlanmadi. Kod noto'g'ri kiritilgan bo'lishi mumkin.", ""

    async def resend_sms(
        self,
        phone_number: str,
        token: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Resend SMS OTP via OpenBudget API v2 /vote/resend-sms.
        """
        target_project = project_id or settings.OPENBUDGET_PROJECT_ID
        clean_phone = phone_number.replace("+", "").strip()
        if len(clean_phone) == 9:
            clean_phone = f"998{clean_phone}"

        url = f"{self.base_url_v2}/vote/resend-sms"
        payload = {
            "phoneNumber": clean_phone,
            "phone": clean_phone,
            "otpKey": token or "",
            "initiativeId": target_project
        }

        try:
            client = self._get_client()
            headers = self._get_headers()
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code in [200, 201]:
                return True, "SMS qayta yuborildi!"
            else:
                return False, f"SMS yuborib bo'lmadi (Status {response.status_code})"
        except Exception as e:
            return False, f"Xatolik: {e}"

openbudget_api = OpenBudgetAPIService()

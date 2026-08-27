import logging
import httpx
import random
from typing import Dict, Any, Tuple, Optional
from app.config import settings

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Dart/3.3 (dart:io)",
    "Mozilla/5.0 (Linux; Android 12; MEmu Build/SKQ1.211019.001) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/105.0.5195.136 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1"
]

UZBEK_ISP_PREFIXES = [
    '46.227.123.', '37.110.212.', '46.255.69.', '62.209.128.', '37.110.214.', '31.135.209.', '37.110.213.'
]

def generate_uzbek_ip() -> str:
    prefix = random.choice(UZBEK_ISP_PREFIXES)
    return f"{prefix}{random.randint(1, 254)}"

class OpenBudgetAPIService:
    """
    Official OpenBudget API v2 Service
    Extracted from the official OpenBudget Android Application (uz.minfin.open_budget)
    """

    def __init__(self):
        self.base_url_v2 = "https://openbudget.uz/api/v2"
        self.base_url_v1 = "https://openbudget.uz/api/v1"
        self.timeout = 15.0

    def _get_headers(self, host: str = "openbudget.uz") -> Dict[str, str]:
        ip = generate_uzbek_ip()
        return {
            "Host": host,
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": f"https://{host}",
            "Referer": f"https://{host}/boards/initiatives",
            "REMOTE_ADDR": ip,
            "HTTP_X_FORWARDED_FOR": ip,
            "HTTP_X_REAL_IP": ip,
            "X-Forwarded-For": ip,
        }

    async def get_captcha(self) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Fetch new captcha image and captchaKey from OpenBudget API v2.
        Returns: (success: bool, message: str, data: dict with 'captchaKey' and 'image' base64)
        """
        url = f"{self.base_url_v2}/vote/captcha-2"
        headers = self._get_headers()

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, verify=False) as client:
            try:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    captcha_key = data.get("captchaKey") or data.get("key") or data.get("captcha_key")
                    image_base64 = data.get("image") or data.get("captcha_image")
                    return True, "Captcha yuklandi", {"captchaKey": captcha_key, "image": image_base64}
                else:
                    return False, f"Captcha olishda xatolik (Status {response.status_code})", {}
            except Exception as e:
                logger.error(f"Error fetching OpenBudget captcha: {e}")
                return False, f"OpenBudget Captcha serveriga ulanishda xatolik: {e}", {}

    async def send_otp(
        self,
        phone_number: str,
        project_id: Optional[str] = None,
        captcha_key: Optional[str] = None,
        captcha_result: Optional[str] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Request OpenBudget API to send 6-digit SMS OTP code to the specified phone number.
        Uses the v2 obfuscated /check endpoint extracted from the official APK.
        Returns: (success: bool, message: str, extra_data: dict)
        """
        target_project = project_id or settings.OPENBUDGET_PROJECT_ID
        clean_phone = phone_number.replace("+", "").strip()
        if len(clean_phone) == 9:
            clean_phone = f"998{clean_phone}"

        logger.info(f"Requesting OpenBudget OTP for phone +{clean_phone} on project {target_project}")

        # Development/Test mode fallback for local test board only
        if target_project == "board_123456":
            return True, "SMS tasdiqlash kodi yuborildi (Test rejimi).", {"token": "mock_test_token"}

        # Multiple endpoint strategies (Official v2 obfuscated endpoint first, then standard v2/v1)
        strategies = [
            (
                f"{self.base_url_v2}/vote/dfghgtrgffg/check",
                {
                    "phoneNumber": clean_phone,
                    "phone": clean_phone,
                    "initiativeId": target_project,
                    "board_id": target_project,
                    "captchaKey": captcha_key or "",
                    "captchaResult": captcha_result or "",
                    "captcha_key": captcha_key or "",
                    "captcha_result": captcha_result or ""
                }
            ),
            (
                f"{self.base_url_v2}/vote/send-code",
                {
                    "phone": clean_phone,
                    "board_id": target_project,
                    "initiative_id": target_project,
                    "application": target_project,
                    "captcha_token": captcha_result or "",
                    "captcha_key": captcha_key or ""
                }
            ),
            (
                f"{self.base_url_v1}/user/validate_phone/",
                {
                    "phone": clean_phone,
                    "initiative_id": target_project
                }
            )
        ]

        last_error_msg = "OpenBudget API serveridan SMS so'rashda ulanish uzildi."

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, verify=False) as client:
            for url, payload in strategies:
                try:
                    headers = self._get_headers()
                    response = await client.post(url, json=payload, headers=headers)
                    logger.info(f"OpenBudget OTP status {response.status_code} from {url}")

                    if response.status_code in [200, 201]:
                        data = response.json()
                        if isinstance(data, dict):
                            token = (
                                data.get("otpKey")
                                or data.get("token")
                                or data.get("data", {}).get("token")
                                or "token_ok"
                            )
                            msg = data.get("message") or data.get("error") or "SMS tasdiqlash kodi telefoningizga yuborildi!"
                            return True, msg, {"token": token, "otpKey": token, "raw": data}
                        return True, "SMS tasdiqlash kodi telefoningizga yuborildi!", {"token": "token_ok"}

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

                    elif response.status_code == 404:
                        continue
                    else:
                        last_error_msg = f"OpenBudget server javobi (HTTP {response.status_code})."
                except httpx.HTTPError as err:
                    logger.warning(f"Endpoint {url} failed: {err}")
                    last_error_msg = f"OpenBudget serveriga ulanishda xatolik ({err})."
                    continue

        return False, f"🔴 {last_error_msg} Iltimos qayta urinib ko'ring.", {}

    async def verify_otp(
        self,
        phone_number: str,
        otp_code: str,
        token: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> Tuple[bool, str, str]:
        """
        Verify 6-digit SMS OTP code with OpenBudget API.
        Uses the v2 obfuscated /verify endpoint extracted from the official APK.
        Returns: (success: bool, message: str, transaction_id: str)
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

        strategies = [
            (
                f"{self.base_url_v2}/vote/iutyjmjyfgnmg/verify",
                {
                    "phoneNumber": clean_phone,
                    "phone": clean_phone,
                    "code": otp_code,
                    "otp": otp_code,
                    "otpKey": token or "",
                    "token": token or "",
                    "initiativeId": target_project
                }
            ),
            (
                f"{self.base_url_v2}/vote/verify-code",
                {
                    "phone": clean_phone,
                    "code": otp_code,
                    "token": token or "mock_token",
                    "application": target_project,
                    "board_id": target_project,
                    "initiative_id": target_project
                }
            ),
            (
                f"{self.base_url_v1}/user/temp/vote/",
                {
                    "phone": clean_phone,
                    "code": otp_code,
                    "initiative_id": target_project
                }
            )
        ]

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, verify=False) as client:
            for url, payload in strategies:
                try:
                    headers = self._get_headers()
                    response = await client.post(url, json=payload, headers=headers)
                    logger.info(f"OpenBudget verify status {response.status_code} from {url}")

                    if response.status_code in [200, 201]:
                        data = response.json()
                        tx_id = data.get("transaction_id") or data.get("id") or f"OB_{clean_phone[-4:]}"
                        return True, "Ovozingiz muvaffaqiyatli tasdiqlandi!", str(tx_id)
                    elif response.status_code == 404:
                        continue
                    else:
                        try:
                            data = response.json()
                            msg = data.get("message") or data.get("detail") or "SMS kodi noto'g'ri yoki muddati o'tgan."
                            if "invalid" in str(msg).lower() or "noto'g'ri" in str(msg).lower():
                                msg = "❌ Tasdiqlash kodi noto'g'ri kiritildi!"
                            return False, msg, ""
                        except Exception:
                            return False, "SMS kodi noto'g'ri kiritildi.", ""

                except httpx.HTTPError as err:
                    logger.warning(f"Verify endpoint {url} failed: {err}")
                    continue

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

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, verify=False) as client:
            try:
                headers = self._get_headers()
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code in [200, 201]:
                    return True, "SMS qayta yuborildi!"
                else:
                    return False, f"SMS yuborib bo'lmadi (Status {response.status_code})"
            except Exception as e:
                return False, f"Xatolik: {e}"

openbudget_api = OpenBudgetAPIService()

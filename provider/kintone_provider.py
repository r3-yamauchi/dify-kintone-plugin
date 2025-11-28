from typing import Any

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError


def _normalize_domain(raw_domain: Any) -> str:
    """kintoneドメイン入力を正規化する（common.py と同等のロジックをローカル実装）。

    - http:// または https:// で始まる場合はスキームを保持する
    - スキームがない場合は https:// を先頭に自動付与する
    - 末尾のスラッシュは除去する
    """

    if not isinstance(raw_domain, str):
        raise ValueError("domain must be a string")
    domain = raw_domain.strip()
    if not domain:
        raise ValueError("domain is empty")
    if not domain.startswith(("http://", "https://")):
        domain = f"https://{domain}"
    return domain.rstrip("/")


class KintoneProvider(ToolProvider):
    """kintone プロバイダーの認証情報を管理する。"""

    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        """ドメインとAPIトークンが同時に空でないことを検証する。"""

        domain = credentials.get("kintone_domain")
        token = credentials.get("kintone_api_token")

        if self._is_blank(domain) and self._is_blank(token):
            raise ToolProviderCredentialValidationError(
                "kintone_domain か kintone_api_token のいずれかは設定してください。"
            )

        # ドメインが入力されている場合は正規化し、http/https付きも許容する
        if not self._is_blank(domain):
            try:
                credentials["kintone_domain"] = _normalize_domain(domain)
            except Exception as exc:  # noqa: BLE001
                raise ToolProviderCredentialValidationError(
                    f"kintone_domain の形式が不正です: {domain!r}"
                ) from exc

    @staticmethod
    def _is_blank(value: Any) -> bool:
        """空文字や未指定値を判定する。"""

        if value is None:
            return True
        if isinstance(value, str) and value.strip() == "":
            return True
        return False

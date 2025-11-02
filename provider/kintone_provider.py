"""
# where: kintone_integration/provider/kintone_provider.py
# what: プロバイダー設定に登録されたkintone認証情報を扱うクラス
# why: フォールバック用の認証情報を任意入力で保持しつつ、ツール側での個別指定を許容するため
"""

from typing import Any

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError


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

    @staticmethod
    def _is_blank(value: Any) -> bool:
        """空文字や未指定値を判定する。"""

        if value is None:
            return True
        if isinstance(value, str) and value.strip() == "":
            return True
        return False

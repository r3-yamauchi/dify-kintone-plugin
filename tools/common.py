"""
where: kintone_integration/tools/common.py
what: kintoneツール群で共有するユーティリティ関数
why: ドメイン正規化やタイムアウト検証などの重複処理を一元化し、保守性を高めるため
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, MutableMapping, Sequence

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

USER_AGENT = "dify-kintone-plugin/0.1.6"
SENSITIVE_KEYS = {"kintone_api_token"}
_MASKED = "***"


def normalize_domain(raw_domain: Any) -> str:
    """kintoneドメイン入力を正規化する。"""

    if not isinstance(raw_domain, str):
        raise ValueError("domain must be a string")
    domain = raw_domain.strip()
    if not domain:
        raise ValueError("domain is empty")
    if domain.startswith(("http://", "https://")):
        domain = domain.split("//", 1)[1]
    return domain.rstrip("/")


def normalize_app_id(raw_value: Any) -> int:
    """アプリIDを整数に正規化する。"""

    text = str(raw_value).strip() if raw_value is not None else ""
    if not text:
        raise ValueError("app id is empty")
    app_id = int(text)
    if app_id <= 0:
        raise ValueError("app id must be positive")
    return app_id


def is_blank(value: Any) -> bool:
    """空もしくは未指定扱いの値かどうかを判定する。"""

    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


def resolve_tool_parameter(tool: Tool, parameters: Mapping[str, Any], name: str) -> Any:
    """ツールパラメータが空ならプロバイダー認証情報をフォールバックとして使用する。"""

    # ブロック上で設定されていればそれを優先する
    value = parameters.get(name)
    if not is_blank(value):
        return value

    runtime = getattr(tool, "runtime", None)
    credentials = getattr(runtime, "credentials", {}) if runtime else {}
    fallback = credentials.get(name)
    if not is_blank(fallback):
        return fallback

    return value


def normalize_api_tokens(raw_value: Any) -> str:
    """kintone APIトークン入力を正規化し、1〜9件のカンマ区切り文字列に揃える。"""

    tokens: list[str]

    if raw_value is None:
        tokens = []
    elif isinstance(raw_value, str):
        tokens = [part.strip() for part in raw_value.split(",") if part.strip()]
    elif isinstance(raw_value, Sequence):
        tokens = []
        for item in raw_value:
            if not isinstance(item, str):
                raise ValueError("kintone APIトークンには文字列のみを指定してください。")
            stripped = item.strip()
            if stripped:
                tokens.append(stripped)
    else:
        raise ValueError("kintone APIトークンには文字列または文字列の配列を指定してください。")

    if not tokens:
        raise ValueError("kintone APIトークンを指定してください。")

    if len(tokens) > 9:
        raise ValueError("kintone APIトークンは最大9件まで指定できます。")

    return ",".join(tokens)


def resolve_timeout(value: Any, default: float) -> float:
    """タイムアウト秒数のパラメータを検証して返す。"""

    if value is None:
        return default
    try:
        timeout = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("timeout must be numeric") from exc
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    return timeout


def build_headers(
    api_token: str,
    *,
    content_type: str | None = "application/json",
    method_override: str | None = None,
    extra: Mapping[str, str] | None = None,
    user_agent: str | None = USER_AGENT,
) -> dict[str, str]:
    """kintone API向けHTTPヘッダーを組み立てる。"""

    headers: dict[str, str] = {"X-Cybozu-API-Token": api_token}
    if user_agent:
        headers["User-Agent"] = user_agent
    if content_type:
        headers["Content-Type"] = content_type
    if method_override:
        headers["X-HTTP-Method-Override"] = method_override
    if extra:
        headers.update(extra)
    return headers


def sanitize_for_logging(
    data: Mapping[str, Any] | None,
    *,
    mask_keys: Iterable[str] = SENSITIVE_KEYS,
    max_string: int = 200,
) -> dict[str, Any]:
    """ログ出力用に値をマスク・省略する。"""

    if not data:
        return {}
    masked = set(mask_keys)
    result: dict[str, Any] = {}
    for key, value in data.items():
        if key in masked:
            result[key] = _MASKED
            continue
        result[key] = _truncate(value, max_string)
    return result


def log_parameters(tool: Tool, parameters: Mapping[str, Any]) -> ToolInvokeMessage:
    """受信パラメータのログメッセージを作成する。"""

    return tool.create_log_message(label="Received parameters", data=sanitize_for_logging(parameters))


def log_response(tool: Tool, label: str, payload: Mapping[str, Any]) -> ToolInvokeMessage:
    """レスポンス情報をログとして出力する。"""

    return tool.create_log_message(label=label, data=sanitize_for_logging(payload))


def ensure_user_agent(headers: MutableMapping[str, str]) -> MutableMapping[str, str]:
    """共通User-Agentを強制的に設定する。"""

    if USER_AGENT and "User-Agent" not in headers:
        headers["User-Agent"] = USER_AGENT
    return headers


def _truncate(value: Any, max_string: int) -> Any:
    """大きい値をログ向けに短縮する。"""

    if isinstance(value, str) and len(value) > max_string:
        return f"{value[:max_string]}...(len={len(value)})"
    if isinstance(value, (list, tuple)) and len(value) > 20:
        preview = list(value[:20])
        preview.append(f"...(total={len(value)})")
        return preview
    if isinstance(value, dict) and len(value) > 20:
        trimmed: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 20:
                trimmed["..."] = f"(total_keys={len(value)})"
                break
            trimmed[key] = _truncate(item, max_string)
        return trimmed
    return value

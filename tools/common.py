"""
where: kintone_integration/tools/common.py
what: kintoneツール群で共有するユーティリティ関数
why: ドメイン正規化やタイムアウト検証などの重複処理を一元化し、保守性を高めるため
"""

from __future__ import annotations

import ast
import json
from typing import Any, Iterable, Mapping, MutableMapping, Sequence

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

USER_AGENT = "r3-yamauchi/dify-kintone-plugin/0.2.0"
SENSITIVE_KEYS = {"kintone_api_token"}
_MASKED = "***"
MAX_LOG_PAYLOAD_CHARS = 4000


def normalize_domain(raw_domain: Any) -> str:
    """kintoneドメイン入力を正規化する。

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


def parse_single_record_data(payload: Any) -> MutableMapping[str, Any]:
    """単一レコードのrecord_dataを辞書に正規化する。

    - dictをそのまま許容
    - JSON文字列をパース（失敗時はast.literal_evalでPythonリテラルも許容）
    - ラッパー形式 {"record_data": {...}} を認識して中身を取り出す
    """

    if isinstance(payload, MutableMapping):
        data = payload
    elif isinstance(payload, str):
        text = payload.strip()
        if not text:
            raise ValueError("record_data が有効なJSON形式ではありません。正しいJSON形式で入力してください。")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            try:
                data = ast.literal_eval(text)
            except (ValueError, SyntaxError):
                raise ValueError("record_data が有効なJSON形式ではありません。正しいJSON形式で入力してください。") from None
    else:
        raise ValueError("record_data が有効なJSON形式ではありません。正しいJSON形式で入力してください。")

    if not isinstance(data, MutableMapping):
        raise ValueError("record_data が有効なJSON形式ではありません。正しいJSON形式で入力してください。")

    # record_data のラッパー形式を許容する
    if "record_data" in data and isinstance(data["record_data"], MutableMapping):
        data = data["record_data"]

    return _to_json_compatible(data)


def validate_record_structure(record_data: Mapping[str, Any]) -> list[str]:
    """単一レコードデータの構造を検証し、問題があればエラー文言を返す。"""

    errors: list[str] = []

    if not isinstance(record_data, Mapping):
        errors.append("record_data はオブジェクトである必要があります")
        return errors

    if not record_data:
        errors.append("record_data にフィールドがありません")
        return errors

    for field_code, field_data in record_data.items():
        if not isinstance(field_code, str):
            errors.append(f"フィールドコードは文字列で指定してください: {field_code!r}")
            continue

        if not isinstance(field_data, Mapping):
            errors.append(f"フィールド '{field_code}' のデータはオブジェクトで指定してください")
            continue

        if "value" not in field_data:
            errors.append(f"フィールド '{field_code}' に 'value' キーがありません")

    return errors


def _to_json_compatible(value: Any) -> Any:
    """kintone API に送れる JSON 互換オブジェクトへ再帰的に変換する。

    - None は空文字列 "" に置換
    - dict / list / tuple を再帰処理
    - それ以外で JSON にできない型はエラー
    """

    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        converted: dict[str, Any] = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise ValueError("record_data のキーは文字列である必要があります。")
            converted[k] = _to_json_compatible(v)
        return converted
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_to_json_compatible(item) for item in value]

    raise ValueError("record_data にJSONへ変換できない値が含まれています。")


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

    sanitized = sanitize_for_logging(payload)
    text = json.dumps(sanitized, ensure_ascii=False)
    if len(text) > MAX_LOG_PAYLOAD_CHARS:
        suffix = f"...(truncated,len={len(text)})"
        head = MAX_LOG_PAYLOAD_CHARS - len(suffix)
        text = text[: max(head, 0)] + suffix
    return tool.create_log_message(label=label, data={"payload": text})


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

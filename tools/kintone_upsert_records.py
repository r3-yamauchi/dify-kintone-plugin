import ast
import json
from collections.abc import Generator
from typing import Any, Dict, List, Tuple

import requests
from requests.exceptions import RequestException, Timeout, HTTPError

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from .common import (
    build_headers,
    is_blank,
    log_parameters,
    log_response,
    normalize_api_tokens,
    normalize_app_id,
    normalize_domain,
    resolve_timeout,
    resolve_tool_parameter,
)


class KintoneUpsertRecordsTool(Tool):
    def _invoke(self, tool_parameters: Dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        # kintone の認証情報およびアプリIDを取得
        raw_domain = resolve_tool_parameter(self, tool_parameters, "kintone_domain")
        if is_blank(raw_domain):
            yield self.create_text_message("kintone ドメインが見つかりません。kintone_domainパラメータを確認してください。")
            return

        try:
            kintone_domain = normalize_domain(raw_domain)
        except ValueError:
            yield self.create_text_message("kintone ドメインが見つかりません。kintone_domainパラメータを確認してください。")
            return

        try:
            kintone_app_id = normalize_app_id(tool_parameters.get("kintone_app_id"))
        except ValueError:
            yield self.create_text_message("kintone アプリIDには正の整数を指定してください。")
            return

        try:
            kintone_api_token = normalize_api_tokens(
                resolve_tool_parameter(self, tool_parameters, "kintone_api_token")
            )
        except ValueError as error:
            yield self.create_text_message(str(error))
            return

        # レコードデータの取得
        records_data = tool_parameters.get("records_data")
        if records_data is None:
            yield self.create_text_message("レコードデータが見つかりません。records_dataパラメータを確認してください。")
            return

        yield log_parameters(
            self,
            {
                "kintone_domain": kintone_domain,
                "kintone_app_id": kintone_app_id,
                "records_data_type": type(records_data).__name__,
            },
        )

        # レコードデータを正規化
        try:
            records_json = self._parse_records_data(records_data)
        except ValueError as error:
            yield self.create_text_message(str(error))
            return

        records_list = records_json.get("records", []) if isinstance(records_json, dict) else []
        update_key_count = sum(1 for item in records_list if isinstance(item, dict) and item.get("updateKey"))

        yield self.create_log_message(
            label="Upsert payload summary",
            data={
                "record_count": len(records_list),
                "update_key_count": update_key_count,
            },
        )

        # レコードデータの基本的な構造を検証
        validation_errors = self._validate_records_structure(records_json)
        if validation_errors:
            error_message = "レコードデータの構造が不正です:\n" + "\n".join(validation_errors)
            yield self.create_text_message(error_message)
            return

        try:
            timeout_seconds = resolve_timeout(tool_parameters.get("request_timeout"), 30.0)
        except ValueError:
            yield self.create_text_message("request_timeout には正の数値を指定してください。")
            return

        # APIリクエスト用のヘッダー設定
        headers = build_headers(kintone_api_token, method_override="PUT")

        # kintone のレコード一括更新/追加 API のエンドポイント
        url = f"{kintone_domain}/k/v1/records.json"

        try:
            # リクエスト用のJSONボディを作成
            request_body = {
                "app": kintone_app_id,
                "records": records_json["records"],
                "upsert": True  # 常にupsertモードで実行
            }

            records_count = len(request_body["records"])
            if records_count > 100:
                yield self.create_text_message(
                    "kintone 一括更新APIで送信できるレコード数は最大100件です。リクエストを分割してください。"
                )
                return

            # APIリクエストの実行
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=request_body,
                    timeout=timeout_seconds
                )
                # HTTPエラーがあれば例外を発生
                response.raise_for_status()
            except Timeout:
                yield self.create_text_message("kintone APIへのリクエストがタイムアウトしました。ネットワーク接続を確認してください。")
                return
            except HTTPError as e:
                # HTTPステータスコードに基づいたエラーメッセージ
                status_code = e.response.status_code if hasattr(e, 'response') else 'unknown'
                error_message = "kintone APIリクエスト中にエラーが発生しました"

                # エラーレスポンスのJSONデータを解析
                error_payload = None
                try:
                    error_payload = e.response.json()
                    if "message" in error_payload:
                        error_message = f"{error_message}: {error_payload['message']}"
                except (json.JSONDecodeError, AttributeError):
                    pass

                structured_error = {
                    "status": status_code,
                    "message": error_message,
                    "details": error_payload,
                }
                if status_code == 401:
                    yield self.create_text_message("kintone APIの認証に失敗しました。APIトークンを確認してください。")
                elif status_code == 403:
                    yield self.create_text_message("kintone APIへのアクセス権限がありません。APIトークンの権限を確認してください。")
                elif status_code == 404:
                    yield self.create_text_message("指定されたkintoneアプリが見つかりません。アプリIDを確認してください。")
                elif isinstance(status_code, int) and status_code >= 500:
                    yield self.create_text_message(f"kintoneサーバーでエラーが発生しました（ステータスコード: {status_code}）。")
                else:
                    yield self.create_text_message(f"{error_message} （ステータスコード: {status_code}）")
                yield self.create_json_message({"error": structured_error})
                yield log_response(self, "kintone upsert error", structured_error)
                return
            except RequestException as e:
                yield self.create_text_message(f"kintone APIへの接続中にエラーが発生しました: {str(e)}")
                return

            # レスポンスのJSONデータを解析
            try:
                data = response.json()
            except json.JSONDecodeError:
                yield self.create_text_message("kintone APIからの応答を解析できませんでした。無効なJSONレスポンスです。")
                return

            yield log_response(self, "kintone upsert response", data)

            # 処理結果の取得
            inserted_count = 0
            updated_count = 0
            operations_counted = False

            records_info = data.get("records")
            if isinstance(records_info, list):
                for item in records_info:
                    if not isinstance(item, dict):
                        continue
                    op = item.get("operation")
                    if not isinstance(op, str):
                        continue
                    normalized = op.strip().upper()
                    if normalized == "INSERT":
                        inserted_count += 1
                        operations_counted = True
                    elif normalized == "UPDATE":
                        updated_count += 1
                        operations_counted = True

            if not operations_counted:
                ids = data.get("ids")
                revisions = data.get("revisions")
                if isinstance(ids, list):
                    inserted_count = len(ids)
                if isinstance(revisions, list):
                    updated_count = len(revisions)
                if inserted_count == 0 and updated_count == 0 and isinstance(records_info, list):
                    updated_count = len(records_info)

            total_processed = inserted_count + updated_count

            result_payload = {
                "add": inserted_count,
                "updated": updated_count,
                "requested": records_count,
                "with_update_key": update_key_count,
            }
            yield self.create_variable_message("upsert_result", result_payload)
            yield self.create_variable_message("response", data)
            yield self.create_json_message(
                {
                    "app_id": kintone_app_id,
                    "processed": result_payload,
                    "raw_response": data,
                }
            )

            if total_processed > 0:
                payload_text = f"アップサート完了: 追加 {inserted_count} 件 / 更新 {updated_count} 件 (リクエスト: {records_count} 件)"
                yield self.create_text_message(payload_text)
            else:
                yield self.create_text_message("レコードの更新/追加処理は完了しましたが、処理されたレコードはありませんでした。")

        except Exception as e:
            # 予期しないエラーの処理
            error_message = f"kintone API 呼び出し中に予期しないエラーが発生しました: {str(e)}"
            yield self.create_text_message(error_message)
            
    def _parse_records_data(self, payload: Any) -> Dict[str, Any]:
        """
        records_dataパラメータを辞書形式へ正規化する。

        - JSON文字列
        - 直接辞書での指定
        - {'records_data': {...}} のラッパー
        - [{'records_data': {...}}, ...] の配列文字列
        を受け付ける。
        """

        # 文字列はJSONとして解釈し、失敗した場合は安全なリテラル評価で再解釈する
        # （LLMがシングルクォート等のPython風表現を生成するケースに対応するため）。
        if isinstance(payload, dict):
            data = payload
        elif isinstance(payload, str):
            text = payload.strip()
            if not text:
                raise ValueError("レコードデータが有効なJSON形式ではありません。正しいJSON形式で入力してください。")
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                try:
                    data = ast.literal_eval(text)
                except (ValueError, SyntaxError):
                    raise ValueError(
                        "レコードデータが有効なJSON形式ではありません。正しいJSON形式で入力してください。"
                    ) from None
        else:
            raise ValueError("レコードデータが有効なJSON形式ではありません。正しいJSON形式で入力してください。")

        if isinstance(data, list):
            target = None
            for item in data:
                if not isinstance(item, dict):
                    continue
                if "records" in item and isinstance(item["records"], list):
                    target = item
                    break
                if "records_data" in item and isinstance(item["records_data"], dict):
                    target = item["records_data"]
                    break
            if target is None:
                raise ValueError("レコードデータが有効なJSON形式ではありません。正しいJSON形式で入力してください。")
            data = target

        if not isinstance(data, dict):
            raise ValueError("レコードデータが有効なJSON形式ではありません。正しいJSON形式で入力してください。")

        # {'records_data': {...}} 形式のラッパーを許容
        if "records" not in data and isinstance(data.get("records_data"), dict):
            data = data["records_data"]

        return data

    def _validate_records_structure(self, records_data: Dict[str, Any]) -> List[str]:
        """
        複数レコードデータの基本的な構造を検証する関数
        
        Args:
            records_data: 検証するレコードデータ
            
        Returns:
            エラーメッセージのリスト（空リストの場合は検証成功）
        """
        errors = []
        
        # レコードデータが辞書型であることを確認
        if not isinstance(records_data, dict):
            errors.append("レコードデータは辞書型である必要があります")
            return errors
            
        # recordsキーが存在することを確認
        if "records" not in records_data:
            errors.append("レコードデータに 'records' キーがありません")
            return errors
            
        # recordsが配列であることを確認
        records = records_data.get("records", [])
        if not isinstance(records, list):
            errors.append("'records' は配列である必要があります")
            return errors
            
        # 各レコードの構造を検証
        for i, record_item in enumerate(records):
            # レコードが辞書型であることを確認
            if not isinstance(record_item, dict):
                errors.append(f"レコード #{i+1} は辞書型である必要があります")
                continue
                
            # recordキーが存在することを確認
            if "record" not in record_item:
                errors.append(f"レコード #{i+1} に 'record' キーがありません")
                continue
                
            # recordが辞書型であることを確認
            record = record_item.get("record")
            if not isinstance(record, dict):
                errors.append(f"レコード #{i+1} の 'record' は辞書型である必要があります")
                continue
                
            # updateKeyが存在する場合の検証
            if "updateKey" in record_item:
                update_key = record_item.get("updateKey")
                
                # updateKeyが辞書型であることを確認
                if not isinstance(update_key, dict):
                    errors.append(f"レコード #{i+1} の 'updateKey' は辞書型である必要があります")
                    continue
                    
                # fieldキーが存在することを確認
                if "field" not in update_key:
                    errors.append(f"レコード #{i+1} の 'updateKey' に 'field' キーがありません")
                    continue
                    
                # valueキーが存在することを確認
                if "value" not in update_key:
                    errors.append(f"レコード #{i+1} の 'updateKey' に 'value' キーがありません")
                    continue
            
            # 各フィールドの構造を検証
            for field_code, field_data in record.items():
                # フィールドコードが文字列であることを確認
                if not isinstance(field_code, str):
                    errors.append(f"レコード #{i+1} のフィールドコードは文字列である必要があります: {field_code}")
                    continue
                    
                # フィールドデータが辞書型であることを確認
                if not isinstance(field_data, dict):
                    errors.append(f"レコード #{i+1} のフィールド '{field_code}' のデータは辞書型である必要があります")
                    continue
                    
                # valueキーが存在することを確認
                if "value" not in field_data:
                    errors.append(f"レコード #{i+1} のフィールド '{field_code}' に 'value' キーがありません")
                
        return errors

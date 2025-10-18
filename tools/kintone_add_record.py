import json
from collections.abc import Generator
from typing import Any, Dict, List

import requests
from requests.exceptions import RequestException, Timeout, HTTPError

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage


class KintoneAddRecordTool(Tool):
    def _invoke(self, tool_parameters: Dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        # kintone の認証情報およびアプリIDを取得
        kintone_domain = tool_parameters.get("kintone_domain")
        if not kintone_domain:
            yield self.create_text_message("kintone ドメインが見つかりません。kintone_domainパラメータを確認してください。")
            return

        kintone_app_id = tool_parameters.get("kintone_app_id")
        if not kintone_app_id:
            yield self.create_text_message("kintone アプリIDが見つかりません。kintone_app_idパラメータを確認してください。")
            return

        kintone_api_token = tool_parameters.get("kintone_api_token")
        if not kintone_api_token:
            yield self.create_text_message("kintone APIトークンが見つかりません。kintone_api_tokenパラメータを確認してください。")
            return

        # レコードデータの取得
        record_data = tool_parameters.get("record_data")
        if not record_data:
            yield self.create_text_message("レコードデータが見つかりません。record_dataパラメータを確認してください。")
            return

        # レコードデータをJSONとして解析
        try:
            record_json = json.loads(record_data)
        except json.JSONDecodeError:
            yield self.create_text_message("レコードデータが有効なJSON形式ではありません。正しいJSON形式で入力してください。")
            return

        # レコードデータの基本的な構造を検証
        validation_errors = self._validate_record_structure(record_json)
        if validation_errors:
            error_message = "レコードデータの構造が不正です:\n" + "\n".join(validation_errors)
            yield self.create_text_message(error_message)
            return

        try:
            timeout_seconds = self._resolve_timeout(tool_parameters.get("request_timeout"), 10.0)
        except ValueError:
            yield self.create_text_message("request_timeout には正の数値を指定してください。")
            return

        # APIリクエスト用のヘッダー設定
        headers = {
            "X-Cybozu-API-Token": kintone_api_token,
            "Content-Type": "application/json"
        }

        # kintone のレコード追加 API のエンドポイント
        url = f"https://{kintone_domain}/k/v1/record.json"

        try:
            # リクエスト用のJSONボディを作成
            request_body = {
                "app": kintone_app_id,
                "record": record_json
            }

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
                if status_code == 401:
                    yield self.create_text_message("kintone APIの認証に失敗しました。APIトークンを確認してください。")
                elif status_code == 403:
                    yield self.create_text_message("kintone APIへのアクセス権限がありません。APIトークンの権限を確認してください。")
                elif status_code == 404:
                    yield self.create_text_message("指定されたkintoneアプリが見つかりません。アプリIDを確認してください。")
                elif status_code >= 500:
                    yield self.create_text_message(f"kintoneサーバーでエラーが発生しました（ステータスコード: {status_code}）。")
                else:
                    yield self.create_text_message(f"kintone APIリクエスト中にHTTPエラーが発生しました: {str(e)}")
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

            # レコードIDの取得
            record_id = data.get("id")
            if not record_id:
                yield self.create_text_message("レコードの追加に成功しましたが、レコードIDを取得できませんでした。")
                return

            # 成功メッセージを返す
            yield self.create_variable_message("record_id", record_id)
            yield self.create_variable_message("response", data)
            success_message = f"レコードが正常に追加されました。レコードID: {record_id}"
            yield self.create_text_message(success_message)

        except Exception as e:
            # 予期しないエラーの処理
            error_message = f"kintone API 呼び出し中に予期しないエラーが発生しました: {str(e)}"
            yield self.create_text_message(error_message)
            
    def _validate_record_structure(self, record_data: Dict[str, Any]) -> List[str]:
        """
        レコードデータの基本的な構造を検証する関数
        
        Args:
            record_data: 検証するレコードデータ
            
        Returns:
            エラーメッセージのリスト（空リストの場合は検証成功）
        """
        errors = []
        
        # レコードデータが辞書型であることを確認
        if not isinstance(record_data, dict):
            errors.append("レコードデータは辞書型である必要があります")
            return errors
            
        # 各フィールドの構造を検証
        for field_code, field_data in record_data.items():
            # フィールドコードが文字列であることを確認
            if not isinstance(field_code, str):
                errors.append(f"フィールドコードは文字列である必要があります: {field_code}")
                continue
                
            # フィールドデータが辞書型であることを確認
            if not isinstance(field_data, dict):
                errors.append(f"フィールド '{field_code}' のデータは辞書型である必要があります")
                continue
                
            # valueキーが存在することを確認
            if "value" not in field_data:
                errors.append(f"フィールド '{field_code}' に 'value' キーがありません")
                
        return errors

    def _resolve_timeout(self, value: Any, default: float) -> float:
        """タイムアウト秒数のパラメータを正の数値に正規化する。"""

        if value is None:
            return default
        try:
            timeout = float(value)
        except (TypeError, ValueError):
            raise ValueError
        if timeout <= 0:
            raise ValueError
        return timeout
        

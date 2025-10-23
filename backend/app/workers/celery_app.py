from __future__ import annotations

from celery import Celery

from ..core.config import get_settings


def create_celery_app() -> Celery:
    """Instantiate the Celery application using the configured broker."""

    settings = get_settings()
    broker_url = settings.celery_broker_url or settings.redis_url
    backend_url = settings.celery_result_backend or settings.redis_url

    app = Celery(
        "disclosure_agent",
        broker=broker_url,
        backend=backend_url,
        include=["app.workers.tasks"],  # タスクモジュールを明示的に含める
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        task_track_started=True,
        # 接続タイムアウト設定（Redisが起動していない場合に素早く失敗する）
        broker_connection_timeout=2,  # ブローカー接続タイムアウト（秒）
        broker_connection_retry=False,  # 接続失敗時にリトライしない
        broker_connection_retry_on_startup=False,  # 起動時の接続リトライを無効化
        result_backend_transport_options={
            'socket_connect_timeout': 2,  # バックエンド接続タイムアウト
            'socket_timeout': 2,
        },
        # タスク有効期限設定（開発環境での古いタスクの自動削除）
        task_reject_on_worker_lost=True,  # ワーカーロスト時にタスクを拒否
        task_acks_late=True,  # タスク完了後にACKを送信（再試行可能に）
        result_expires=3600,  # 結果の有効期限: 1時間（秒）
    )
    return app


celery_app = create_celery_app()

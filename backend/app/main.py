import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.router import api_router
from .core.config import get_settings

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""

    config = get_settings()
    
    # デバッグ: 設定値をログ出力
    logger.info("=" * 60)
    logger.info("APPLICATION CONFIGURATION")
    logger.info("=" * 60)
    logger.info(f"Environment: {config.environment}")
    logger.info(f"OpenAI API Key configured: {bool(config.openai_api_key)}")
    logger.info(
        "OpenAI Provider: %s",
        "azure" if config.use_azure_openai else "openai",
    )
    if config.use_azure_openai:
        logger.info(f"Azure OpenAI endpoint configured: {bool(config.azure_openai_endpoint)}")
        logger.info(f"Azure OpenAI API version: {config.azure_openai_api_version}")
    logger.info(f"OpenAI Model: {config.openai_model}")
    logger.info(f"LLM Classification enabled: {config.document_classification_use_llm}")
    logger.info(f"Max prompt chars: {config.document_classification_max_prompt_chars}")
    logger.info("=" * 60)
    
    app = FastAPI(
        title="Disclosure Comparison API",
        version="0.1.0",
        openapi_url=f"{config.api_prefix}/openapi.json",
        docs_url=f"{config.api_prefix}/docs",
        redoc_url=f"{config.api_prefix}/redoc",
    )
    
    # CORS設定: フロントエンドからのリクエストを許可
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000", 
            "http://localhost:3001", 
            "http://localhost:3002",
            "http://localhost:9000"
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.include_router(api_router, prefix=config.api_prefix)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"status": "ready"}

    if config.environment == "development":

        @app.get("/debug/config", include_in_schema=False)
        async def debug_config() -> dict:
            """デバッグ用: 設定値を確認"""
            return {
                "environment": config.environment,
                "openai_api_key_configured": bool(config.openai_api_key),
                "openai_model": config.openai_model,
                "document_classification_use_llm": config.document_classification_use_llm,
                "document_classification_max_prompt_chars": config.document_classification_max_prompt_chars,
                "openai_provider": "azure" if config.use_azure_openai else "openai",
                "azure_openai_endpoint_configured": bool(config.azure_openai_endpoint),
                "azure_openai_api_version": config.azure_openai_api_version,
            }

    return app


app = create_app()

import hmac
import logging
import os
import threading
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

from modules.config.env import load_env


FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
logger = logging.getLogger(__name__)


class DistancePayload(BaseModel):
    distance: Optional[float] = None


class BrokerConnectPayload(BaseModel):
    mode: str
    passphrase: Optional[str] = None


class WebAPI(threading.Thread):
    def __init__(
        self,
        runtime,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ):
        load_env()
        super().__init__()
        self.host = host or os.environ.get("FT_WEB_HOST", "127.0.0.1")
        self.port = port or int(os.environ.get("FT_WEB_PORT", "8000"))
        self.app = create_app(runtime)
        self.server: Optional[uvicorn.Server] = None

    def run(self) -> None:
        config = uvicorn.Config(self.app, host=self.host, port=self.port, log_level="info")
        self.server = uvicorn.Server(config)
        self.server.run()

    def stop(self) -> None:
        if self.server is not None:
            self.server.should_exit = True


def create_app(runtime) -> FastAPI:
    load_env()
    app = FastAPI(title="FT Trading API")
    auth_token = os.environ.get("FT_WEB_AUTH_TOKEN", "")

    def require_auth(authorization: Optional[str] = Header(None)) -> None:
        if not auth_token:
            return

        expected = f"Bearer {auth_token}"
        if authorization is None or not hmac.compare_digest(authorization, expected):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )

    if (FRONTEND_DIR / "static").exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "static"), name="assets")

    @app.get("/")
    def index():
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/api/auth/status")
    def auth_status():
        return {"required": bool(auth_token)}

    @app.get("/api/health", dependencies=[Depends(require_auth)])
    def health():
        return runtime.get_health()

    @app.get("/api/prices", dependencies=[Depends(require_auth)])
    def prices():
        return runtime.get_prices()

    @app.get("/api/positions", dependencies=[Depends(require_auth)])
    def positions():
        return runtime.get_positions()

    @app.get("/api/broker", dependencies=[Depends(require_auth)])
    def broker_status():
        return runtime.get_broker_status()

    @app.get("/api/runtimes", dependencies=[Depends(require_auth)])
    def runtime_status():
        return runtime.get_runtime_status()

    @app.post("/api/broker/connect", dependencies=[Depends(require_auth)])
    def connect_broker(payload: BrokerConnectPayload, request: Request):
        try:
            result = runtime.connect_broker(payload.mode, payload.passphrase)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        logger.info(f"UI broker connect from {request.client.host if request.client else 'unknown'}: {payload.mode}")
        return result

    @app.post("/api/trading/connect", dependencies=[Depends(require_auth)])
    def start_trading(payload: BrokerConnectPayload, request: Request):
        try:
            result = runtime.start_trading(payload.mode, payload.passphrase)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        logger.info(f"UI trading start from {request.client.host if request.client else 'unknown'}: {payload.mode}")
        return result

    @app.post("/api/trading/stop", dependencies=[Depends(require_auth)])
    def stop_trading(request: Request):
        result = runtime.stop_trading()
        logger.info(f"UI trading stop from {request.client.host if request.client else 'unknown'}")
        return result

    @app.post("/api/recording/connect", dependencies=[Depends(require_auth)])
    def start_recording(payload: BrokerConnectPayload, request: Request):
        try:
            result = runtime.start_recording(payload.mode, payload.passphrase)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        logger.info(f"UI recording start from {request.client.host if request.client else 'unknown'}: {payload.mode}")
        return result

    @app.post("/api/recording/stop", dependencies=[Depends(require_auth)])
    def stop_recording(request: Request):
        result = runtime.stop_recording()
        logger.info(f"UI recording stop from {request.client.host if request.client else 'unknown'}")
        return result

    @app.post("/api/positions/{position_id}/close", dependencies=[Depends(require_auth)])
    def close_position(position_id: str, request: Request):
        try:
            runtime.close_position(position_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        logger.info(f"UI close action from {request.client.host if request.client else 'unknown'}: {position_id}")
        return {"ok": True}

    @app.post("/api/positions/{position_id}/limit", dependencies=[Depends(require_auth)])
    def update_limit(position_id: str, payload: DistancePayload, request: Request):
        try:
            result = runtime.update_limit(position_id, payload.distance)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        logger.info(
            f"UI limit action from {request.client.host if request.client else 'unknown'}: "
            f"{position_id} -> {payload.distance}"
        )
        return result

    @app.post("/api/positions/{position_id}/stop-profit", dependencies=[Depends(require_auth)])
    def update_stop_profit(position_id: str, payload: DistancePayload, request: Request):
        try:
            result = runtime.update_stop_profit(position_id, payload.distance)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        logger.info(
            f"UI stop profit action from {request.client.host if request.client else 'unknown'}: "
            f"{position_id} -> {payload.distance}"
        )
        return result

    return app

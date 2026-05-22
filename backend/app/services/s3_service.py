import asyncio
import functools
from pathlib import Path
from typing import Any, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError

from app.core.config import settings
from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger

logger = get_logger(__name__)

S3_CONFIG = Config(
    region_name=settings.AWS_REGION,
    retries={
        "max_attempts": 3,
        "mode": "adaptive",
    },
    connect_timeout=10,
    read_timeout=60,
)

# Local storage root used when S3 is not available (development only)
_LOCAL_STORAGE_ROOT = Path("/tmp/gstsense_local_storage")


def _is_dev_mode() -> bool:
    return settings.ENVIRONMENT == "development"


def get_s3_client() -> Any:
    """Create boto3 S3 client configured for ap-south-1 Mumbai."""
    return boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        config=S3_CONFIG,
    )


class S3Service:
    def __init__(self) -> None:
        if not _is_dev_mode():
            self.client = get_s3_client()
        else:
            self.client = None
        self.bucket = settings.AWS_S3_BUCKET

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    async def _run(self, func, *args, **kwargs):  # type: ignore[no-untyped-def]
        """Offload synchronous boto3 call to the thread-pool executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))

    def _local_path(self, s3_key: str) -> Path:
        path = _LOCAL_STORAGE_ROOT / s3_key
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    async def upload_file(
        self,
        file_bytes: bytes,
        s3_key: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[dict] = None,
    ) -> str:
        """Upload raw bytes to S3 (or local disk in dev) and return the s3_key."""
        logger.info("s3_upload_started", s3_key=s3_key, file_size_bytes=len(file_bytes))

        if _is_dev_mode():
            self._local_path(s3_key).write_bytes(file_bytes)
            logger.info("local_storage_upload_completed", s3_key=s3_key)
            return s3_key

        extra_args: dict = {"ContentType": content_type}
        if metadata:
            extra_args["Metadata"] = {k: str(v) for k, v in metadata.items()}

        try:
            await self._run(
                self.client.put_object,
                Bucket=self.bucket,
                Key=s3_key,
                Body=file_bytes,
                **extra_args,
            )
        except (ClientError, NoCredentialsError) as exc:
            logger.error("s3_upload_failed", s3_key=s3_key, error=str(exc))
            raise ExternalServiceError.storage_service_error()

        logger.info("s3_upload_completed", s3_key=s3_key, file_size_bytes=len(file_bytes))
        return s3_key

    async def download_file(self, s3_key: str) -> bytes:
        """Download an S3 object and return its raw bytes."""
        logger.info("s3_download_started", s3_key=s3_key)

        if _is_dev_mode():
            local = self._local_path(s3_key)
            if not local.exists():
                raise ExternalServiceError.storage_service_error()
            data = local.read_bytes()
            logger.info("local_storage_download_completed", s3_key=s3_key)
            return data

        try:
            response = await self._run(
                self.client.get_object,
                Bucket=self.bucket,
                Key=s3_key,
            )
            data = response["Body"].read()
        except ClientError as exc:
            error_code = exc.response["Error"]["Code"]
            logger.error("s3_download_failed", s3_key=s3_key, error_code=error_code)
            raise ExternalServiceError.storage_service_error()

        logger.info("s3_download_completed", s3_key=s3_key, file_size_bytes=len(data))
        return data

    async def generate_presigned_url(
        self,
        s3_key: str,
        expiry_seconds: int = 900,
        filename: Optional[str] = None,
    ) -> str:
        """Return a presigned GET URL (or local file:// path in dev)."""
        if _is_dev_mode():
            local = self._local_path(s3_key)
            return f"file://{local}"

        params: dict = {"Bucket": self.bucket, "Key": s3_key}
        if filename:
            params["ResponseContentDisposition"] = (
                f'attachment; filename="{filename}"'
            )
        try:
            url: str = await self._run(
                self.client.generate_presigned_url,
                "get_object",
                Params=params,
                ExpiresIn=expiry_seconds,
            )
        except (ClientError, NoCredentialsError) as exc:
            logger.error("s3_presign_failed", s3_key=s3_key, error=str(exc))
            raise ExternalServiceError.storage_service_error()

        return url

    async def delete_file(self, s3_key: str) -> bool:
        """Delete an S3 object. Returns True always (S3 delete is idempotent)."""
        logger.info("s3_delete_started", s3_key=s3_key)

        if _is_dev_mode():
            local = self._local_path(s3_key)
            if local.exists():
                local.unlink()
            return True

        try:
            await self._run(
                self.client.delete_object,
                Bucket=self.bucket,
                Key=s3_key,
            )
            logger.info("s3_delete_completed", s3_key=s3_key)
            return True
        except (ClientError, NoCredentialsError) as exc:
            logger.error("s3_delete_failed", s3_key=s3_key, error=str(exc))
            return False

    async def file_exists(self, s3_key: str) -> bool:
        """Return True if the key exists."""
        if _is_dev_mode():
            return self._local_path(s3_key).exists()

        try:
            await self._run(
                self.client.head_object,
                Bucket=self.bucket,
                Key=s3_key,
            )
            return True
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
                return False
            logger.error("s3_head_failed", s3_key=s3_key, error=str(exc))
            return False

    # ------------------------------------------------------------------
    # Key builders
    # ------------------------------------------------------------------

    def build_scan_gstr1_key(self, org_id: str, scan_id: str) -> str:
        return f"orgs/{org_id}/scans/{scan_id}/gstr1.xlsx"

    def build_scan_gstr3b_key(self, org_id: str, scan_id: str) -> str:
        return f"orgs/{org_id}/scans/{scan_id}/gstr3b.xlsx"

    def build_scan_pdf_key(self, org_id: str, scan_id: str) -> str:
        return f"orgs/{org_id}/scans/{scan_id}/report.pdf"

    def build_notice_pdf_key(self, org_id: str, notice_id: str) -> str:
        return f"orgs/{org_id}/notices/{notice_id}/notice.pdf"


s3_service = S3Service()

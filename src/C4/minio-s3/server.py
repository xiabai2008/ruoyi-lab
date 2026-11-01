"""MinIO / S3 未授权访问靶场。

为什么用 Python 复刻而不是跑真 MinIO
====================================
MinIO 2025 年把**社区版二进制彻底下架**：所有 `dl.min.io/server/minio/release/*`
路径都返回 410 Gone，唯一在发的是需要商业 license 的 AIStor 版 ——
实测该版本无 license 时连 `ListBuckets` 都拒绝
（`AccessDenied: No license is installed`），做不了「匿名可读」这个漏洞场景。

所以这里按**真实 S3 协议**复刻响应，而不是靠 marker 桩：

- 响应头照抄真 MinIO：`Server: MinIO`、`X-Amz-Request-Id`、`X-Amz-Id-2`、
  `Accept-Ranges: bytes`、`X-Content-Type-Options: nosniff`
- 匿名 ListBuckets 返回真实 XML 结构 `<ListAllMyBucketsResult>`
  （namespace 与 Element 层级都与 AWS S3 / MinIO 一致）
- 拒绝时返回真实 `<Error><Code>AccessDenied</Code>...` 结构
- `/minio/health/live` 是 MinIO 真实的健康检查端点

扫描器必须真的按 S3 语义去读 XML 才可能命中，靠猜字符串过不了。

与插件判定路径的关系（关键）
============================
`minio_unauth` 插件探两个路径：
  1. `/minio/health/live`  —— 服务存在性
  2. `/minio/`             —— 期待 bucket 列表

但真实 MinIO 的**匿名桶列举走 S3 根路径 `/`**（`GET /` → ListBuckets），
`/minio/` 是**控制台登录页**的入口，永远不含 bucket 列表。

本靶场如实复刻这个差异：
  - `/`             → 200 + `<ListAllMyBucketsResult>`（匿名可列举，漏洞态）
  - `/minio/`       → 200 + 控制台 HTML（登录页）
  - `/minio/health/live` → 200（空体）

要用 `--insecure-mode` 参数可切换到「安全配置」形态（根路径也返回 403）。

用法：
    python server.py                    # 漏洞态：匿名可列举（默认）
    python server.py --safe             # 安全态：匿名被拒（403）
    python server.py --port 19000
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# 靶场里的桶（模拟一家医院内网的影像/报表存储）
BUCKETS = [
    ("hospital-reports", "2021-04-15T08:12:33.000Z"),
    ("patient-uploads", "2021-06-02T11:35:10.000Z"),
    ("backup-2021", "2021-12-28T22:03:47.000Z"),
]

LIST_BUCKETS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<ListAllMyBucketsResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><Owner><ID>minio</ID><DisplayName>minio</DisplayName></Owner><Buckets>{buckets}</Buckets></ListAllMyBucketsResult>"""

BUCKET_ENTRY = "<Bucket><Name>{name}</Name><CreationDate>{date}</CreationDate></Bucket>"

ERROR_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Error><Code>{code}</Code><Message>{message}</Message><Resource>{resource}</Resource><RequestId>{req}</RequestId><HostId>{host}</HostId></Error>"""

# MinIO 控制台的登录页（/minio/ 的真实内容 —— 是 SPA，没有 bucket 列表）
CONSOLE_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8">
<title>MinIO Console</title></head>
<body><div id="root"></div>
<script>window.__MINIO_CONSOLE__=true;</script>
</body></html>"""


def _req_id() -> str:
    """16 字节十六进制，与 MinIO 的 RequestId 形态一致。"""
    import os

    return os.urandom(8).hex().upper()


def _host_id() -> str:
    return hashlib.sha256(b"minio-lab-host").hexdigest()


class S3Handler(BaseHTTPRequestHandler):
    server_version = "MinIO"
    sys_version = ""

    # 由 main() 设置：True = 安全态（匿名被拒）
    safe_mode = False

    def log_message(self, fmt: str, *args) -> None:  # noqa: D102 - 静默访问日志
        pass

    # ── 响应工具 ──

    def _send(self, status: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(status)
        # 照抄真实 MinIO 的响应头
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        # Server 头由 BaseHTTPRequestHandler 用 server_version 自动加（"MinIO"），
        # 这里不能重复写 —— 否则响应里出现 "Server: MinIO , MinIO"，
        # 会和真实 MinIO 的单一 Server 头不一致，可能干扰按头匹配的插件。
        self.send_header("X-Amz-Request-Id", _req_id())
        self.send_header("X-Amz-Id-2", _host_id())
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Xss-Protection", "1; mode=block")
        self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        # HEAD 请求不写 body（否则连接被提前关闭，客户端报 000）
        if not getattr(self, "_head_only", False):
            self.wfile.write(body)

    def _error(self, status: int, code: str, message: str, resource: str) -> None:
        body = ERROR_XML.format(
            code=code, message=message, resource=resource, req=_req_id(), host=_host_id()
        ).encode("utf-8")
        self._send(status, body, "application/xml")

    # ── 路由 ──

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler 接口
        path = self.path.split("?")[0]

        # 1. MinIO 健康检查（真实端点，永远是 200 空体，与会话无关）
        if path == "/minio/health/live":
            self._send(200, b"", "text/plain")
            return

        # 2. 控制台入口：真实 MinIO 返回 Console SPA（登录页），不含 bucket 列表
        if path in ("/minio/", "/minio"):
            self._send(200, CONSOLE_HTML.encode("utf-8"), "text/html; charset=utf-8")
            return

        # 3. S3 根路径：ListBuckets —— 这是匿名列举的真实入口
        if path == "/":
            if self.safe_mode:
                # 安全态：MinIO 默认配置就是匿名被拒
                self._error(403, "AccessDenied", "Access Denied.", "/")
                return
            entries = "".join(BUCKET_ENTRY.format(name=n, date=d) for n, d in BUCKETS)
            body = LIST_BUCKETS_XML.format(buckets=entries).encode("utf-8")
            self._send(200, body, "application/xml")
            return

        # 4. 桶级列举（匿名可读时返回真实对象列表 XML）
        seg = path.strip("/").split("/")
        if seg and seg[0] in {n for n, _ in BUCKETS}:
            if self.safe_mode:
                self._error(403, "AccessDenied", "Access Denied.", path)
                return
            bucket = seg[0]
            if len(seg) == 1:
                body = (
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    '<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
                    f"<Name>{bucket}</Name><Prefix></Prefix><MaxKeys>1000</MaxKeys>"
                    "<IsTruncated>false</IsTruncated>"
                    "<Contents><Key>sample.txt</Key><Size>22</Size>"
                    "<LastModified>2021-04-15T08:12:33.000Z</LastModified>"
                    '<ETag>"d41d8cd98f00b204e9800998ecf8427e"</ETag>'
                    "<StorageClass>STANDARD</StorageClass></Contents>"
                    "</ListBucketResult>"
                ).encode("utf-8")
                self._send(200, body, "application/xml")
                return
            # 对象不存在
            self._error(404, "NoSuchKey", "The specified key does not exist.", path)
            return

        self._error(404, "NoSuchBucket", "The specified bucket does not exist.", path)

    def do_HEAD(self) -> None:  # noqa: N802
        """HEAD 只回头不写体。

        直接复用 do_GET 会往 HEAD 请求写 body —— 客户端已按协议不读 body，
        连接会被提前关闭，表现为 curl/requests 拿到 000（连接重置）。
        实测踩过：`curl -I http://127.0.0.1:19000/` 触发异常。
        """
        self._head_only = True
        try:
            self.do_GET()
        finally:
            self._head_only = False


def main() -> int:
    ap = argparse.ArgumentParser(description="MinIO/S3 未授权访问靶场")
    ap.add_argument("--port", type=int, default=19000)
    ap.add_argument(
        "--safe",
        action="store_true",
        help="安全态：匿名 ListBuckets 返回 403（默认是漏洞态：匿名可列举）",
    )
    args = ap.parse_args()

    S3Handler.safe_mode = args.safe
    mode = "安全态（匿名被拒 403）" if args.safe else "漏洞态（匿名可列举）"

    srv = HTTPServer(("0.0.0.0", args.port), S3Handler)
    print(f"[OK] MinIO/S3 靶场已启动 :{args.port} —— {mode}")
    print(f"     S3 ListBuckets : http://127.0.0.1:{args.port}/")
    print(f"     Console        : http://127.0.0.1:{args.port}/minio/")
    print(f"     Health         : http://127.0.0.1:{args.port}/minio/health/live")
    try:
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        while True:
            import time

            time.sleep(3600)
    except KeyboardInterrupt:
        print("\n[OK] 已停止")
        srv.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())

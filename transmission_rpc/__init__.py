import random
from typing import Type

import requests
from requests.exceptions import RequestException
from tenacity import RetryCallState, retry, retry_base, stop_after_attempt
from tenacity.stop import stop_base

from transmission_rpc.exceptions import TransmissionError
from transmission_rpc.schemas import RpcResponse


class retry_status_code(retry_base):
    def __init__(self, code: int):
        self.code = code

    def __call__(self, retry_state: RetryCallState) -> bool:
        if retry_state.outcome.failed:
            exc = retry_state.outcome.exception()
            return isinstance(exc, RequestException) and exc.response.status_code == self.code
        else:
            return False


class stop_after_exception(stop_base):
    def __init__(self, exc_cls: Type[BaseException]):
        self.exc_cls = exc_cls

    def __call__(self, retry_state: RetryCallState) -> bool:
        return isinstance(retry_state.outcome.exception(), self.exc_cls)


class TransmissionRpcClient(requests.Session):
    def __init__(self, rpc_url: str, auth=None):
        super().__init__()
        self.auth = auth
        self.rpc_url = rpc_url

    @retry(
        retry=retry_status_code(409),
        stop=stop_after_exception(TransmissionError) | stop_after_attempt(3),
    )
    def rpc_request(self, method: str, arguments: dict | None = None) -> RpcResponse:
        if arguments is None:
            arguments = {}

        tag = random.getrandbits(32)

        body = {"method": method, "arguments": arguments, "tag": tag}

        resp = self.post(self.rpc_url, json=body)

        if resp.status_code == 409:
            self.headers["X-Transmission-Session-Id"] = resp.headers["X-Transmission-Session-Id"]

        resp.raise_for_status()

        data = RpcResponse.parse_raw(resp.content, encoding=resp.encoding)

        if data.result != "success":
            raise TransmissionError(data.result)

        if data.tag != tag:
            raise TransmissionError("Tag mismatch")

        return data

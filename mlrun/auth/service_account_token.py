# Copyright 2026 Iguazio
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import mlrun.auth.utils
import mlrun.common.schemas
import mlrun.utils.singleton
from mlrun.config import config as mlconf

_SERVICE_ACCOUNT_AUTHENTICATOR_KIND = "sa"
_TOKEN_EXPIRATION_BUFFER_MULTIPLIER_BASE = 1


class Client(
    metaclass=mlrun.utils.singleton.AbstractSingleton,
):
    """
    A client for Iguazio service account authentication.

    This client reads the service account token from a specified file path (mounted by kubernetes)
    and provides methods to add authentication headers to HTTP requests.
    """

    _SERVICE_ACCOUNT_AUTHENTICATION_HEADER = {
        mlrun.common.schemas.HeaderNames.igz_authenticator_kind: (
            _SERVICE_ACCOUNT_AUTHENTICATOR_KIND
        ),
    }

    def __init__(self) -> None:
        """
        Initialize the service account token client.
        """
        self._token_cache = None
        self._token_path = mlconf.httpdb.authentication.service_account.token_path
        self._token_expiration_seconds = (
            mlconf.httpdb.authentication.service_account.token_expiration_seconds
        )
        self._token_expiration_buffer_seconds = self._token_expiration_seconds * (
            _TOKEN_EXPIRATION_BUFFER_MULTIPLIER_BASE
            - mlconf.auth_with_oauth_token.refresh_threshold
        )

    def escalate_request_headers(self, headers: dict[str, str]) -> dict[str, str]:
        """
        Add service account authentication headers to the given headers.

        :param headers: Original request headers.
        :return: Headers with added service account authentication.
        """
        auth_headers = self.auth_headers
        combined_headers = headers.copy()
        combined_headers.update(auth_headers)
        return combined_headers

    @property
    def auth_headers(self) -> dict[str, str]:
        """
        Get the service account authentication headers.
        """
        headers = self._SERVICE_ACCOUNT_AUTHENTICATION_HEADER.copy()
        headers[mlrun.common.schemas.HeaderNames.authorization] = (
            mlrun.common.schemas.AuthorizationHeaderPrefixes.bearer + self.token
        )
        return headers

    @property
    def token(self) -> str:
        """
        Get the service account token, using a cached value if it's still valid.
        """
        if self._token_cache and not mlrun.auth.utils.is_token_expired(
            self._token_cache, self._token_expiration_buffer_seconds
        ):
            return self._token_cache

        with open(self._token_path) as token_file:
            self._token_cache = token_file.read().strip()

        return self._token_cache

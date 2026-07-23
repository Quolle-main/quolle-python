"""Quolle Python SDK — the official client for the Quolle email API.

Basic usage::

    from quolle import Quolle

    quolle = Quolle(api_key="qle_...")
    result = quolle.emails.send(
        from_="hello@mail.yourdomain.com",
        to="customer@example.com",
        subject="Welcome!",
        html="<h1>Thanks for signing up</h1>",
    )
    print(result["id"])
"""

from .client import Quolle
from .errors import QuolleError

__all__ = ["Quolle", "QuolleError"]
__version__ = "1.0.0"

# `app/core/rate_limit.py` — API rate limiting

**Source:** `app/core/rate_limit.py`

This module defines the single rate limiter shared by the whole API.

## Behavior

- The limiter comes from **slowapi**.
- The client's IP address, via `get_remote_address`, is the rate-limit identity.
  The API has no users or authentication, so there is no per-account identity.
- The default limit is `settings.DEFAULT_RATE_LIMIT` (`60/minute` by default) and
  applies to every endpoint.
- Individual endpoints also declare `@limiter.limit(settings.DEFAULT_RATE_LIMIT)`
  in the router modules, which makes the limit explicit next to the route.

`app/main.py` stores the limiter in `app.state`, adds `SlowAPIMiddleware`, and
registers the handler that turns `RateLimitExceeded` into the standard response.

Change the limit through the `DEFAULT_RATE_LIMIT` environment variable rather
than editing this module.

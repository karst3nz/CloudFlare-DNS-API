# CloudflareAsyncAPI

**CloudflareAsyncAPI** is an asynchronous Python client for interacting with Cloudflare's REST API v4 using either a Bearer token or a Global API Key.

This client supports creating zones, registering domains, adding DNS records, and checking zone status.
https://dash.cloudflare.com/
---

## 🚀 Features

- Authenticate using API token or global key
- Create zones and register domains
- Add DNS records (A, AAAA, CNAME, etc.)
- Wait for zone activation
- Structured exception handling
- Full support for asynchronous usage

---


## 🔐 Authentication

You can authenticate in two ways:

### 1. Using an API Token

```python
cf = CloudflareAsyncAPI.from_api_token("your-api-token")
```

### 2. Using a Global API Key and Email

```python
cf = CloudflareAsyncAPI.from_global_key("your-email@example.com", "your-global-api-key")
```

---

## 🧰 Usage

Here is a complete example of how to use the client or check example.py:

```python
import asyncio
from cloudflare_async_api import CloudflareAsyncAPI  # Adjust the import path as needed

async def main():
    cf = CloudflareAsyncAPI.from_global_key("your-email@example.com", "your-global-api-key")
    async with cf:
        # Register a new domain
        zone_id, ns1, ns2 = await cf.register_domain("example.com", fail_if_exists=False)

        # Print zone info
        print("Zone ID:", zone_id)
        print("NS1:", ns1)
        print("NS2:", ns2)

        # Add an A record
        await cf.add_dns_record(
            zone_id=zone_id,
            record_type="A",
            name="www",
            content="192.0.2.1",
            proxied=True  # Enable Cloudflare proxy
        )

        # Optionally wait until zone is active
        await cf.wait_until_active(zone_id)

asyncio.run(main())
```

---

## ⚠️ Exceptions

The client raises custom exceptions for known Cloudflare error codes:

- `ZoneAlreadyExists`
- `InvalidRequestHeaders`
- `IdenticalRecordExists`
- `DNSRecordInvalid`
- `UserCredsInvalid`
- `ExceededZonesLimit`

---

## 📄 License

This project is provided as-is under the MIT License.
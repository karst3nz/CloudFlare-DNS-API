from cloudflare import CloudflareAsyncAPI
import asyncio
from log import create_logger, logging

async def example():
    cf = CloudflareAsyncAPI.from_api_token( # Requires a Full DNS and USER permissions. Better use ".from_global_key()" is more simple
        token="YOUR-CF-TOKEN"
    )
    #------------- OR -------------#
    cf = CloudflareAsyncAPI.from_global_key(
        email="YOUR-CF-EMAIL",
        api_key="YOUR-CF-GLOBAL-KEY"
    )
    logger = create_logger("example", prefix="CF-Example", level=logging.DEBUG)
    try:
        async with cf:
            # Register the domain (creates a new zone)
            zone_id, ns1, ns2 = await cf.register_domain("example.com")
            logger.info("Zone ID: {}".format(zone_id))
            logger.info("NS1: {}".format(ns1))
            logger.info("NS2: {}".format(ns2))
            # Add an A record
            await cf.add_dns_record(
                zone_id=zone_id,
                record_type="A",
                name="www",
                content="192.0.2.2",
                proxied=True  # Enable Cloudflare proxy
            )

            # Optionally wait until the zone is active
            await cf.wait_until_active(zone_id)    
    except cf.UserCredsInvalid as e:
        logger.critical(e)
        
if __name__ == "__main__":
    asyncio.run(example())
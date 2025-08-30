def connect_to_mongo(db_uri):
    import dns.resolver

    dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
    dns.resolver.default_resolver.nameservers = ["8.8.8.8"]

    from pymongo.mongo_client import MongoClient
    from pymongo.server_api import ServerApi

    uri = db_uri

    client = MongoClient(uri, server_api=ServerApi("1"))
    return client

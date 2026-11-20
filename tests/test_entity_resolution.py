from src.entity_resolution import EntityResolver, EntityNormalizer, SimilarityMetrics


def test_legal_suffix_stripping():
    assert EntityNormalizer.clean("OpenAI, Inc.") == "openai"
    assert EntityNormalizer.clean("Anthropic PBC") == "anthropic"
    assert EntityNormalizer.clean("Scale AI, LLC") == "scale"
    assert EntityNormalizer.clean("Mistral AI SAS") == "mistral"
    assert EntityNormalizer.clean("Cohere Technologies Inc.") == "cohere"


def test_exact_and_alias_resolution():
    resolver = EntityResolver()

    canonical, conf, method = resolver.resolve_startup("OpenAI, Inc.")
    assert canonical == "OpenAI"
    assert method == "EXACT_SEED"
    assert conf == 1.00

    canonical, conf, method = resolver.resolve_startup("Open AI")
    assert canonical == "OpenAI"
    assert conf == 1.00

    canonical, conf, method = resolver.resolve_startup("Anthropic PBC")
    assert canonical == "Anthropic"
    assert conf == 1.00


def test_domain_based_resolution():
    resolver = EntityResolver()
    canonical, conf, method = resolver.resolve_startup("Random Name", source_url="https://openai.com/research")
    assert canonical == "OpenAI"
    assert method == "DOMAIN_MATCH"
    assert conf == 0.99


def test_fuzzy_resolution():
    resolver = EntityResolver()
    # Slight typo
    canonical, conf, method = resolver.resolve_startup("PerplexityAI Inc")
    assert canonical == "Perplexity AI"


def test_product_resolution():
    resolver = EntityResolver()
    prod_can, startup_can, conf, method = resolver.resolve_product("ChatGPT Pro", startup_name="OpenAI Global")
    assert startup_can == "OpenAI"
    assert prod_can == "Chatgpt Pro"

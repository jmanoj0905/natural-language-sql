import pytest
import numpy as np
from app.core.ai.schema_embedder import SchemaEmbedder, get_schema_embedder

pytestmark = pytest.mark.slow


def test_embed_shape_and_norm():
    emb = SchemaEmbedder()
    v = emb.embed(["x"])
    assert v.shape == (1, 384)
    assert abs(float(np.linalg.norm(v[0])) - 1.0) < 1e-3


def test_synonym_similarity():
    emb = SchemaEmbedder()
    a, b = emb.embed(["customer", "client"])
    cos = float(a @ b)
    assert cos > 0.5


def test_unrelated_similarity_lower():
    emb = SchemaEmbedder()
    a, b = emb.embed(["customer", "potato salad recipe instructions"])
    cos = float(a @ b)
    assert cos < 0.5


def test_singleton():
    a = get_schema_embedder()
    b = get_schema_embedder()
    assert a is b

import sys
sys.path.insert(0, '.')
from app.memory import init_hindsight

client = init_hindsight()
print("Client connected to:", client._base_url)

# Try to create bank first (bank must exist before retain)
try:
    print("Creating bank 'Pranavv28'...")
    result = client.create_bank(bank_id="Pranavv28")
    print("Bank created:", result)
except Exception as e:
    print("create_bank error (may already exist):", e)

# Try a simple retain
print("\nTesting retain...")
try:
    result = client.retain(
        bank_id="Pranavv28",
        content="Test memory: developer Pranavv28 writes Python code.",
        context="test",
        tags=["python", "code-review"],
        metadata={"review_number": "0", "test": "true"}
    )
    print("Retain success:", result)
except Exception as e:
    print("Retain error:", str(e)[:500])

# Try a recall
print("\nTesting recall...")
try:
    result = client.recall(
        bank_id="Pranavv28",
        query="What does this developer write?",
        budget="low"
    )
    print("Recall success:", len(result.results), "results")
except Exception as e:
    print("Recall error:", str(e)[:500])

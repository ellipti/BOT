"""
Minimal test to check MT5Broker class definition
"""

# Test if we can even execute the file
print("Attempting to load MT5 broker file...")

try:
    # First test if we can exec the file content
    with open("adapters/mt5_broker.py") as f:
        content = f.read()
        print(f"File content length: {len(content)} characters")

    # Try to compile it
    compile(content, "adapters/mt5_broker.py", "exec")
    print("✅ File compiles successfully")

    # Try to exec it in a namespace
    namespace = {}
    exec(content, namespace)

    print("✅ File executes successfully")
    print(f"Namespace keys: {list(namespace.keys())}")

    # Look for the class
    if "MT5Broker" in namespace:
        print("✅ MT5Broker class found in namespace")
        print(f"Class type: {type(namespace['MT5Broker'])}")
    else:
        print("❌ MT5Broker class NOT found in namespace")
        # Print all available classes
        classes = [k for k, v in namespace.items() if isinstance(v, type)]
        print(f"Available classes: {classes}")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()

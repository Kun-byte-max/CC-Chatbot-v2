import sys
import asyncio
from pathlib import Path

root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from backend.api.employee import handle_employee_context


async def main():
    print("=" * 60)
    print("TESTING WIDGET INTENT ROUTING IN HANDLE_EMPLOYEE_CONTEXT")
    print("=" * 60)

    # Test 1: Position Closing Soon
    print("\n--- 1. Testing 'Show me jobs closing soon' ---")
    res1 = await handle_employee_context("Show me jobs closing soon")
    print("result_type:", res1.get("result_type") if res1 else None)
    print("results count:", len(res1.get("results") or []) if res1 else 0)
    if res1 and res1.get("results"):
        first = res1["results"][0]
        print(f"First Job Card: title='{first.title}', company='{first.company}'")

    # Test 2: Organizations Near You
    print("\n" + "=" * 60)
    print("--- 2. Testing 'Show me companies near me' ---")
    res2 = await handle_employee_context("Show me companies near me", user_location="Delhi")
    print("result_type:", res2.get("result_type") if res2 else None)
    print("results count:", len(res2.get("results") or []) if res2 else 0)
    if res2 and res2.get("results"):
        first_org = res2["results"][0]
        print(f"First Org Card: name='{first_org.get('name')}', city='{first_org.get('city')}'")

    print("\n" + "=" * 60)
    print("EMPLOYEE WIDGET INTENT TEST COMPLETED!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

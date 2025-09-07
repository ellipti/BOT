#!/usr/bin/env python3
"""Test concurrent access to atomic operations"""

import threading
import time
from pathlib import Path

from utils.atomic_io import atomic_read_json, atomic_update_json, atomic_write_json


def test_concurrent_access():
    """Test atomic operations under concurrent access"""
    print("Атом үйлдлүүдийн зэрэгцээ хандалтын тестийг хийж байна...")

    test_file = Path("concurrent_test.json")
    if test_file.exists():
        test_file.unlink()

    # Initialize file
    atomic_write_json(test_file, {"counter": 0, "operations": []})

    num_threads = 3
    num_operations_per_thread = 5

    results = []
    errors = []

    def worker(thread_id: int):
        """Worker function that performs atomic updates"""
        try:
            for i in range(num_operations_per_thread):

                def increment_counter(data):
                    if data is None:
                        data = {"counter": 0, "operations": []}

                    current_counter = data.get("counter", 0)
                    operations = data.get("operations", [])

                    # Simulate some processing time
                    time.sleep(0.01)  # Reduced from 0.001 to avoid too much contention

                    new_data = {
                        "counter": current_counter + 1,
                        "operations": operations
                        + [
                            {
                                "thread": thread_id,
                                "operation": i,
                                "timestamp": time.time(),
                            }
                        ],
                    }

                    return new_data

                # Each thread waits a bit to avoid all starting at once
                time.sleep(thread_id * 0.01)
                atomic_update_json(test_file, increment_counter)
                results.append(f"Thread {thread_id} operation {i} completed")

                # Small delay between operations in same thread
                time.sleep(0.02)

        except Exception as e:
            errors.append(f"Thread {thread_id} error: {e}")

    # Start all threads
    threads = []
    start_time = time.time()

    for i in range(num_threads):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    # Wait for all threads to complete
    for t in threads:
        t.join()

    end_time = time.time()

    # Check results
    final_data = atomic_read_json(test_file)
    if final_data is None:
        final_data = {"counter": 0, "operations": []}

    final_counter = final_data.get("counter", 0)
    final_operations = final_data.get("operations", [])

    expected_count = num_threads * num_operations_per_thread

    print("\nTest Results:")
    print(f"   Expected operations: {expected_count}")
    print(f"   Actual counter: {final_counter}")
    print(f"   Operations recorded: {len(final_operations)}")
    print(f"   Successful results: {len(results)}")
    print(f"   Errors: {len(errors)}")
    print(f"   Execution time: {end_time - start_time:.2f}s")

    # Validate results
    success = True
    if final_counter != expected_count:
        print(f"   ❌ Counter mismatch: expected {expected_count}, got {final_counter}")
        success = False

    if len(final_operations) != expected_count:
        print(
            f"   ❌ Operations count mismatch: expected {expected_count}, got {len(final_operations)}"
        )
        success = False

    if len(errors) > 0:
        print(f"   ❌ Errors occurred: {errors}")
        success = False

    if success:
        print("   ✅ All concurrent operations completed successfully!")
        print("   ✅ Race conditions prevented by atomic operations!")

    # Cleanup
    test_file.unlink()

    return success


def test_file_locking_contention():
    """Test file locking under contention"""
    print("\nTesting file locking contention...")

    test_file = Path("locking_test.json")
    if test_file.exists():
        test_file.unlink()

    # Initialize
    atomic_write_json(test_file, {"access_log": []})

    num_threads = 3
    access_duration = 0.5  # seconds each thread holds the lock

    access_times = []
    errors = []

    def long_operation(thread_id: int):
        """Simulate a long operation that holds the file lock"""
        try:
            start = time.time()

            def add_to_log(data):
                if data is None:
                    data = {"access_log": []}

                log = data.get("access_log", [])

                # Simulate long processing while holding the lock
                time.sleep(access_duration)

                log.append(
                    {
                        "thread": thread_id,
                        "start_time": start,
                        "processing_time": access_duration,
                    }
                )

                return {"access_log": log}

            atomic_update_json(test_file, add_to_log)
            end = time.time()

            access_times.append(
                {
                    "thread": thread_id,
                    "start": start,
                    "end": end,
                    "duration": end - start,
                }
            )

        except Exception as e:
            errors.append(f"Thread {thread_id}: {e}")

    # Start threads simultaneously
    threads = []
    for i in range(num_threads):
        t = threading.Thread(target=long_operation, args=(i,))
        threads.append(t)

    # Start all at once
    start_time = time.time()
    for t in threads:
        t.start()

    for t in threads:
        t.join()

    total_time = time.time() - start_time

    # Check results
    final_data = atomic_read_json(test_file)
    if final_data is None:
        final_data = {"access_log": []}

    access_log = final_data.get("access_log", [])

    print("\nFile Locking Test Results:")
    print(f"   Threads: {num_threads}")
    print(f"   Expected processing time per thread: {access_duration}s")
    print(f"   Total execution time: {total_time:.2f}s")
    print(f"   Access log entries: {len(access_log)}")
    print(f"   Errors: {len(errors)}")

    # Validate sequential access (should be close to num_threads * access_duration)
    expected_min_time = num_threads * access_duration
    success = True

    if len(access_log) != num_threads:
        print("   ❌ Missing access log entries")
        success = False

    if total_time < expected_min_time - 0.1:  # Allow small margin
        print("   ❌ Execution too fast, possible race condition")
        success = False

    if len(errors) > 0:
        print(f"   ❌ Errors: {errors}")
        success = False

    if success:
        print("   ✅ File locking working properly - sequential access enforced!")

    # Cleanup
    test_file.unlink()

    return success


if __name__ == "__main__":
    success1 = test_concurrent_access()
    success2 = test_file_locking_contention()

    if success1 and success2:
        print("\n🎉 Бүх зэрэгцээ тестүүд амжилттай!")
        print("🔒 Атом үйлдлүүд зөв ажиллаж байна!")
        print("🛡️ Уралдааны нөхцөлийг амжилттай сэргийллээ!")
    else:
        print("\n❌ Зарим зэрэгцээ тестүүд амжилтгүй боллоо!")

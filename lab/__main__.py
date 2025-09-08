"""
Strategy Lab - Module Entry Point

Enables running lab as a Python module:
    python -m lab.runner --max-jobs 4
    python -m lab.visualize results.csv
"""

if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Add the parent directory to sys.path to enable imports
    lab_dir = Path(__file__).parent
    parent_dir = lab_dir.parent
    sys.path.insert(0, str(parent_dir))

    # Check if specific subcommand requested
    if len(sys.argv) > 1 and sys.argv[1] == "visualize":
        # Run visualization module
        sys.argv = sys.argv[1:]  # Remove "visualize" from args
        from lab.visualize import main as viz_main

        viz_main()
    else:
        # Run main runner
        from lab.runner import main

        main()

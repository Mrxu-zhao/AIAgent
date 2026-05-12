import argparse
import json

import runner


def build_parser():
    parser = argparse.ArgumentParser(description="Run control-plane task batch")
    parser.add_argument("--max-workers", type=int, default=2)
    return parser


def main():
    args = build_parser().parse_args()
    result = runner.run_task_batch(max_workers=args.max_workers)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

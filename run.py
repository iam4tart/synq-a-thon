import sys
import os
import argparse
import json

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from src.pipeline import BreakdownPipeline
    from src.human_gate import HumanApprovalGate
    from src.pii_sanitizer import PIISanitizer
except ImportError:
    from solutions.src.pipeline import BreakdownPipeline
    from solutions.src.human_gate import HumanApprovalGate
    from solutions.src.pii_sanitizer import PIISanitizer


def main():
    parser = argparse.ArgumentParser(description="Meridian Freight Breakdown-to-Resolution Automation")
    parser.add_argument("--process-queue", type=str, nargs="?", const="tickets.json", default="tickets.json", help="Path to input breakdown queue file")
    parser.add_argument("--approve-comms", action="store_true", help="Approve all pending client communications")
    parser.add_argument("--approver", type=str, default="Ops_Manager", help="Name of approving manager")
    parser.add_argument("--verify-idempotency", action="store_true", help="Run back-to-back idempotency verification")
    parser.add_argument("--base-dir", type=str, default=current_dir, help="Base directory containing static corpus")
    parser.add_argument("--web", action="store_true", help="Start FastAPI Web Dashboard on http://127.0.0.1:8000")
    parser.add_argument("--port", type=int, default=8000, help="Port for Web Dashboard")

    args = parser.parse_args()

    if args.web:
        import uvicorn
        print(f"Starting Meridian Freight Web Dashboard on http://127.0.0.1:{args.port} ...")
        uvicorn_app = "app:app" if os.path.basename(current_dir) == "solutions" else "solutions.app:app"
        uvicorn.run(uvicorn_app, host="127.0.0.1", port=args.port, reload=False)
        return

    output_dir = os.path.join(current_dir, "outputs")
    audit_dir = os.path.join(current_dir, "audit")
    pipeline = BreakdownPipeline(base_dir=args.base_dir, output_dir=output_dir, audit_dir=audit_dir)
    gate = HumanApprovalGate(output_dir=output_dir)

    if args.verify_idempotency:
        print("=== Running Idempotency Test (Run 1) ===")
        stats1 = pipeline.process_queue_file(args.process_queue)
        print(f"Run 1 Stats: {stats1}")
        
        wo_path = os.path.join(output_dir, "work_orders.jsonl")
        with open(wo_path, "r", encoding="utf-8") as f:
            wo1 = f.read()

        print("=== Running Idempotency Test (Run 2 - Back to Back) ===")
        stats2 = pipeline.process_queue_file(args.process_queue)
        print(f"Run 2 Stats: {stats2}")
        
        with open(wo_path, "r", encoding="utf-8") as f:
            wo2 = f.read()

        assert wo1 == wo2, "IDEMPOTENCY FAILURE: Outputs differ between runs!"
        print(">>> IDEMPOTENCY VERIFIED: Outputs are bitwise identical! Zero duplicates generated.")
        return

    print(f"=== Processing Breakdown Queue: {args.process_queue} ===")
    stats = pipeline.process_queue_file(args.process_queue)
    print(f"Queue Processing Complete:")
    print(f" - Total Raw Records: {stats['total_raw']}")
    print(f" - Valid Processed:   {stats['processed_valid']}")
    print(f" - Quarantined:       {stats['quarantined']}")
    print(f" - Duplicates Skipped:{stats['duplicates_skipped']}")

    if args.approve_comms:
        print("\n=== Approving Client Communications ===")
        approved = gate.approve(approver_name=args.approver)
        print(f"Approved and sent {approved} client messages to solutions/outputs/comms_sent.jsonl")


if __name__ == '__main__':
    main()

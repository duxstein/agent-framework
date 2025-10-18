"""
Example usage of the Enterprise AI Agent Framework SDK.

This example demonstrates how to create, validate, and manage flows
using the SDK components.
"""

import json
from pathlib import Path

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sdk.models import Task, Flow
from sdk.policy import RetryLimitPolicy, TimeoutPolicy, TenantIsolationPolicy
from sdk.registry import FlowRegistry


def create_example_flow():
    """Create an example flow with multiple tasks."""
    
    # Create tasks
    task1 = Task(
        handler="data_processor",
        inputs={"source": "database", "table": "users"},
        retries=3,
        timeout=300,
        condition="user_count > 0",
        metadata={"priority": "high"}
    )
    
    task2 = Task(
        handler="ml_predictor",
        inputs={"model": "sentiment_analysis", "features": ["text", "timestamp"]},
        retries=2,
        timeout=600,
        metadata={"model_version": "v2.1"}
    )
    
    task3 = Task(
        handler="notification_sender",
        inputs={"channel": "email", "template": "prediction_results"},
        retries=1,
        timeout=120,
        condition="prediction_confidence > 0.8"
    )
    
    # Create flow
    flow = Flow(
        tasks=[task1, task2, task3],
        version="1.0.0",
        type="DAG",
        tenant_id="tenant_123",
        metadata={"environment": "production", "owner": "data_team"}
    )
    
    return flow


def validate_flow_example():
    """Example of flow validation."""
    print("=== Flow Validation Example ===")
    
    flow = create_example_flow()
    
    # Validate the flow
    validation_result = flow.validate()
    
    print(f"Flow ID: {flow.id}")
    print(f"Version: {flow.version}")
    print(f"Type: {flow.type}")
    print(f"Tenant ID: {flow.tenant_id}")
    print(f"Number of tasks: {len(flow.tasks)}")
    
    if validation_result["valid"]:
        print("Flow validation passed!")
    else:
        print("Flow validation failed:")
        for error in validation_result["errors"]:
            print(f"  - {error}")
    
    # Show flow statistics
    stats = flow.get_statistics()
    print(f"\nFlow Statistics:")
    print(f"  - Total tasks: {stats['total_tasks']}")
    print(f"  - Unique handlers: {stats['unique_handlers']}")
    print(f"  - Total retries: {stats['total_retries']}")
    print(f"  - Tasks with timeout: {stats['tasks_with_timeout']}")
    print(f"  - Tasks with condition: {stats['tasks_with_condition']}")


def policy_example():
    """Example of using policies."""
    print("\n=== Policy Example ===")
    
    flow = create_example_flow()
    
    # Create policies
    retry_policy = RetryLimitPolicy(max_retries=5)
    timeout_policy = TimeoutPolicy(max_timeout=3600)
    tenant_policy = TenantIsolationPolicy()
    
    # Apply policies to flow
    print("Applying policies to flow...")
    
    # Check tenant isolation
    tenant_result = tenant_policy.evaluate(flow=flow)
    print(f"Tenant isolation: {tenant_result['result'].value}")
    print(f"Message: {tenant_result['message']}")
    
    # Check retry limits for each task
    for i, task in enumerate(flow.tasks):
        retry_result = retry_policy.evaluate(task=task, flow=flow)
        print(f"Task {i+1} retry policy: {retry_result['result'].value}")
        
        timeout_result = timeout_policy.evaluate(task=task, flow=flow)
        print(f"Task {i+1} timeout policy: {timeout_result['result'].value}")
        if timeout_result['result'].value == 'modify':
            print(f"  Suggested timeout: {timeout_result['modifications']['timeout']}s")


def save_and_load_example():
    """Example of saving and loading flows."""
    print("\n=== Save and Load Example ===")
    
    flow = create_example_flow()
    
    # Save flow to file
    flow_file = Path("example_flow.json")
    flow.save(flow_file)
    print(f"Flow saved to: {flow_file}")
    
    # Load flow from file
    loaded_flow = Flow.load(flow_file)
    print(f"Flow loaded from: {flow_file}")
    print(f"Loaded flow ID: {loaded_flow.id}")
    print(f"Loaded flow version: {loaded_flow.version}")
    print(f"Loaded flow tasks: {len(loaded_flow.tasks)}")
    
    # Clean up
    flow_file.unlink()
    print("Example file cleaned up")


def registry_example():
    """Example of using the flow registry (without actual database)."""
    print("\n=== Registry Example ===")
    
    flow = create_example_flow()
    
    print("Flow registry example (simulated):")
    print(f"  - Flow ID: {flow.id}")
    print(f"  - Flow name: 'Example Data Processing Flow'")
    print(f"  - Description: 'Processes user data and generates predictions'")
    print(f"  - Tags: ['data-processing', 'ml', 'notifications']")
    print(f"  - Tenant: {flow.tenant_id}")
    
    print("\nRegistry operations that would be available:")
    print("  - register_flow(): Register flow in database")
    print("  - get_flow(): Retrieve flow by ID")
    print("  - list_flows(): List flows with filters")
    print("  - update_flow(): Update existing flow")
    print("  - delete_flow(): Remove flow from registry")
    print("  - search_flows(): Search flows by name/description/tags")


def cli_example():
    """Example of CLI usage."""
    print("\n=== CLI Example ===")
    
    print("The agentctl CLI tool provides the following commands:")
    print("  - validate <flow.json>: Validate a flow definition")
    print("  - publish <flow.json> --name 'My Flow': Publish flow to registry")
    print("  - list: List flows in registry")
    print("  - get <flow-id>: Retrieve flow by ID")
    print("  - delete <flow-id>: Delete flow from registry")
    print("  - stats: Show registry statistics")
    
    print("\nExample CLI commands:")
    print("  python agentctl validate example_flow.json")
    print("  python agentctl publish example_flow.json --name 'Data Processing Flow' --tags 'ml,data'")
    print("  python agentctl list --tenant-id tenant_123")
    print("  python agentctl get flow-123-456")


if __name__ == "__main__":
    print("Enterprise AI Agent Framework SDK - Example Usage")
    print("=" * 50)
    
    validate_flow_example()
    policy_example()
    save_and_load_example()
    registry_example()
    cli_example()
    
    print("\n" + "=" * 50)
    print("Example completed successfully!")

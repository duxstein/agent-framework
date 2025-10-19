"""
Example usage of the Enterprise AI Agent Framework SDK.

This file demonstrates how to create tasks, flows, guardrails,
and manage multi-tenancy using the SDK classes.
"""

from sdk import Task, Flow, Guardrails, TenantManager, ValidationError
from datetime import timedelta


def example_task_creation():
    """Example of creating tasks with different configurations."""
    print("=== Task Creation Examples ===")
    
    # Simple task
    task1 = Task(
        handler="email_sender",
        inputs={"to": "user@example.com", "subject": "Hello", "body": "Test message"},
        retries=3,
        timeout=timedelta(minutes=5)
    )
    print(f"Task 1: {task1}")
    
    # Task with condition
    def should_send_email(context):
        return context.get("user_preference", {}).get("email_enabled", True)
    
    task2 = Task(
        handler="email_sender",
        inputs={"to": "user@example.com", "subject": "Conditional", "body": "Conditional message"},
        condition=should_send_email,
        tenant_id="tenant_123"
    )
    print(f"Task 2: {task2}")
    print(f"Should execute: {task2.should_execute({'user_preference': {'email_enabled': True}})}")
    
    # Task serialization
    serialized = task1.serialize()
    print(f"Serialized task: {serialized}")
    
    # Task deserialization
    deserialized_task = Task.deserialize(serialized)
    print(f"Deserialized task: {deserialized_task}")


def example_flow_creation():
    """Example of creating and managing flows."""
    print("\n=== Flow Creation Examples ===")
    
    # Create tasks
    task1 = Task("email_sender", {"to": "user@example.com", "subject": "Welcome"})
    task2 = Task("slack_notifier", {"channel": "#general", "message": "User registered"})
    task3 = Task("database_logger", {"action": "user_registration", "user_id": "123"})
    
    # Create flow
    flow = Flow(tenant_id="tenant_123")
    flow.add_task(task1)
    flow.add_task(task2)
    flow.add_task(task3)
    
    print(f"Flow: {flow}")
    print(f"Number of tasks: {len(flow)}")
    
    # Flow validation
    validation_result = flow.validate()
    print(f"Flow validation: {validation_result}")
    
    # Flow statistics
    stats = flow.get_statistics()
    print(f"Flow statistics: {stats}")
    
    # Flow serialization
    flow_dict = flow.to_dict()
    print(f"Flow as dict: {flow_dict}")


def example_guardrails():
    """Example of using guardrails for validation and enforcement."""
    print("\n=== Guardrails Examples ===")
    
    # Create guardrails
    guardrails = Guardrails(
        max_retries=5,
        max_timeout=timedelta(minutes=10),
        allowed_handlers=["email_sender", "slack_notifier", "database_logger"],
        blocked_handlers=["dangerous_handler"],
        tenant_id="tenant_123"
    )
    
    # Create a task
    task = Task(
        handler="email_sender",
        inputs={"to": "user@example.com", "subject": "Test"},
        retries=3,
        timeout=timedelta(minutes=5),
        tenant_id="tenant_123"
    )
    
    # Validate task inputs
    is_valid, errors = guardrails.validate_task_inputs(task)
    print(f"Task validation: valid={is_valid}, errors={errors}")
    
    # Validate task output
    output = {"status": "success", "message_id": "12345"}
    is_valid, errors = guardrails.validate_task_output(task, output)
    print(f"Output validation: valid={is_valid}, errors={errors}")
    
    # Create a flow and validate it
    flow = Flow(tenant_id="tenant_123")
    flow.add_task(task)
    
    is_valid, errors = guardrails.validate_flow(flow)
    print(f"Flow validation: valid={is_valid}, errors={errors}")
    
    # Security report
    security_report = guardrails.get_security_report(flow)
    print(f"Security report: {security_report}")


def example_multitenancy():
    """Example of multi-tenancy management."""
    print("\n=== Multi-tenancy Examples ===")
    
    # Create tenant manager
    tenant_manager = TenantManager()
    
    # Register tenants
    tenant1_id = tenant_manager.register_tenant(
        name="Acme Corp",
        max_concurrent_flows=5,
        max_tasks_per_flow=50,
        allowed_handlers=["email_sender", "slack_notifier"]
    )
    
    tenant2_id = tenant_manager.register_tenant(
        name="Beta Inc",
        max_concurrent_flows=10,
        max_tasks_per_flow=100,
        allowed_handlers=["email_sender", "slack_notifier", "database_logger"]
    )
    
    print(f"Registered tenants: {tenant_manager.list_tenants()}")
    
    # Check tenant limits
    limits1 = tenant_manager.check_tenant_limits(tenant1_id)
    print(f"Tenant 1 limits: {limits1}")
    
    # Simulate flow execution
    if tenant_manager.increment_active_flows(tenant1_id):
        print(f"Incremented active flows for tenant 1")
        tenant_manager.increment_task_count(tenant1_id, 3)
        tenant_manager.decrement_active_flows(tenant1_id)
    
    # Get tenant statistics
    stats1 = tenant_manager.get_tenant_statistics(tenant1_id)
    print(f"Tenant 1 statistics: {stats1}")
    
    # Get all statistics
    all_stats = tenant_manager.get_all_statistics()
    print(f"All statistics: {all_stats}")


def example_integration():
    """Example of integrating all components together."""
    print("\n=== Integration Example ===")
    
    # Setup
    tenant_manager = TenantManager()
    tenant_id = tenant_manager.register_tenant(
        name="Demo Company",
        max_concurrent_flows=3,
        max_tasks_per_flow=20
    )
    
    guardrails = Guardrails(
        max_retries=3,
        max_timeout=timedelta(minutes=5),
        tenant_id=tenant_id
    )
    
    # Create a workflow
    flow = Flow(tenant_id=tenant_id)
    
    # Add tasks
    tasks = [
        Task("email_sender", {"to": "user@example.com", "subject": "Welcome"}, tenant_id=tenant_id),
        Task("slack_notifier", {"channel": "#general", "message": "New user"}, tenant_id=tenant_id),
        Task("database_logger", {"action": "user_registration"}, tenant_id=tenant_id)
    ]
    
    for task in tasks:
        flow.add_task(task)
    
    # Validate everything
    print(f"Flow validation: {flow.validate()}")
    print(f"Guardrails validation: {guardrails.validate_flow(flow)}")
    print(f"Tenant limits check: {tenant_manager.check_tenant_limits(tenant_id)}")
    
    # Simulate execution
    if tenant_manager.increment_active_flows(tenant_id):
        print("Flow execution started")
        
        for task in flow.get_execution_order():
            print(f"Executing task: {task.handler}")
            tenant_manager.increment_task_count(tenant_id)
        
        tenant_manager.decrement_active_flows(tenant_id)
        print("Flow execution completed")
    
    print(f"Final statistics: {tenant_manager.get_tenant_statistics(tenant_id)}")


if __name__ == "__main__":
    """Run all examples."""
    try:
        example_task_creation()
        example_flow_creation()
        example_guardrails()
        example_multitenancy()
        example_integration()
        print("\n=== All examples completed successfully! ===")
    except Exception as e:
        print(f"Error running examples: {e}")
        import traceback
        traceback.print_exc()

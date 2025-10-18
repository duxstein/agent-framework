"""
Unit tests for Enterprise AI Agent Framework SDK policy system.

This module contains comprehensive tests for the Policy classes and interfaces.
"""

import pytest
from datetime import datetime

from sdk.models import Task, Flow
from sdk.policy import (
    Policy, PreTaskPolicy, PostTaskPolicy, FlowPolicy,
    PolicyResult, PolicyError,
    RetryLimitPolicy, TimeoutPolicy, TenantIsolationPolicy, ResultValidationPolicy
)


class TestPolicy:
    """Test cases for the base Policy class."""
    
    def test_policy_creation(self):
        """Test policy creation with default values."""
        class TestPolicy(Policy):
            def evaluate(self, context, **kwargs):
                return {
                    'result': PolicyResult.ALLOW,
                    'message': 'Test policy',
                    'modifications': None,
                    'metadata': {}
                }
        
        policy = TestPolicy(name="test_policy")
        
        assert policy.name == "test_policy"
        assert policy.description == ""
        assert policy.enabled is True
        assert policy.priority == 100
        assert policy.metadata == {}
    
    def test_policy_creation_with_custom_values(self):
        """Test policy creation with custom values."""
        class TestPolicy(Policy):
            def evaluate(self, context, **kwargs):
                return {
                    'result': PolicyResult.ALLOW,
                    'message': 'Test policy',
                    'modifications': None,
                    'metadata': {}
                }
        
        policy = TestPolicy(
            name="custom_policy",
            description="A custom test policy",
            enabled=False,
            priority=50,
            metadata={"env": "test"}
        )
        
        assert policy.name == "custom_policy"
        assert policy.description == "A custom test policy"
        assert policy.enabled is False
        assert policy.priority == 50
        assert policy.metadata == {"env": "test"}
    
    def test_policy_is_enabled(self):
        """Test policy enabled status."""
        class TestPolicy(Policy):
            def evaluate(self, context, **kwargs):
                return {
                    'result': PolicyResult.ALLOW,
                    'message': 'Test policy',
                    'modifications': None,
                    'metadata': {}
                }
        
        enabled_policy = TestPolicy(name="enabled", enabled=True)
        disabled_policy = TestPolicy(name="disabled", enabled=False)
        
        assert enabled_policy.is_enabled() is True
        assert disabled_policy.is_enabled() is False
    
    def test_policy_get_priority(self):
        """Test policy priority."""
        class TestPolicy(Policy):
            def evaluate(self, context, **kwargs):
                return {
                    'result': PolicyResult.ALLOW,
                    'message': 'Test policy',
                    'modifications': None,
                    'metadata': {}
                }
        
        policy = TestPolicy(name="test", priority=75)
        assert policy.get_priority() == 75
    
    def test_policy_to_dict(self):
        """Test policy serialization to dictionary."""
        class TestPolicy(Policy):
            def evaluate(self, context, **kwargs):
                return {
                    'result': PolicyResult.ALLOW,
                    'message': 'Test policy',
                    'modifications': None,
                    'metadata': {}
                }
        
        policy = TestPolicy(
            name="test_policy",
            description="Test description",
            enabled=True,
            priority=100,
            metadata={"env": "test"}
        )
        
        policy_dict = policy.to_dict()
        
        assert policy_dict["name"] == "test_policy"
        assert policy_dict["description"] == "Test description"
        assert policy_dict["enabled"] is True
        assert policy_dict["priority"] == 100
        assert policy_dict["metadata"] == {"env": "test"}
        assert policy_dict["type"] == "TestPolicy"


class TestRetryLimitPolicy:
    """Test cases for the RetryLimitPolicy."""
    
    def test_retry_limit_policy_creation(self):
        """Test retry limit policy creation."""
        policy = RetryLimitPolicy(max_retries=5)
        
        assert policy.name == "retry_limit"
        assert policy.max_retries == 5
    
    def test_retry_limit_policy_allow(self):
        """Test retry limit policy allowing task."""
        policy = RetryLimitPolicy(max_retries=5)
        task = Task(handler="test", retries=3)
        flow = Flow(tasks=[task])
        
        result = policy.evaluate(task=task, flow=flow)
        
        assert result["result"] == PolicyResult.ALLOW
        assert "Retry limit policy passed" in result["message"]
        assert result["modifications"] is None
        assert result["metadata"]["max_retries"] == 5
        assert result["metadata"]["task_retries"] == 3
    
    def test_retry_limit_policy_deny(self):
        """Test retry limit policy denying task."""
        policy = RetryLimitPolicy(max_retries=3)
        task = Task(handler="test", retries=5)
        flow = Flow(tasks=[task])
        
        result = policy.evaluate(task=task, flow=flow)
        
        assert result["result"] == PolicyResult.DENY
        assert "exceeds maximum allowed" in result["message"]
        assert result["modifications"] is None
        assert result["metadata"]["max_retries"] == 3
        assert result["metadata"]["task_retries"] == 5


class TestTimeoutPolicy:
    """Test cases for the TimeoutPolicy."""
    
    def test_timeout_policy_creation(self):
        """Test timeout policy creation."""
        policy = TimeoutPolicy(max_timeout=3600)
        
        assert policy.name == "timeout_limit"
        assert policy.max_timeout == 3600
    
    def test_timeout_policy_allow(self):
        """Test timeout policy allowing task."""
        policy = TimeoutPolicy(max_timeout=3600)
        task = Task(handler="test", timeout=1800)
        flow = Flow(tasks=[task])
        
        result = policy.evaluate(task=task, flow=flow)
        
        assert result["result"] == PolicyResult.ALLOW
        assert "Timeout policy passed" in result["message"]
        assert result["modifications"] is None
        assert result["metadata"]["max_timeout"] == 3600
        assert result["metadata"]["task_timeout"] == 1800
    
    def test_timeout_policy_modify(self):
        """Test timeout policy modifying task."""
        policy = TimeoutPolicy(max_timeout=1800)
        task = Task(handler="test", timeout=3600)
        flow = Flow(tasks=[task])
        
        result = policy.evaluate(task=task, flow=flow)
        
        assert result["result"] == PolicyResult.MODIFY
        assert "exceeds maximum allowed" in result["message"]
        assert result["modifications"]["timeout"] == 1800
        assert result["metadata"]["max_timeout"] == 1800
        assert result["metadata"]["original_timeout"] == 3600


class TestTenantIsolationPolicy:
    """Test cases for the TenantIsolationPolicy."""
    
    def test_tenant_isolation_policy_creation(self):
        """Test tenant isolation policy creation."""
        policy = TenantIsolationPolicy()
        
        assert policy.name == "tenant_isolation"
    
    def test_tenant_isolation_policy_allow(self):
        """Test tenant isolation policy allowing flow."""
        policy = TenantIsolationPolicy()
        task1 = Task(handler="handler1", tenant_id="tenant1")
        task2 = Task(handler="handler2", tenant_id="tenant1")
        flow = Flow(tasks=[task1, task2], tenant_id="tenant1")
        
        result = policy.evaluate(flow=flow)
        
        assert result["result"] == PolicyResult.ALLOW
        assert "Tenant isolation policy passed" in result["message"]
        assert result["modifications"] is None
        assert result["metadata"]["tenant_id"] == "tenant1"
    
    def test_tenant_isolation_policy_deny_no_tenant(self):
        """Test tenant isolation policy denying flow without tenant."""
        policy = TenantIsolationPolicy()
        task = Task(handler="test")
        flow = Flow(tasks=[task])
        
        result = policy.evaluate(flow=flow)
        
        assert result["result"] == PolicyResult.DENY
        assert "must have a tenant_id" in result["message"]
        assert result["modifications"] is None
    
    def test_tenant_isolation_policy_deny_inconsistent_tenants(self):
        """Test tenant isolation policy denying flow with inconsistent tenants."""
        policy = TenantIsolationPolicy()
        task1 = Task(handler="handler1", tenant_id="tenant1")
        task2 = Task(handler="handler2", tenant_id="tenant2")
        flow = Flow(tasks=[task1, task2])
        
        result = policy.evaluate(flow=flow)
        
        assert result["result"] == PolicyResult.DENY
        assert "must have the same tenant_id" in result["message"]
        assert result["modifications"] is None


class TestResultValidationPolicy:
    """Test cases for the ResultValidationPolicy."""
    
    def test_result_validation_policy_creation(self):
        """Test result validation policy creation."""
        policy = ResultValidationPolicy(required_fields=["status", "data"])
        
        assert policy.name == "result_validation"
        assert policy.required_fields == ["status", "data"]
    
    def test_result_validation_policy_allow(self):
        """Test result validation policy allowing result."""
        policy = ResultValidationPolicy(required_fields=["status", "data"])
        task = Task(handler="test")
        flow = Flow(tasks=[task])
        result = {"status": "success", "data": {"key": "value"}}
        
        validation_result = policy.evaluate(task=task, flow=flow, result=result)
        
        assert validation_result["result"] == PolicyResult.ALLOW
        assert "Result validation policy passed" in validation_result["message"]
        assert validation_result["modifications"] is None
        assert validation_result["metadata"]["required_fields"] == ["status", "data"]
    
    def test_result_validation_policy_deny_empty_result(self):
        """Test result validation policy denying empty result."""
        policy = ResultValidationPolicy(required_fields=["status"])
        task = Task(handler="test")
        flow = Flow(tasks=[task])
        result = {}
        
        validation_result = policy.evaluate(task=task, flow=flow, result=result)
        
        assert validation_result["result"] == PolicyResult.DENY
        assert "Task result is empty" in validation_result["message"]
        assert validation_result["modifications"] is None
    
    def test_result_validation_policy_deny_missing_fields(self):
        """Test result validation policy denying result with missing fields."""
        policy = ResultValidationPolicy(required_fields=["status", "data", "timestamp"])
        task = Task(handler="test")
        flow = Flow(tasks=[task])
        result = {"status": "success", "data": {"key": "value"}}
        
        validation_result = policy.evaluate(task=task, flow=flow, result=result)
        
        assert validation_result["result"] == PolicyResult.DENY
        assert "missing required fields" in validation_result["message"]
        assert validation_result["modifications"] is None
        assert "timestamp" in validation_result["metadata"]["missing_fields"]


class TestPreTaskPolicy:
    """Test cases for the PreTaskPolicy interface."""
    
    def test_pre_task_policy_interface(self):
        """Test PreTaskPolicy interface implementation."""
        class CustomPreTaskPolicy(PreTaskPolicy):
            def evaluate(self, task, flow, context=None):
                return {
                    'result': PolicyResult.ALLOW,
                    'message': 'Custom pre-task policy',
                    'modifications': None,
                    'metadata': {}
                }
        
        policy = CustomPreTaskPolicy(name="custom_pre_task")
        task = Task(handler="test")
        flow = Flow(tasks=[task])
        
        result = policy.evaluate(task=task, flow=flow)
        
        assert result["result"] == PolicyResult.ALLOW
        assert result["message"] == "Custom pre-task policy"


class TestPostTaskPolicy:
    """Test cases for the PostTaskPolicy interface."""
    
    def test_post_task_policy_interface(self):
        """Test PostTaskPolicy interface implementation."""
        class CustomPostTaskPolicy(PostTaskPolicy):
            def evaluate(self, task, flow, result, context=None):
                return {
                    'result': PolicyResult.ALLOW,
                    'message': 'Custom post-task policy',
                    'modifications': None,
                    'metadata': {}
                }
        
        policy = CustomPostTaskPolicy(name="custom_post_task")
        task = Task(handler="test")
        flow = Flow(tasks=[task])
        result = {"status": "success"}
        
        evaluation_result = policy.evaluate(task=task, flow=flow, result=result)
        
        assert evaluation_result["result"] == PolicyResult.ALLOW
        assert evaluation_result["message"] == "Custom post-task policy"


class TestFlowPolicy:
    """Test cases for the FlowPolicy interface."""
    
    def test_flow_policy_interface(self):
        """Test FlowPolicy interface implementation."""
        class CustomFlowPolicy(FlowPolicy):
            def evaluate(self, flow, context=None):
                return {
                    'result': PolicyResult.ALLOW,
                    'message': 'Custom flow policy',
                    'modifications': None,
                    'metadata': {}
                }
        
        policy = CustomFlowPolicy(name="custom_flow")
        task = Task(handler="test")
        flow = Flow(tasks=[task])
        
        result = policy.evaluate(flow=flow)
        
        assert result["result"] == PolicyResult.ALLOW
        assert result["message"] == "Custom flow policy"


class TestPolicyResult:
    """Test cases for the PolicyResult enum."""
    
    def test_policy_result_values(self):
        """Test PolicyResult enum values."""
        assert PolicyResult.ALLOW.value == "allow"
        assert PolicyResult.DENY.value == "deny"
        assert PolicyResult.MODIFY.value == "modify"
    
    def test_policy_result_string_representation(self):
        """Test PolicyResult string representation."""
        assert str(PolicyResult.ALLOW) == "PolicyResult.ALLOW"
        assert str(PolicyResult.DENY) == "PolicyResult.DENY"
        assert str(PolicyResult.MODIFY) == "PolicyResult.MODIFY"


class TestPolicyError:
    """Test cases for the PolicyError exception."""
    
    def test_policy_error_creation(self):
        """Test PolicyError creation."""
        error = PolicyError("Test error message")
        
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)
    
    def test_policy_error_inheritance(self):
        """Test PolicyError inheritance."""
        error = PolicyError("Test error")
        
        assert isinstance(error, Exception)
        assert isinstance(error, PolicyError)

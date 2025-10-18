"""
Guardrails class for Enterprise AI Agent Framework.

Provides input validation, output validation, retry enforcement,
timeout enforcement, and security guardrails for tasks and flows.
"""

import re
import time
from typing import Any, Dict, List, Optional, Callable, Union, Tuple
from datetime import datetime, timedelta
from .task import Task
from .flow import Flow


class ValidationError(Exception):
    """Exception raised when validation fails."""
    pass


class Guardrails:
    """
    Guardrails for Enterprise AI Agent Framework.
    
    Provides comprehensive validation and enforcement mechanisms for
    tasks and flows, including input/output validation, retry/timeout
    enforcement, and security checks.
    
    Attributes:
        max_retries (int): Maximum allowed retries across all tasks
        max_timeout (Optional[timedelta]): Maximum allowed timeout
        allowed_handlers (Optional[List[str]]): Whitelist of allowed handlers
        blocked_handlers (Optional[List[str]]): Blacklist of blocked handlers
        input_validators (Dict[str, Callable]): Custom input validators by handler
        output_validators (Dict[str, Callable]): Custom output validators by handler
        tenant_id (Optional[str]): Tenant identifier for multi-tenancy
    """
    
    def __init__(
        self,
        max_retries: int = 10,
        max_timeout: Optional[Union[int, timedelta]] = None,
        allowed_handlers: Optional[List[str]] = None,
        blocked_handlers: Optional[List[str]] = None,
        tenant_id: Optional[str] = None
    ):
        """
        Initialize Guardrails.
        
        Args:
            max_retries (int): Maximum allowed retries across all tasks
            max_timeout (Optional[Union[int, timedelta]]): Maximum allowed timeout
            allowed_handlers (Optional[List[str]]): Whitelist of allowed handlers
            blocked_handlers (Optional[List[str]]): Blacklist of blocked handlers
            tenant_id (Optional[str]): Tenant identifier for multi-tenancy
        """
        self.max_retries = max_retries
        self.max_timeout = self._parse_timeout(max_timeout)
        self.allowed_handlers = allowed_handlers or []
        self.blocked_handlers = blocked_handlers or []
        self.input_validators: Dict[str, Callable] = {}
        self.output_validators: Dict[str, Callable] = {}
        self.tenant_id = tenant_id
    
    def _parse_timeout(self, timeout: Optional[Union[int, timedelta]]) -> Optional[timedelta]:
        """
        Parse timeout value into timedelta object.
        
        Args:
            timeout: Timeout in seconds (int) or timedelta object
            
        Returns:
            Optional[timedelta]: Parsed timeout or None
        """
        if timeout is None:
            return None
        if isinstance(timeout, int):
            return timedelta(seconds=timeout)
        if isinstance(timeout, timedelta):
            return timeout
        raise ValueError("Timeout must be an integer (seconds) or timedelta object")
    
    def validate_task_inputs(self, task: Task) -> Tuple[bool, List[str]]:
        """
        Validate task inputs before execution.
        
        Args:
            task (Task): Task to validate
            
        Returns:
            Tuple[bool, List[str]]: (is_valid, list_of_errors)
        """
        errors = []
        
        # Check handler permissions
        if not self._is_handler_allowed(task.handler):
            errors.append(f"Handler '{task.handler}' is not allowed")
        
        # Check retry limits
        if task.retries > self.max_retries:
            errors.append(f"Retries ({task.retries}) exceed maximum allowed ({self.max_retries})")
        
        # Check timeout limits
        if task.timeout and self.max_timeout and task.timeout > self.max_timeout:
            errors.append(f"Timeout ({task.timeout}) exceeds maximum allowed ({self.max_timeout})")
        
        # Check tenant consistency
        if self.tenant_id and task.tenant_id and self.tenant_id != task.tenant_id:
            errors.append("Task tenant_id doesn't match guardrails tenant_id")
        
        # Run custom input validator if available
        if task.handler in self.input_validators:
            try:
                validator_result = self.input_validators[task.handler](task.inputs)
                if not validator_result:
                    errors.append(f"Custom input validation failed for handler '{task.handler}'")
            except Exception as e:
                errors.append(f"Input validation error for handler '{task.handler}': {str(e)}")
        
        # Basic input validation
        if not isinstance(task.inputs, dict):
            errors.append("Task inputs must be a dictionary")
        
        # Check for potentially dangerous inputs
        dangerous_patterns = [
            r'<script.*?>.*?</script>',  # Script tags
            r'javascript:',  # JavaScript URLs
            r'data:text/html',  # Data URLs
            r'vbscript:',  # VBScript URLs
        ]
        
        inputs_str = str(task.inputs).lower()
        for pattern in dangerous_patterns:
            if re.search(pattern, inputs_str, re.IGNORECASE):
                errors.append(f"Potentially dangerous content detected in inputs: {pattern}")
        
        return len(errors) == 0, errors
    
    def validate_task_output(self, task: Task, output: Any) -> Tuple[bool, List[str]]:
        """
        Validate task output after execution.
        
        Args:
            task (Task): Task that produced the output
            output (Any): Output to validate
            
        Returns:
            Tuple[bool, List[str]]: (is_valid, list_of_errors)
        """
        errors = []
        
        # Run custom output validator if available
        if task.handler in self.output_validators:
            try:
                validator_result = self.output_validators[task.handler](output)
                if not validator_result:
                    errors.append(f"Custom output validation failed for handler '{task.handler}'")
            except Exception as e:
                errors.append(f"Output validation error for handler '{task.handler}': {str(e)}")
        
        # Basic output validation
        if output is None:
            errors.append("Task output cannot be None")
        
        # Check for potentially dangerous outputs
        if isinstance(output, str):
            dangerous_patterns = [
                r'<script.*?>.*?</script>',  # Script tags
                r'javascript:',  # JavaScript URLs
                r'data:text/html',  # Data URLs
            ]
            
            for pattern in dangerous_patterns:
                if re.search(pattern, output, re.IGNORECASE):
                    errors.append(f"Potentially dangerous content detected in output: {pattern}")
        
        return len(errors) == 0, errors
    
    def validate_flow(self, flow: Flow) -> Tuple[bool, List[str]]:
        """
        Validate an entire flow.
        
        Args:
            flow (Flow): Flow to validate
            
        Returns:
            Tuple[bool, List[str]]: (is_valid, list_of_errors)
        """
        errors = []
        
        # Check tenant consistency
        if self.tenant_id and flow.tenant_id and self.tenant_id != flow.tenant_id:
            errors.append("Flow tenant_id doesn't match guardrails tenant_id")
        
        # Validate each task in the flow
        for i, task in enumerate(flow.tasks):
            is_valid, task_errors = self.validate_task_inputs(task)
            if not is_valid:
                for error in task_errors:
                    errors.append(f"Task {i} ({task.id}): {error}")
        
        # Check flow-level constraints
        if len(flow.tasks) == 0:
            errors.append("Flow must contain at least one task")
        
        # Check for circular dependencies (simplified check)
        task_ids = [task.id for task in flow.tasks]
        if len(task_ids) != len(set(task_ids)):
            errors.append("Flow contains duplicate task IDs")
        
        return len(errors) == 0, errors
    
    def enforce_retry_policy(self, task: Task, attempt_count: int) -> bool:
        """
        Enforce retry policy for a task.
        
        Args:
            task (Task): Task being retried
            attempt_count (int): Current attempt count (1-based)
            
        Returns:
            bool: True if retry should be allowed, False otherwise
        """
        # Check task-level retry limit
        if attempt_count > task.retries:
            return False
        
        # Check global retry limit
        if attempt_count > self.max_retries:
            return False
        
        # Check tenant-specific retry limits (if implemented)
        if self.tenant_id and task.tenant_id != self.tenant_id:
            return False
        
        return True
    
    def enforce_timeout_policy(self, task: Task, start_time: datetime) -> bool:
        """
        Enforce timeout policy for a task.
        
        Args:
            task (Task): Task being executed
            start_time (datetime): When the task started execution
            
        Returns:
            bool: True if task should continue, False if timeout exceeded
        """
        if not task.timeout:
            return True
        
        elapsed = datetime.utcnow() - start_time
        return elapsed < task.timeout
    
    def _is_handler_allowed(self, handler: str) -> bool:
        """
        Check if a handler is allowed by the guardrails.
        
        Args:
            handler (str): Handler name to check
            
        Returns:
            bool: True if handler is allowed, False otherwise
        """
        # Check blacklist first
        if handler in self.blocked_handlers:
            return False
        
        # If whitelist is empty, allow all handlers
        if not self.allowed_handlers:
            return True
        
        # Check whitelist
        return handler in self.allowed_handlers
    
    def add_input_validator(self, handler: str, validator: Callable[[Dict[str, Any]], bool]) -> None:
        """
        Add a custom input validator for a specific handler.
        
        Args:
            handler (str): Handler name
            validator (Callable[[Dict[str, Any]], bool]): Validation function
        """
        self.input_validators[handler] = validator
    
    def add_output_validator(self, handler: str, validator: Callable[[Any], bool]) -> None:
        """
        Add a custom output validator for a specific handler.
        
        Args:
            handler (str): Handler name
            validator (Callable[[Any], bool]): Validation function
        """
        self.output_validators[handler] = validator
    
    def remove_input_validator(self, handler: str) -> None:
        """
        Remove a custom input validator for a specific handler.
        
        Args:
            handler (str): Handler name
        """
        self.input_validators.pop(handler, None)
    
    def remove_output_validator(self, handler: str) -> None:
        """
        Remove a custom output validator for a specific handler.
        
        Args:
            handler (str): Handler name
        """
        self.output_validators.pop(handler, None)
    
    def get_security_report(self, flow: Flow) -> Dict[str, Any]:
        """
        Generate a security report for a flow.
        
        Args:
            flow (Flow): Flow to analyze
            
        Returns:
            Dict[str, Any]: Security report
        """
        report = {
            'flow_id': flow.id,
            'tenant_id': flow.tenant_id,
            'total_tasks': len(flow.tasks),
            'security_issues': [],
            'handler_permissions': {},
            'risk_score': 0
        }
        
        risk_score = 0
        
        for task in flow.tasks:
            # Check handler permissions
            is_allowed = self._is_handler_allowed(task.handler)
            report['handler_permissions'][task.handler] = is_allowed
            
            if not is_allowed:
                report['security_issues'].append(f"Blocked handler '{task.handler}' in task {task.id}")
                risk_score += 10
            
            # Check retry limits
            if task.retries > self.max_retries:
                report['security_issues'].append(f"Excessive retries ({task.retries}) in task {task.id}")
                risk_score += 5
            
            # Check timeout limits
            if task.timeout and self.max_timeout and task.timeout > self.max_timeout:
                report['security_issues'].append(f"Excessive timeout ({task.timeout}) in task {task.id}")
                risk_score += 3
        
        report['risk_score'] = min(risk_score, 100)  # Cap at 100
        
        return report
    
    def __repr__(self) -> str:
        """String representation of the guardrails."""
        return (
            f"Guardrails(max_retries={self.max_retries}, "
            f"max_timeout={self.max_timeout}, "
            f"tenant_id='{self.tenant_id}')"
        )

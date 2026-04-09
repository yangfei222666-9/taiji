#!/usr/bin/env python3
"""
Agent State Machine

Explicit state management for agents with clear transitions.

States:
- idle: Agent is created but not running
- running: Agent is actively executing a task
- blocked: Agent is waiting for resources or dependencies
- degraded: Agent is running but with reduced performance
- archived: Agent is no longer active

Transitions:
- idle → running: start()
- running → idle: complete()
- running → blocked: block()
- blocked → running: unblock()
- running → degraded: degrade()
- degraded → running: recover()
- any → archived: archive()
"""

from enum import Enum
from datetime import datetime
from typing import Optional, Dict
import json
from pathlib import Path

class AgentState(Enum):
    """Agent states"""
    IDLE = "idle"
    RUNNING = "running"
    BLOCKED = "blocked"
    DEGRADED = "degraded"
    ARCHIVED = "archived"

class AgentStateMachine:
    """State machine for agent lifecycle management"""
    
    # Valid state transitions
    TRANSITIONS = {
        AgentState.IDLE: [AgentState.RUNNING, AgentState.ARCHIVED],
        AgentState.RUNNING: [AgentState.IDLE, AgentState.BLOCKED, AgentState.DEGRADED, AgentState.ARCHIVED],
        AgentState.BLOCKED: [AgentState.RUNNING, AgentState.ARCHIVED],
        AgentState.DEGRADED: [AgentState.RUNNING, AgentState.ARCHIVED],
        AgentState.ARCHIVED: []  # Terminal state
    }
    
    def __init__(self, agent_id: str, initial_state: AgentState = AgentState.IDLE):
        self.agent_id = agent_id
        self.current_state = initial_state
        self.state_history = [{
            "state": initial_state.value,
            "timestamp": datetime.now().isoformat(),
            "reason": "initialized"
        }]
    
    def transition(self, new_state: AgentState, reason: str = "") -> bool:
        """
        Transition to a new state
        
        Args:
            new_state: Target state
            reason: Reason for transition
            
        Returns:
            True if transition successful, False otherwise
        """
        # Check if transition is valid
        if new_state not in self.TRANSITIONS[self.current_state]:
            print(f"Invalid transition: {self.current_state.value} → {new_state.value}")
            return False
        
        # Record transition
        old_state = self.current_state
        self.current_state = new_state
        
        self.state_history.append({
            "from": old_state.value,
            "to": new_state.value,
            "timestamp": datetime.now().isoformat(),
            "reason": reason
        })
        
        print(f"Agent {self.agent_id}: {old_state.value} → {new_state.value} ({reason})")
        return True
    
    # Convenience methods for common transitions
    
    def start(self, reason: str = "task assigned") -> bool:
        """Start agent (idle → running)"""
        return self.transition(AgentState.RUNNING, reason)
    
    def complete(self, reason: str = "task completed") -> bool:
        """Complete task (running → idle)"""
        return self.transition(AgentState.IDLE, reason)
    
    def block(self, reason: str = "waiting for resources") -> bool:
        """Block agent (running → blocked)"""
        return self.transition(AgentState.BLOCKED, reason)
    
    def unblock(self, reason: str = "resources available") -> bool:
        """Unblock agent (blocked → running)"""
        return self.transition(AgentState.RUNNING, reason)
    
    def degrade(self, reason: str = "performance issues") -> bool:
        """Degrade agent (running → degraded)"""
        return self.transition(AgentState.DEGRADED, reason)
    
    def recover(self, reason: str = "performance restored") -> bool:
        """Recover agent (degraded → running)"""
        return self.transition(AgentState.RUNNING, reason)
    
    def archive(self, reason: str = "no longer needed") -> bool:
        """Archive agent (any → archived)"""
        return self.transition(AgentState.ARCHIVED, reason)
    
    def get_state(self) -> AgentState:
        """Get current state"""
        return self.current_state
    
    def is_active(self) -> bool:
        """Check if agent is active (not archived)"""
        return self.current_state != AgentState.ARCHIVED
    
    def is_available(self) -> bool:
        """Check if agent is available for new tasks"""
        return self.current_state == AgentState.IDLE
    
    def get_history(self) -> list:
        """Get state transition history"""
        return self.state_history
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "agent_id": self.agent_id,
            "current_state": self.current_state.value,
            "state_history": self.state_history
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AgentStateMachine':
        """Create from dictionary"""
        agent_id = data["agent_id"]
        current_state = AgentState(data["current_state"])
        
        machine = cls(agent_id, current_state)
        machine.state_history = data["state_history"]
        
        return machine


# Example usage and tests
if __name__ == "__main__":
    print("=" * 80)
    print("  Agent State Machine - Demo")
    print("=" * 80)
    print()
    
    # Create state machine
    agent = AgentStateMachine("test-agent-001")
    print(f"Initial state: {agent.get_state().value}")
    print()
    
    # Valid transitions
    print("Valid transitions:")
    agent.start("New task assigned")
    agent.complete("Task finished successfully")
    agent.start("Another task")
    agent.degrade("High error rate detected")
    agent.recover("Error rate normalized")
    agent.block("Waiting for API response")
    agent.unblock("API response received")
    agent.complete("Task completed")
    print()
    
    # Invalid transition
    print("Invalid transition:")
    agent.block("Should fail - not running")
    print()
    
    # Archive
    print("Archive:")
    agent.archive("Agent no longer needed")
    print()
    
    # Print history
    print("State history:")
    for entry in agent.get_history():
        print(f"  {entry}")
    print()
    
    # Serialize
    print("Serialization:")
    data = agent.to_dict()
    print(f"  Serialized: {json.dumps(data, indent=2)}")
    
    # Deserialize
    restored = AgentStateMachine.from_dict(data)
    print(f"  Restored state: {restored.get_state().value}")
    print()
    
    print("=" * 80)
    print("  Demo completed!")
    print("=" * 80)

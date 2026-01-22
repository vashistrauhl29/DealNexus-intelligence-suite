"""
Communication Handler for Multi-Agent Discovery System

Manages inter-agent messaging, cross-talk logging, and escalation
when resolution cannot be achieved within the configured turn limit.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Literal

# Resolve paths relative to project root
PROJECT_ROOT = Path(__file__).parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
CROSS_TALK_LOG = LOGS_DIR / "cross_talk.json"
HUMAN_INTERVENTION_FILE = LOGS_DIR / "HUMAN_INTERVENTION_REQUIRED.txt"
GOVERNANCE_RULES_PATH = PROJECT_ROOT / "knowledge_base" / "GOVERNANCE_RULES.md"

# Configuration
MAX_UNRESOLVED_TURNS = 3

# Valid agents in the system
VALID_AGENTS = [
    "outcomes_strategist",
    "technical_pm",
    "legal_counsel",
    "finance_director",
    "document_architect"
]

ResolutionStatus = Literal["resolved", "unresolved", "pending"]


class CommunicationEntry:
    """Represents a single inter-agent communication entry."""

    def __init__(
        self,
        sender: str,
        recipient: str,
        issue_identified: str,
        policy_reference_used: str,
        resolution_status: ResolutionStatus = "pending"
    ):
        self.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self.sender = sender
        self.recipient = recipient
        self.issue_identified = issue_identified
        self.policy_reference_used = policy_reference_used
        self.resolution_status = resolution_status
        self.conversation_id = self._generate_conversation_id()

    def _generate_conversation_id(self) -> str:
        """Generate a unique conversation ID based on participants and timestamp."""
        participants = sorted([self.sender, self.recipient])
        date_part = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"{participants[0]}-{participants[1]}-{date_part}"

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "conversation_id": self.conversation_id,
            "sender": self.sender,
            "recipient": self.recipient,
            "issue_identified": self.issue_identified,
            "policy_reference_used": self.policy_reference_used,
            "resolution_status": self.resolution_status
        }


class CommunicationHandler:
    """
    Handles inter-agent communication logging and escalation.

    Key responsibilities:
    - Log all agent-to-agent messages to cross_talk.json
    - Track unresolved issues per conversation
    - Escalate to human intervention after MAX_UNRESOLVED_TURNS
    """

    def __init__(self):
        self._ensure_logs_directory()
        self._conversation_turn_counts: dict[str, int] = {}

    def _ensure_logs_directory(self) -> None:
        """Ensure the logs directory exists."""
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def _load_cross_talk_log(self) -> list[dict]:
        """Load existing cross-talk log or return empty list."""
        if CROSS_TALK_LOG.exists():
            try:
                with open(CROSS_TALK_LOG, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return []
        return []

    def _save_cross_talk_log(self, entries: list[dict]) -> None:
        """Save entries to cross-talk log."""
        with open(CROSS_TALK_LOG, "w") as f:
            json.dump(entries, f, indent=2)

    def _get_conversation_key(self, sender: str, recipient: str, issue: str) -> str:
        """Generate a key to track conversation turns for a specific issue."""
        participants = sorted([sender, recipient])
        return f"{participants[0]}:{participants[1]}:{issue}"

    def _count_unresolved_turns(self, conversation_key: str) -> int:
        """Count consecutive unresolved turns for a conversation."""
        return self._conversation_turn_counts.get(conversation_key, 0)

    def _write_human_intervention_required(
        self,
        sender: str,
        recipient: str,
        issue_identified: str,
        policy_reference: str,
        turn_count: int
    ) -> None:
        """Write deadlock summary to HUMAN_INTERVENTION_REQUIRED.txt."""
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        summary = f"""
================================================================================
HUMAN INTERVENTION REQUIRED
================================================================================
Timestamp: {timestamp}
Deadlock Detected: Yes
Unresolved Turns: {turn_count}
Maximum Allowed: {MAX_UNRESOLVED_TURNS}

PARTICIPANTS:
  - Agent 1: {sender}
  - Agent 2: {recipient}

ISSUE IDENTIFIED:
  {issue_identified}

POLICY REFERENCE:
  {policy_reference}

RECOMMENDED ACTION:
  Manual review required to resolve the deadlock between agents.
  Reference governance rules at: {GOVERNANCE_RULES_PATH.relative_to(PROJECT_ROOT)}

RESOLUTION OPTIONS:
  1. Override agent decision with human judgment
  2. Modify policy parameters to enable resolution
  3. Escalate to executive stakeholder for strategic direction

================================================================================

"""
        # Append to file (create if doesn't exist)
        with open(HUMAN_INTERVENTION_FILE, "a") as f:
            f.write(summary)

    def send_message(
        self,
        sender: str,
        recipient: str,
        issue_identified: str,
        policy_reference_used: str,
        resolution_status: ResolutionStatus = "pending"
    ) -> dict:
        """
        Send a message from one agent to another and log the communication.

        Args:
            sender: The sending agent identifier
            recipient: The receiving agent identifier
            issue_identified: Description of the issue being communicated
            policy_reference_used: Reference to the governance policy applied
            resolution_status: Current status of the issue resolution

        Returns:
            dict containing the logged entry and any escalation info

        Raises:
            ValueError: If sender or recipient is not a valid agent
        """
        # Validate agents
        if sender not in VALID_AGENTS:
            raise ValueError(f"Invalid sender: {sender}. Must be one of {VALID_AGENTS}")
        if recipient not in VALID_AGENTS:
            raise ValueError(f"Invalid recipient: {recipient}. Must be one of {VALID_AGENTS}")
        if sender == recipient:
            raise ValueError("Sender and recipient cannot be the same agent")

        # Create the communication entry
        entry = CommunicationEntry(
            sender=sender,
            recipient=recipient,
            issue_identified=issue_identified,
            policy_reference_used=policy_reference_used,
            resolution_status=resolution_status
        )

        # Log to cross_talk.json
        entries = self._load_cross_talk_log()
        entries.append(entry.to_dict())
        self._save_cross_talk_log(entries)

        # Track unresolved turns
        conversation_key = self._get_conversation_key(sender, recipient, issue_identified)

        if resolution_status == "unresolved":
            self._conversation_turn_counts[conversation_key] = \
                self._conversation_turn_counts.get(conversation_key, 0) + 1
        elif resolution_status == "resolved":
            self._conversation_turn_counts[conversation_key] = 0

        # Check for escalation
        escalation_triggered = False
        current_turns = self._count_unresolved_turns(conversation_key)

        if current_turns >= MAX_UNRESOLVED_TURNS:
            self._write_human_intervention_required(
                sender=sender,
                recipient=recipient,
                issue_identified=issue_identified,
                policy_reference=policy_reference_used,
                turn_count=current_turns
            )
            escalation_triggered = True

        return {
            "entry": entry.to_dict(),
            "unresolved_turn_count": current_turns,
            "escalation_triggered": escalation_triggered,
            "max_turns_allowed": MAX_UNRESOLVED_TURNS
        }

    def get_conversation_history(
        self,
        sender: Optional[str] = None,
        recipient: Optional[str] = None
    ) -> list[dict]:
        """
        Retrieve conversation history, optionally filtered by participants.

        Args:
            sender: Filter by sender agent (optional)
            recipient: Filter by recipient agent (optional)

        Returns:
            List of communication entries matching the filter
        """
        entries = self._load_cross_talk_log()

        if sender:
            entries = [e for e in entries if e["sender"] == sender]
        if recipient:
            entries = [e for e in entries if e["recipient"] == recipient]

        return entries

    def get_unresolved_issues(self) -> list[dict]:
        """Get all currently unresolved issues from the cross-talk log."""
        entries = self._load_cross_talk_log()
        return [e for e in entries if e["resolution_status"] == "unresolved"]

    def resolve_issue(self, conversation_id: str) -> bool:
        """
        Mark a specific conversation as resolved.

        Args:
            conversation_id: The conversation ID to resolve

        Returns:
            True if the conversation was found and resolved, False otherwise
        """
        entries = self._load_cross_talk_log()
        found = False

        for entry in entries:
            if entry["conversation_id"] == conversation_id:
                entry["resolution_status"] = "resolved"
                found = True

        if found:
            self._save_cross_talk_log(entries)

        return found


# Convenience function for direct usage
def log_agent_communication(
    sender: str,
    recipient: str,
    issue_identified: str,
    policy_reference_used: str,
    resolution_status: ResolutionStatus = "pending"
) -> dict:
    """
    Convenience function to log inter-agent communication.

    Creates a CommunicationHandler instance and logs the message.
    See CommunicationHandler.send_message for full documentation.
    """
    handler = CommunicationHandler()
    return handler.send_message(
        sender=sender,
        recipient=recipient,
        issue_identified=issue_identified,
        policy_reference_used=policy_reference_used,
        resolution_status=resolution_status
    )


if __name__ == "__main__":
    # Example usage demonstrating escalation after 3 unresolved turns
    handler = CommunicationHandler()

    print("=== Communication Handler Demo ===\n")

    # Simulate a custom build cost review scenario from the orchestrator manifest
    for turn in range(1, 5):
        print(f"Turn {turn}:")
        result = handler.send_message(
            sender="technical_pm",
            recipient="finance_director",
            issue_identified="Custom build requirement: Legacy CRM integration",
            policy_reference_used="GOVERNANCE_RULES.md - Section 1: Custom Build Requirement",
            resolution_status="unresolved"
        )
        print(f"  Unresolved turns: {result['unresolved_turn_count']}")
        print(f"  Escalation triggered: {result['escalation_triggered']}")

        if result['escalation_triggered']:
            print(f"\n  >>> ESCALATION: Written to {HUMAN_INTERVENTION_FILE.name}")
            break
        print()

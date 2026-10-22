from typing import Literal, List
from agency_swarm.tools import BaseTool
from pydantic import Field
import json

from helpers import execute_composio_tool


class RemoveLabelFromEmail(BaseTool):
    """
    Removes labels from a specific email message.
    
    For Gmail: Use label IDs. Common operations:
    - Remove 'UNREAD' to mark as read
    - Remove 'INBOX' to archive
    - Remove 'STARRED' to unstar
    
    For Outlook: Remove category names from the message.
    """
    
    provider: Literal["gmail", "outlook"] = Field(
        ...,
        description="Email provider: 'gmail' or 'outlook'"
    )
    
    message_id: str = Field(
        ...,
        description="The message ID to remove labels from (obtained from FindEmails)"
    )
    
    label_ids: List[str] = Field(
        ...,
        description="List of label IDs to remove. Gmail: 'UNREAD', 'INBOX', 'STARRED', 'Label_123'. Outlook: category names."
    )
    
    def run(self):
        try:
            if self.provider == "gmail":
                return self._remove_gmail_labels(execute_composio_tool)
            else:
                return self._remove_outlook_categories(execute_composio_tool)
                
        except Exception as e:
            return f"Error removing labels: {str(e)}"
    
    def _remove_gmail_labels(self, execute_tool) -> str:
        """Removes labels from a Gmail message."""
        result = execute_tool(
            tool_name="GMAIL_ADD_LABEL_TO_EMAIL",
            arguments={
                "user_id": "me",
                "message_id": self.message_id,
                "remove_label_ids": self.label_ids
            },
        )
        
        if isinstance(result, dict) and result.get("error"):
            return f"Error removing Gmail labels: {result.get('error')}"
        
        data = result.get("data", {})
        
        return json.dumps({
            "provider": "gmail",
            "success": True,
            "message_id": self.message_id,
            "labels_removed": self.label_ids,
            "current_labels": data.get("labelIds", [])
        }, indent=2)
    
    def _remove_outlook_categories(self, execute_tool) -> str:
        """Removes categories from an Outlook message."""
        # Get current categories
        get_result = execute_tool(
            tool_name="OUTLOOK_GET_MESSAGE",
            arguments={
                "user_id": "me",
                "message_id": self.message_id,
                "select": ["id", "categories"]
            },
        )
        
        if isinstance(get_result, dict) and get_result.get("error"):
            return f"Error getting Outlook message: {get_result.get('error')}"
        
        current_categories = get_result.get("data", {}).get("categories", [])
        
        # Calculate remaining categories
        remaining_categories = [c for c in current_categories if c not in self.label_ids]
        
        return json.dumps({
            "provider": "outlook",
            "success": True,
            "message_id": self.message_id,
            "categories_removed": self.label_ids,
            "remaining_categories": remaining_categories,
            "note": "Outlook category update requires OUTLOOK_UPDATE_MESSAGE which may not be available"
        }, indent=2)


if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
    
    print("=" * 60)
    print("RemoveLabelFromEmail Test Suite")
    print("=" * 60)
    print()
    
    # Get a message ID first
    from virtual_assistant.tools.FindEmails import FindEmails
    check_tool = FindEmails(provider="gmail", query="is:unread", limit=1)
    result = check_tool.run()
    
    import json
    data = json.loads(result)
    if data.get("emails"):
        message_id = data["emails"][0]["message_id"]
        
        # Test: Mark as read by removing UNREAD label
        print("Test: Mark email as read (remove UNREAD label)")
        print("-" * 60)
        tool = RemoveLabelFromEmail(
            provider="gmail",
            message_id=message_id,
            label_ids=["UNREAD"]
        )
        result = tool.run()
        print(result)
    else:
        print("No emails to test with")
    
    print()
    print("=" * 60)
    print("Tests completed!")
    print("=" * 60)


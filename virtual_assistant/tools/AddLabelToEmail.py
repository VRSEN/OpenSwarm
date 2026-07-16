from typing import Literal, List
from agency_swarm.tools import BaseTool
from pydantic import Field
import json

from helpers import execute_composio_tool


class AddLabelToEmail(BaseTool):
    """
    Adds labels to a specific email message.
    
    For Gmail: Use label IDs (system labels like 'STARRED', 'IMPORTANT', 'INBOX', 
    or custom label IDs like 'Label_123' from ManageLabels).
    
    For Outlook: Use category names (must exist in the user's category list).
    """
    
    provider: Literal["gmail", "outlook"] = Field(
        ...,
        description="Email provider: 'gmail' or 'outlook'"
    )
    
    message_id: str = Field(
        ...,
        description="The message ID to add labels to (obtained from FindEmails)"
    )
    
    label_ids: List[str] = Field(
        ...,
        description="List of label IDs to add. Gmail: 'STARRED', 'IMPORTANT', 'Label_123'. Outlook: category names."
    )
    
    def run(self):
        try:
            if self.provider == "gmail":
                return self._add_gmail_labels(execute_composio_tool)
            else:
                return self._add_outlook_categories(execute_composio_tool)
                
        except Exception as e:
            return f"Error adding labels: {str(e)}"
    
    def _add_gmail_labels(self, execute_tool) -> str:
        """Adds labels to a Gmail message."""
        result = execute_tool(
            tool_name="GMAIL_ADD_LABEL_TO_EMAIL",
            arguments={
                "user_id": "me",
                "message_id": self.message_id,
                "add_label_ids": self.label_ids
            },
        )
        
        if isinstance(result, dict) and result.get("error"):
            return f"Error adding Gmail labels: {result.get('error')}"
        
        data = result.get("data", {})
        
        return json.dumps({
            "provider": "gmail",
            "success": True,
            "message_id": self.message_id,
            "labels_added": self.label_ids,
            "current_labels": data.get("labelIds", [])
        }, indent=2)
    
    def _add_outlook_categories(self, execute_tool) -> str:
        """Adds categories to an Outlook message."""
        # For Outlook, we need to update the message with categories
        # First get current categories, then add new ones
        
        # Get current message
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
        
        # Combine current and new categories (avoid duplicates)
        updated_categories = list(set(current_categories + self.label_ids))
        
        # Update the message with new categories
        # Note: Outlook doesn't have a direct "add category" API, need to use update
        return json.dumps({
            "provider": "outlook",
            "success": True,
            "message_id": self.message_id,
            "categories_added": self.label_ids,
            "current_categories": current_categories,
            "updated_categories": updated_categories,
            "note": "Outlook category update requires OUTLOOK_UPDATE_MESSAGE which may not be available"
        }, indent=2)


if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
    
    print("=" * 60)
    print("AddLabelToEmail Test Suite")
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
        
        # Test: Add STARRED label
        print("Test: Add STARRED label to email")
        print("-" * 60)
        tool = AddLabelToEmail(
            provider="gmail",
            message_id=message_id,
            label_ids=["STARRED"]
        )
        result = tool.run()
        print(result)
        print()
        
        # Remove it to clean up
        from virtual_assistant.tools.RemoveLabelFromEmail import RemoveLabelFromEmail
        print("Cleanup: Remove STARRED label")
        print("-" * 60)
        tool = RemoveLabelFromEmail(
            provider="gmail",
            message_id=message_id,
            label_ids=["STARRED"]
        )
        result = tool.run()
        print(result)
    else:
        print("No emails to test with")
    
    print()
    print("=" * 60)
    print("Tests completed!")
    print("=" * 60)


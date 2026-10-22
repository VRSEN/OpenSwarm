from typing import Literal
from agency_swarm.tools import BaseTool
from pydantic import Field
import json
import re

from helpers import execute_composio_tool


def strip_html(html_content: str) -> str:
    """Converts HTML to plain text by removing tags and decoding entities."""
    if not html_content:
        return ""
    
    # Remove style and script tags with their content
    text = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Replace common block elements with newlines
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</(p|div|tr|li|h[1-6])>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</td>', '\t', text, flags=re.IGNORECASE)
    
    # Remove all remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Decode common HTML entities
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    text = text.replace('&#39;', "'")
    text = text.replace('&apos;', "'")
    
    # Clean up whitespace
    text = re.sub(r'\n\s*\n', '\n\n', text)  # Collapse multiple newlines
    text = re.sub(r'[ \t]+', ' ', text)  # Collapse multiple spaces
    text = '\n'.join(line.strip() for line in text.split('\n'))  # Strip each line
    text = text.strip()
    
    return text


class ReadEmail(BaseTool):
    """
    Reads the full content of a specific email by its message ID.
    
    Use this after FindEmails to fetch the complete email content
    when you need to read the full message body.
    """
    
    provider: Literal["gmail", "outlook"] = Field(
        ...,
        description="Email provider: 'gmail' or 'outlook'"
    )
    
    message_id: str = Field(
        ...,
        description="The message ID to fetch (obtained from FindEmails)"
    )
    
    body_format: Literal["text", "html"] = Field(
        default="text",
        description="Format for the email body: 'text' (plain text, default) or 'html' (raw HTML). Keep the default to save tokens."
    )
    
    def run(self):
        try:
            if self.provider == "gmail":
                return self._read_gmail_message(execute_composio_tool)
            else:
                return self._read_outlook_message(execute_composio_tool)
                
        except Exception as e:
            return f"Error reading email: {str(e)}"
    
    def _read_gmail_message(self, execute_tool) -> str:
        """Reads a Gmail message by ID."""
        result = execute_tool(
            tool_name="GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID",
            arguments={
                "user_id": "me",
                "message_id": self.message_id,
                "format": "full"
            },
        )
        
        if isinstance(result, dict) and result.get("error"):
            return f"Error reading Gmail message: {result.get('error')}"

        data = result.get("data", {})

        if not data:
            return f"Message not found: {self.message_id}"

        if self.body_format == "text":
            # Use preview body (clean plain text) if available, fallback to stripping HTML
            preview = data.get("preview", {})
            body_content = preview.get("body", "")
            if not body_content:
                body_content = strip_html(data.get("messageText", ""))
        else:
            body_content = data.get("messageText", "")
        
        return json.dumps({
            "provider": "gmail",
            "message_id": data.get("messageId"),
            "thread_id": data.get("threadId"),
            "subject": data.get("subject", "(No subject)"),
            "from": data.get("sender", "Unknown"),
            "to": data.get("to", ""),
            "received_at": data.get("messageTimestamp"),
            "labels": data.get("labelIds", []),
            "body": body_content,
            "has_attachments": len(data.get("attachmentList", [])) > 0,
            "attachments": [
                {"filename": att.get("filename"), "size": att.get("size")}
                for att in data.get("attachmentList", [])
            ]
        }, indent=2)
    
    def _read_outlook_message(self, execute_tool) -> str:
        """Reads an Outlook message by ID."""
        result = execute_tool(
            tool_name="OUTLOOK_GET_MESSAGE",
            arguments={
                "user_id": "me",
                "message_id": self.message_id,
                "select": [
                    "id", "subject", "from", "toRecipients", "ccRecipients",
                    "receivedDateTime", "body", "hasAttachments", "webLink",
                    "isRead", "importance", "conversationId"
                ]
            },
        )
        
        if isinstance(result, dict) and result.get("error"):
            return f"Error reading Outlook message: {result.get('error')}"

        data = result.get("data", {})

        if not data:
            return f"Message not found: {self.message_id}"

        from_info = data.get("from", {}).get("emailAddress", {})
        from_str = f"{from_info.get('name', '')} <{from_info.get('address', 'Unknown')}>"

        to_recipients = []
        for recipient in data.get("toRecipients", []):
            email_addr = recipient.get("emailAddress", {})
            to_recipients.append(f"{email_addr.get('name', '')} <{email_addr.get('address', '')}>")
        
        cc_recipients = []
        for recipient in data.get("ccRecipients", []):
            email_addr = recipient.get("emailAddress", {})
            cc_recipients.append(f"{email_addr.get('name', '')} <{email_addr.get('address', '')}>")
        
        body_data = data.get("body", {})
        body_content = body_data.get("content", "")
        body_type = body_data.get("contentType", "text")

        if self.body_format == "text" and body_type.lower() == "html" and body_content:
            body_content = strip_html(body_content)

        return json.dumps({
            "provider": "outlook",
            "message_id": data.get("id"),
            "conversation_id": data.get("conversationId"),
            "subject": data.get("subject", "(No subject)"),
            "from": from_str,
            "to": to_recipients,
            "cc": cc_recipients,
            "received_at": data.get("receivedDateTime"),
            "is_read": data.get("isRead"),
            "importance": data.get("importance"),
            "body": body_content,
            "has_attachments": data.get("hasAttachments", False),
            "web_link": data.get("webLink", "")
        }, indent=2)


if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
    
    print("=" * 60)
    print("ReadEmail Test Suite")
    print("=" * 60)
    print()
    
    # Get a message ID from FindEmails
    from virtual_assistant.tools.FindEmails import FindEmails
    check_tool = FindEmails(provider="gmail", query="is:unread", limit=1)
    result = check_tool.run()
    
    import json
    try:
        data = json.loads(result)
        if data.get("emails"):
            message_id = data["emails"][0]["message_id"]
            
            # Test 1: Read Gmail message as plain text (default)
            print("Test 1: Gmail - Plain text (default)")
            print("-" * 60)
            tool = ReadEmail(provider="gmail", message_id=message_id, body_format="text")
            result = tool.run()
            result_data = json.loads(result)
            if result_data.get("body") and len(result_data["body"]) > 500:
                result_data["body"] = result_data["body"][:500] + "... [truncated]"
            print(json.dumps(result_data, indent=2))
            print()
            
            # Test 2: Read Gmail message as HTML
            print("Test 2: Gmail - HTML format")
            print("-" * 60)
            tool = ReadEmail(provider="gmail", message_id=message_id, body_format="html")
            result = tool.run()
            result_data = json.loads(result)
            if result_data.get("body") and len(result_data["body"]) > 300:
                result_data["body"] = result_data["body"][:300] + "... [truncated]"
            print(json.dumps(result_data, indent=2))
            print()
        else:
            print("No unread emails to test with")
    except json.JSONDecodeError:
        print(f"Error parsing result: {result}")
    
    # Test 3: Read an Outlook message
    print("Test 3: Outlook - Plain text")
    print("-" * 60)
    check_tool = FindEmails(provider="outlook", is_read=False, limit=1)
    result = check_tool.run()
    try:
        data = json.loads(result)
        if data.get("emails"):
            message_id = data["emails"][0]["message_id"]
            tool = ReadEmail(provider="outlook", message_id=message_id, body_format="text")
            result = tool.run()
            print(result[:1500])
        else:
            print("No unread Outlook emails to test with")
    except json.JSONDecodeError:
        print(f"Result: {result}")
    print()
    
    print("=" * 60)
    print("All tests completed!")
    print("=" * 60)


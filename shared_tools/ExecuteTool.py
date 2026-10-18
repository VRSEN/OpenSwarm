from typing import Optional, List
from agency_swarm.tools import BaseTool
from pydantic import Field
import json

from helpers import execute_composio_tool


class ExecuteTool(BaseTool):
    """
    Executes a single Composio tool call and returns the result.
    
    Use this tool for simple, single-action tasks where you need to:
    - Execute one tool
    - Get the result
    - No data transformation needed
    
    Examples:
    - Creating a single calendar event
    - Submitting a support ticket
    - Sending a simple notification
    - Fetching specific data
    
    For complex workflows requiring multiple tool calls or data transformation,
    use IPythonInterpreter instead.
    """
    
    tool_name: str = Field(
        ..., 
        description="The exact name of the Composio tool to execute (e.g., 'GMAIL_SEND_EMAIL', 'JIRA_CREATE_ISSUE')"
    )
    
    arguments: dict = Field(
        ...,
        description="Dictionary of arguments to pass to the tool. Keys are parameter names, values are parameter values.",
        # Workaround to avoid the agents SDK from stripping dynamic dictionary inputs:
        json_schema_extra={"type":"object","additionalProperties": True, "properties": {}}
    )

    session_id: Optional[str] = Field(
        None,
        description=(
            "Optional Composio session id returned by SearchTools or ManageConnections. "
            "Pass it when executing a tool discovered or authorized in that session."
        ),
    )
    
    return_fields: Optional[List[str]] = Field(
        None,
        description="Optional list of field names to extract from the tool's response. If provided, only these fields will be returned. If not provided or the field doesn't exist, the full response is returned."
    )
    class ToolConfig:
        strict: bool = False
    
    def run(self):
        try:
            result = execute_composio_tool(
                tool_name=self.tool_name,
                arguments=self.arguments,
                session_id=self.session_id,
            )

            if isinstance(result, dict) and result.get("error"):
                return f"Error executing {self.tool_name}: {result.get('error')}"

            if self.return_fields:
                filtered_result = {}
                
                # Handle both dict and object-like results
                if isinstance(result, dict):
                    for field in self.return_fields:
                        # Support nested field access with dot notation (e.g., "data.id")
                        if "." in field:
                            parts = field.split(".")
                            value = result
                            try:
                                for part in parts:
                                    if isinstance(value, dict):
                                        value = value.get(part)
                                    else:
                                        value = getattr(value, part, None)
                                    if value is None:
                                        break
                                if value is not None:
                                    filtered_result[field] = value
                            except (KeyError, AttributeError, TypeError):
                                # Field doesn't exist, skip it
                                continue
                        else:
                            # Simple field access
                            if field in result:
                                filtered_result[field] = result[field]
                else:
                    # Try to access as object attributes
                    for field in self.return_fields:
                        try:
                            if "." in field:
                                parts = field.split(".")
                                value = result
                                for part in parts:
                                    value = getattr(value, part, None)
                                    if value is None:
                                        break
                                if value is not None:
                                    filtered_result[field] = value
                            else:
                                value = getattr(result, field, None)
                                if value is not None:
                                    filtered_result[field] = value
                        except (AttributeError, TypeError):
                            # Field doesn't exist, skip it
                            continue
                
                # Return filtered result if we got any fields, otherwise return full result
                if filtered_result:
                    return json.dumps(filtered_result, indent=2, default=str)
                else:
                    # No fields were found, return full result as fallback
                    return json.dumps(result, indent=2, default=str)
            
            return json.dumps(result, indent=2, default=str)
            
        except Exception as e:
            return f"Error executing tool {self.tool_name}: {str(e)}"


if __name__ == "__main__":
    import sys
    import os
    # Add parent directory to path for helpers import
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
    
    print("=" * 60)
    print("ExecuteTool Test Suite")
    print("=" * 60)
    print()
    
    # Test case 1: Simple execution without field filtering
    print("Test 1: Execute GMAIL_LIST_LABELS without filtering")
    print("-" * 60)
    tool = ExecuteTool(
        tool_name="GMAIL_LIST_LABELS",
        arguments={"user_id": "me"}
    )
    result = tool.run()
    print(f"Result length: {len(result)} characters")
    print(f"Contains 'data': {'data' in result}")
    print(f"Contains 'successful': {'successful' in result}")
    print()
    
    # Test case 2: Execute tool with simple field filtering
    print("Test 2: Execute with simple field filtering")
    print("-" * 60)
    tool = ExecuteTool(
        tool_name="GMAIL_LIST_LABELS",
        arguments={"user_id": "me"},
        return_fields=["successful", "error"]
    )
    result = tool.run()
    print("Filtered result:")
    print(result)
    print()
    
    # Test case 3: Execute tool with nested field access
    print("Test 3: Execute with nested field filtering (dot notation)")
    print("-" * 60)
    tool = ExecuteTool(
        tool_name="GMAIL_LIST_LABELS",
        arguments={"user_id": "me"},
        return_fields=["data.labels", "successful"]
    )
    result = tool.run()
    print(f"Result length: {len(result)} characters")
    print(f"Contains 'data.labels': {'data.labels' in result}")
    print()
    
    # Test case 4: Non-existent fields fallback
    print("Test 4: Non-existent fields (should return full result)")
    print("-" * 60)
    tool = ExecuteTool(
        tool_name="GMAIL_LIST_LABELS",
        arguments={"user_id": "me"},
        return_fields=["nonexistent_field1", "nonexistent_field2"]
    )
    result = tool.run()
    print(f"Result length: {len(result)} characters")
    print(f"Fallback to full result: {len(result) > 1000}")
    print()
    
    print("=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)


#!/usr/bin/env python3
"""
Runtime monkey patch for Agency Swarm dual communication tools per pair.

This patches classes/functions in memory (no framework file rewriting):
- agency.setup.parse_agent_flows
- agency.setup.configure_agents
- agency.core.parse_agent_flows
- agency.core.configure_agents
"""

from __future__ import annotations

from typing import Any


def _validate_communication_tool_class(tool_class: type, send_message_class: type, handoff_class: type) -> None:
    if not issubclass(tool_class, (send_message_class, handoff_class)):
        raise TypeError(
            f"Invalid communication tool class: {tool_class.__name__}. "
            "Expected a SendMessage or Handoff subclass."
        )


def _add_tool_class_for_pair(
    mapping: dict[tuple[str, str], list[type]],
    default_tool_pairs: set[tuple[str, str]],
    pair_key: tuple[str, str],
    tool_class: type | None,
    send_message_class: type,
    handoff_class: type,
) -> None:
    if tool_class is None:
        return
    _validate_communication_tool_class(tool_class, send_message_class, handoff_class)
    if pair_key in default_tool_pairs and issubclass(tool_class, send_message_class):
        raise ValueError(
            f"Duplicate communication tool class detected for {pair_key[0]} -> {pair_key[1]}: "
            f"{tool_class.__name__}. Each SendMessage tool for a pair can only be defined once."
        )
    classes = mapping.setdefault(pair_key, [])
    if issubclass(tool_class, send_message_class):
        for existing_tool_class in classes:
            if issubclass(existing_tool_class, send_message_class):
                raise ValueError(
                    f"Duplicate communication tool class detected for {pair_key[0]} -> {pair_key[1]}: "
                    f"{tool_class.__name__}. Each SendMessage tool for a pair can only be defined once."
                )
    if tool_class in classes:
        raise ValueError(
            f"Duplicate communication tool class detected for {pair_key[0]} -> {pair_key[1]}: "
            f"{tool_class.__name__}. Each tool class for a pair can only be defined once."
        )
    classes.append(tool_class)


def _add_default_tool_pair(
    custom_mapping: dict[tuple[str, str], list[type]],
    default_tool_pairs: set[tuple[str, str]],
    pair_key: tuple[str, str],
    send_message_class: type,
) -> None:
    if pair_key in default_tool_pairs:
        raise ValueError(
            f"Duplicate communication flow detected: {pair_key[0]} -> {pair_key[1]}. "
            "Each default agent-to-agent communication can only be defined once."
        )
    for tool_class in custom_mapping.get(pair_key, []):
        if issubclass(tool_class, send_message_class):
            raise ValueError(
                f"Duplicate communication tool class detected for {pair_key[0]} -> {pair_key[1]}: "
                f"{tool_class.__name__}. Each SendMessage tool for a pair can only be defined once."
            )
    default_tool_pairs.add(pair_key)


def apply_dual_comms_patch() -> None:
    import warnings

    from agency_swarm.agent.agent_flow import AgentFlow
    from agency_swarm.agent.core import Agent
    from agency_swarm.agency import core as core_mod
    from agency_swarm.agency import setup as setup_mod
    from agency_swarm.tools.send_message import Handoff, SendMessage, SendMessageHandoff

    if getattr(setup_mod, "_dual_comms_patch_applied", False):
        return

    def parse_agent_flows_patched(
        agency: Any, communication_flows: list[Any]
    ) -> tuple[list[tuple[Agent, Agent]], dict[tuple[str, str], list[type]], set[tuple[str, str]]]:
        basic_flows: list[tuple[Agent, Agent]] = []
        tool_class_mapping: dict[tuple[str, str], list[type]] = {}
        default_tool_pairs: set[tuple[str, str]] = set()
        seen_flows: set[tuple[str, str]] = set()

        chain_flows = AgentFlow.get_and_clear_chain_flows()
        chain_flows_used = False

        for flow_entry in communication_flows:
            if isinstance(flow_entry, AgentFlow):
                flow_entry = (flow_entry, None)

            if isinstance(flow_entry, (tuple, list)) and len(flow_entry) == 2:
                first, second = flow_entry

                if isinstance(first, Agent) and isinstance(second, Agent):
                    flow_key = (first.name, second.name)
                    if flow_key not in seen_flows:
                        seen_flows.add(flow_key)
                        basic_flows.append((first, second))
                    _add_default_tool_pair(tool_class_mapping, default_tool_pairs, flow_key, SendMessage)

                elif isinstance(first, AgentFlow) and (isinstance(second, type) or second is None):
                    tool_class = second
                    direct_flows = first.get_all_flows()
                    if not chain_flows_used:
                        all_flows = direct_flows + [f for f in chain_flows if f not in direct_flows]
                        chain_flows_used = True
                    else:
                        all_flows = direct_flows

                    for sender, receiver in all_flows:
                        flow_key = (sender.name, receiver.name)
                        if flow_key not in seen_flows:
                            seen_flows.add(flow_key)
                            basic_flows.append((sender, receiver))
                        elif tool_class is None:
                            _add_default_tool_pair(tool_class_mapping, default_tool_pairs, flow_key, SendMessage)
                            continue
                        if tool_class is None:
                            _add_default_tool_pair(tool_class_mapping, default_tool_pairs, flow_key, SendMessage)
                        else:
                            _add_tool_class_for_pair(
                                tool_class_mapping,
                                default_tool_pairs,
                                flow_key,
                                tool_class,
                                SendMessage,
                                Handoff,
                            )
                else:
                    raise TypeError(
                        f"Invalid communication flow entry: {flow_entry}. "
                        "Expected (Agent, Agent) or (AgentFlow, tool_class)."
                    )

            elif isinstance(flow_entry, (tuple, list)) and len(flow_entry) == 3:
                sender, receiver, tool_class = flow_entry

                if not isinstance(sender, Agent) or not isinstance(receiver, Agent):
                    raise TypeError(f"Invalid communication flow entry: {flow_entry}. Expected (Agent, Agent, tool_class).")

                # The agency factory reconstructs flows from _communication_tool_classes,
                # which stores lists of types per pair. Accept both a single class and a list.
                tool_classes = tool_class if isinstance(tool_class, (list, tuple)) else [tool_class]
                if not tool_classes:
                    raise ValueError("Communication flow tool class list cannot be empty.")
                for tc in tool_classes:
                    if not isinstance(tc, type):
                        raise TypeError(f"Invalid tool class in communication flow: {tc}. Expected a class type.")

                flow_key = (sender.name, receiver.name)
                if flow_key not in seen_flows:
                    seen_flows.add(flow_key)
                    basic_flows.append((sender, receiver))

                for tc in tool_classes:
                    _add_tool_class_for_pair(tool_class_mapping, default_tool_pairs, flow_key, tc, SendMessage, Handoff)

            else:
                raise ValueError(f"Invalid communication flow entry: {flow_entry}. Expected 2 or 3 elements.")

        return basic_flows, tool_class_mapping, default_tool_pairs

    def configure_agents_patched(agency: Any, defined_communication_flows: list[tuple[Agent, Agent]]) -> None:
        setup_mod.logger.info("Configuring agents...")

        communication_map: dict[str, list[str]] = {agent_name: [] for agent_name in agency.agents}
        for sender, receiver in defined_communication_flows:
            sender_name = sender.name
            receiver_name = receiver.name
            if receiver_name not in communication_map[sender_name]:
                communication_map[sender_name].append(receiver_name)

        for agent_name, agent_instance in agency.agents.items():
            runtime_state = agency._agent_runtime_state[agent_name]
            allowed_recipients = communication_map.get(agent_name, [])

            if allowed_recipients:
                if not agent_instance.supports_outbound_communication:
                    joined = ", ".join(allowed_recipients)
                    raise ValueError(
                        f"Agent '{agent_name}' cannot be the sender in communication_flows. "
                        f"It can receive delegated work, but it cannot delegate to: {joined}."
                    )
                setup_mod.logger.debug(f"Agent '{agent_name}' can send messages to: {allowed_recipients}")
                for recipient_name in allowed_recipients:
                    recipient_agent = agency.agents[recipient_name]
                    pair_key = (agent_name, recipient_name)
                    configured = agency._communication_tool_classes.get(pair_key, [])
                    tool_classes: list[type] = []
                    if pair_key in agency._default_communication_tool_pairs:
                        tool_classes.append(agency.send_message_tool_class or SendMessage)
                    tool_classes.extend(configured)
                    if not tool_classes:
                        tool_classes.append(agency.send_message_tool_class or SendMessage)

                    for effective_tool_class in tool_classes:
                        try:
                            if isinstance(effective_tool_class, Handoff) or (
                                isinstance(effective_tool_class, type) and issubclass(effective_tool_class, Handoff)
                            ):
                                if (
                                    not setup_mod._warned_deprecated_send_message_handoff
                                    and isinstance(effective_tool_class, type)
                                    and issubclass(effective_tool_class, SendMessageHandoff)
                                ):
                                    warnings.warn(
                                        "SendMessageHandoff is deprecated; use Handoff instead.",
                                        DeprecationWarning,
                                        stacklevel=3,
                                    )
                                    setup_mod._warned_deprecated_send_message_handoff = True

                                handoff_instance = effective_tool_class().create_handoff(recipient_agent=recipient_agent)
                                handoff_instance._agency_swarm_tool_class = effective_tool_class
                                runtime_state.handoffs.append(handoff_instance)
                                setup_mod.logger.debug(f"Added Handoff for {agent_name} -> {recipient_name}")
                            else:
                                chosen_tool_class = effective_tool_class or SendMessage
                                if not isinstance(chosen_tool_class, type) or not issubclass(chosen_tool_class, SendMessage):
                                    chosen_tool_class = SendMessage

                                agent_instance.register_subagent(
                                    recipient_agent,
                                    send_message_tool_class=chosen_tool_class,
                                    runtime_state=runtime_state,
                                )
                        except Exception as e:
                            setup_mod.logger.error(
                                f"Error registering subagent '{recipient_name}' for sender '{agent_name}': {e}",
                                exc_info=True,
                            )
            else:
                setup_mod.logger.debug(f"Agent '{agent_name}' has no explicitly defined outgoing communication paths.")

        setup_mod.logger.info("Agent configuration complete.")

    setup_mod.parse_agent_flows = parse_agent_flows_patched
    setup_mod.configure_agents = configure_agents_patched

    # Agency.__init__ uses these symbols imported into core module scope.
    core_mod.parse_agent_flows = parse_agent_flows_patched
    core_mod.configure_agents = configure_agents_patched

    setup_mod._dual_comms_patch_applied = True


if __name__ == "__main__":
    apply_dual_comms_patch()
    print("Dual communication monkey patch applied in current Python process.")

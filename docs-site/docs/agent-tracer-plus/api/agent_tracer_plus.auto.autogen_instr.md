# Module: `agent_tracer_plus.auto.autogen_instr`

Auto-instrumentation for AutoGen.

Patches ConversableAgent.generate_reply and initiate_chat
for automatic trace span creation.

## Function `patch_autogen()`
Patch AutoGen ConversableAgent for auto-tracing.


# Conversation quality and plan continuity

This update builds on `b9bbcc6869f07d9afd7f52ac1cd0331c6d6d6eed` without replacing the Python simulation or shared inference scheduler.

## Grounded conversations

`communication.py` offers optional reasons to speak based on nearby people, visible unfinished projects, pending offers, remembered news, rivalry, locally inspectable shortages and actual visitors from another settlement. It does not author dialogue or force an encounter. Per-pair cooldowns reduce repeated approaches. The LLM may decline or choose its own grounded reason.

Requests retrieve memories using the latest turns and partner context. They include the agent's own plans, commitments, relevant sourced knowledge, reflections, local projects, known relationships, own shipment and accessible community information. A partner's private inventory/goals are never copied into the context. Reports remain uncertain. Context fitting still bounds the complete system/user messages; a small character budget can expose fewer action schemas and memories.

The response envelope accepts:

```json
{
  "goal": "Finish the farm before making another commitment",
  "plan": [],
  "plan_policy": "keep",
  "conversation": {
    "target": "a3",
    "topic": "farm project",
    "message": "Could you help finish the farm beside us?"
  }
}
```

A conversation response uses `speech`, optionally `stance`, `end_conversation` and at most two `dialogue_actions`. Supported immediate dialogue actions are offer/accept/reject, help, teach, share, commit_work and conflict_response. They must involve this partner and pass the ordinary engine preconditions. Prose alone never transfers goods or fulfills a promise. Outcomes and failures go into the conversation and both participants' memories, and are supplied on subsequent turns.

Trust assessment is bounded to one stance update per participant per conversation. Actual trade/help/work consequences have separate engine effects. Three repeated normalized statements from the same participant end an unproductive loop; otherwise the configured NPC turn limit still applies. This is a modest guard against repetition, not semantic dialogue evaluation.

## Continuous plans and commitments

An active plan is preserved by default during a new reflection or reply. `plan_policy: "append"` adds work after its remaining steps (up to 16); `"replace"` requires a nonempty concrete `revision_reason`, logged as a revision event. Existing step start times survive append operations. The active plan's goal remains stable even if a conversation introduces another personal goal. Empty plans do not cancel work.

`commit_work` records a voluntary commitment to contribute to a visible unfinished home project. Once the agent's existing plan and urgent survival needs permit, fallback execution walks to that site and contributes through the normal work action. Actual contributed work is tracked; closure distinguishes fulfilled, superseded and expired commitments. Fulfillment affects cooperation/trust and memory. It does not promise a whole building will be completed alone. Work commitments expire after 300 ticks and are currently limited to home-settlement projects.

Trade offers now maintain one current commitment record for each party. Acceptance, rejection and expiration update both records. An unaccepted offer is never a binding promise or resource transfer.

## Scheduling and cross-settlement contact

Queued requests refresh their private snapshots before dispatch. New heard dialogue invalidates an older in-flight reflection. One active conversation per participant prevents overlapping turns; an NPC addressing the player enters a replyable waiting state. Disabling inference explicitly closes pending replies with an error instead of leaving a permanent thinking state.

Couriers briefly stop after a real destination exchange, making local contact possible, and remain nearby during an active conversation while survival remains authoritative. The owned cargo still travels in the same shipment and returns normally. No new goods, remote exchanges or forced diplomacy are introduced. Construction routines also now reach the actual site rather than incrementing progress remotely from a store.

## Evidence and limits

Seventeen added regressions cover autonomous project conversations, persistent work commitments, multi-turn negotiated exchanges/conservation, preserved/revised plans, retrieval/privacy, overlap prevention, stale contexts, expiry, repetition/trust bounds, courier pauses and player-initiated/agent-initiated dialogue. Test speech comes from explicitly scripted providers. It verifies the pipeline and effects, **not real model quality**.

No live Ollama was available. Whether a particular local model produces interesting, grounded speech or consistently follows these optional fields still needs genuine inference and playtesting. Opportunity ranking is heuristic, stances remain model assessments, work pledges have simple deadlines, and this is not a general contract or unrestricted diplomatic system. All previous broader architecture limits still apply.

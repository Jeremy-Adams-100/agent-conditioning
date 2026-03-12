<restored-session id="{session_id}" parent="{parent_id}" depth="{depth}" timestamp="{timestamp}">

{summary_xml}

[SESSION HISTORY]

You have {session_count} previous sessions stored and searchable.
Your lineage is {depth} compactions deep from the original conversation.

Tool available: search_sessions(query, limit)
  - Searches all past session summaries by content
  - Returns matching summaries ranked by relevance
  - Use when the current summary doesn't contain context you need
  - Use when the user references something not in your current state

[CONTINUITY INSTRUCTIONS]

1. You are resuming work. Read the summary above carefully.
2. Your current framework stage is: {current_stage}
3. Your pending gates are listed in the summary. Pick up where you
   left off — check which gates remain unmet and continue from there.
4. Do NOT re-explore or re-plan work that the summary shows as
   completed, unless you find evidence it was done incorrectly.
5. Do NOT announce the compaction to the user. From their perspective,
   the conversation is continuous. If they ask, you can explain.
6. Emit a checkpoint as your first action to re-establish state.

</restored-session>

/**
 * Summary: React UI component 'Prompt Templates'.
 *
 * What it does: Renders the 'Prompt Templates' dashboard interface, manages localized state, and handles user actions.
 *
 * How it fits in: Layout component rendered by parent dashboard containers; interacts with hooks and contexts from 'dashboard/src/app'.
 */



export type PromptCategory = "general" | "skill";

export type TemplateOption = {
  id: string;
  label: string;
  category: PromptCategory;
  description: string;
  starter: string;
};

export const TEMPLATES: TemplateOption[] = [
  {
    id: "general-blank",
    label: "Blank Prompt",
    category: "general",
    description: "Start from scratch with no template",
    starter: "",
  },
  {
    id: "general-task",
    label: "Structured Task",
    category: "general",
    description: "Goal, scope, context, acceptance criteria, and stop condition",
    starter: `Goal: [What should be true when this task is done]\n\nScope:\n- Files: [specific files or directories to touch]\n- Do NOT modify: [files that must remain unchanged]\n\nContext:\n- This module handles [describe what it does]\n- It depends on [list dependencies or related modules]\n- Current behavior: [what happens now]\n- Desired behavior: [what should happen after]\n\nAcceptance criteria:\n- [ ] [Specific, verifiable condition 1]\n- [ ] [Specific, verifiable condition 2]\n- [ ] All existing tests pass\n- [ ] No lint or type errors introduced\n\nStop condition: Stop when all acceptance criteria are met and tests pass. Do not refactor unrelated code.`,
  },
  {
    id: "general-review",
    label: "Code Review",
    category: "general",
    description: "Five-element review: role, scope, focus, format, severity",
    starter: `Act as a senior engineer reviewing for production readiness.\n\nScope: Review the recent changes in [target files or directory].\n\nFocus areas (in priority order):\n1. Security: injection, auth bypass, data exposure, input validation\n2. Correctness: logic errors, edge cases, race conditions, null handling\n3. Performance: N+1 queries, unnecessary allocations, missing indexes\n4. Error handling: uncaught exceptions, silent failures, missing retries\n5. Maintainability: unclear naming, missing types, excessive complexity\n\nOutput format: Numbered list, each item including:\n- [file:line] severity (Critical/High/Medium/Low)\n- Issue description (one sentence)\n- Fix suggestion (concrete code or approach)\n\nRules:\n- Only report actual issues, not style preferences\n- If no issues found in a category, skip it\n- Critical and High issues must include a code fix\n- Do not suggest changes that alter public API without flagging it`,
  },
  {
    id: "general-refactor",
    label: "Refactor",
    category: "general",
    description: "Restructure code with explicit constraints and verification",
    starter: `Goal: Refactor [target module/function] to reduce complexity while preserving all existing behavior.\n\nScope:\n- Files to modify: [list specific files]\n- Do NOT change: public API signatures, test files, unrelated modules\n\nRefactoring targets:\n- Extract [describe what to extract] into [where]\n- Reduce cyclomatic complexity of [function] from ~[N] to under 10\n- Eliminate duplication between [A] and [B]\n- Improve naming: [old_name] -> [new_name] (explain why)\n\nConstraints:\n- Zero behavior change — all existing tests must pass without modification\n- No new dependencies\n- Each commit should be a single logical change\n- If a change is risky, add a test BEFORE making it\n\nVerification:\n- Run the full test suite after each change\n- Confirm no type errors or lint warnings\n- Diff should be reviewable in under 5 minutes`,
  },
  {
    id: "skill-feature",
    label: "New Feature",
    category: "skill",
    description: "Implement a feature with spec, acceptance criteria, and stop condition",
    starter: `Feature: [Name]\n\nDescription: [One paragraph explaining what this feature does and why it exists]\n\nUser story: As a [role], I want to [action] so that [benefit].\n\nAcceptance criteria:\n- [ ] [Specific behavior 1 — describe input and expected output]\n- [ ] [Specific behavior 2]\n- [ ] [Edge case handling — what happens with invalid input]\n- [ ] Unit tests cover all new public functions\n- [ ] No regression in existing tests\n\nTechnical approach:\n- Add [what] to [where]\n- Wire it into [existing system/route/handler]\n- Follow the pattern used in [reference file] for consistency\n\nOut of scope:\n- Do NOT modify [unrelated module]\n- Do NOT add new dependencies without flagging\n- Do NOT change database schema\n\nStop condition: Feature works as described, tests pass, lint clean. Do not add extra functionality beyond what is specified.`,
  },
  {
    id: "skill-fix",
    label: "Bug Fix",
    category: "skill",
    description: "Diagnose root cause, fix, add regression test, verify",
    starter: `Bug: [Title]\n\nSymptom: [What the user sees — error message, wrong output, crash]\n\nExpected behavior: [What should happen instead]\n\nReproduction:\n1. [Step 1]\n2. [Step 2]\n3. [Observe: describe the failure]\n\nEnvironment: [OS, runtime version, relevant config]\n\nSuspected area: [file or module, if known]\n\nInstructions:\n1. Reproduce the bug first — confirm you can trigger it\n2. Identify the root cause (not just the symptom)\n3. Write a failing test that captures the bug\n4. Implement the minimal fix\n5. Verify the test now passes\n6. Run the full test suite to confirm no regressions\n7. If the fix touches error handling, verify adjacent error paths\n\nConstraints:\n- Minimal change — do not refactor surrounding code\n- If the fix requires a design change, describe it and stop for approval\n- Add a comment explaining WHY the fix works if it is non-obvious`,
  },
  {
    id: "skill-test",
    label: "Add Tests",
    category: "skill",
    description: "Systematic test coverage with edge cases and isolation",
    starter: `Target: [module or file to test]\n\nCurrent coverage: [X% or "none"]\nTarget coverage: [Y% or "all public functions"]\n\nTest categories to cover:\n1. Happy path: normal inputs produce expected outputs\n2. Edge cases: empty input, null/undefined, boundary values, max length\n3. Error paths: invalid input, network failures, timeouts, permission denied\n4. Integration: verify interaction with [dependency] works correctly\n\nTest requirements:\n- Use [existing test framework — jest/pytest/vitest/etc.]\n- Follow the pattern in [reference test file]\n- Each test has a descriptive name explaining WHAT it verifies\n- Tests are isolated — no shared mutable state between tests\n- Mock external dependencies, do not mock the unit under test\n- No flaky tests — avoid timing-dependent assertions\n\nPriority order:\n1. Untested public functions (highest risk)\n2. Error handling paths\n3. Edge cases for complex logic\n4. Integration boundaries\n\nStop condition: All specified categories covered, all tests pass, no flaky tests.`,
  },
  {
    id: "skill-security",
    label: "Security Audit",
    category: "skill",
    description: "OWASP-based audit with severity, location, and remediation",
    starter: `Act as a security audit engineer.\n\nScope: All files in [target directory or recent changes].\n\nCheck against OWASP Top 10:\n1. Injection (SQL, NoSQL, command, LDAP)\n2. Broken authentication (weak tokens, missing expiry, session fixation)\n3. Sensitive data exposure (plaintext secrets, logs leaking PII)\n4. XML external entities (if applicable)\n5. Broken access control (missing auth middleware, privilege escalation)\n6. Security misconfiguration (debug mode, default credentials, open CORS)\n7. XSS (reflected, stored, DOM-based)\n8. Insecure deserialization\n9. Components with known vulnerabilities (outdated deps)\n10. Insufficient logging (auth failures not logged, no rate limiting)\n\nAdditional checks:\n- Hardcoded secrets, API keys, or tokens in source\n- Missing input validation or sanitization\n- Rate limiting on authentication endpoints\n- Error responses leaking internal details (stack traces, DB schema)\n\nOutput format for each finding:\n[file:line] [Critical/High/Medium/Low]\nIssue: [one sentence]\nExploit scenario: [how an attacker would use this]\nFix: [concrete code change or configuration]\n\nRules:\n- Only report actual vulnerabilities, not theoretical risks\n- Critical and High must include remediation code\n- If no issues found, state "No vulnerabilities detected" with confidence level`,
  },
  {
    id: "skill-docs",
    label: "Documentation",
    category: "skill",
    description: "Generate developer-focused docs with examples and architecture",
    starter: `Target: [module, API, or project area]\n\nDocumentation type: [API reference / Architecture overview / Setup guide / Migration guide]\n\nAudience: [developers on the team / external API consumers / new contributors]\n\nRequirements:\n- Start with a one-paragraph summary of what this does and why\n- Include a quick-start example (copy-paste-run)\n- Document all public functions/endpoints with:\n  - Parameters (name, type, required/optional, default)\n  - Return type and shape\n  - Error cases and what they return\n  - One usage example per function\n- Architecture section: how components connect, data flow\n- Configuration: all env vars and config options with descriptions\n\nConstraints:\n- Keep it concise — developers scan, they do not read novels\n- Use code blocks for all examples\n- No marketing language or filler\n- If behavior is undocumented or unclear from code, flag it as "needs clarification"\n- Match the existing documentation style in the project\n\nOutput: Write directly to [target file — README.md / docs/api.md / etc.]`,
  },
];

export function textToXml(name: string, content: string, category: PromptCategory): string {
  const escaped = content
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  if (category === "skill") {
    return `<agent_task>
  <identity>
    <role>Specialized coding agent executing a scoped skill</role>
    <constraints>
      <constraint>Only modify files within assigned scope</constraint>
      <constraint>Follow existing project patterns and conventions</constraint>
      <constraint>No emojis in code, comments, or commits</constraint>
      <constraint>Search for solutions before guessing</constraint>
      <constraint>Stop when acceptance criteria are met</constraint>
    </constraints>
  </identity>

  <context>
    <skill_name>${name}</skill_name>
    <execution_mode>autonomous</execution_mode>
  </context>

  <instructions>
${escaped}
  </instructions>

  <quality_gates>
    <gate type="pre-flight">Verify scope and dependencies before starting</gate>
    <gate type="testing">All tests must pass including new ones</gate>
    <gate type="lint">Lint and type checks must be clean</gate>
    <gate type="build">Build must succeed</gate>
    <gate type="scope">No changes outside assigned files</gate>
    <gate type="regression">No existing tests broken</gate>
  </quality_gates>

  <output>
    <format>Pull request with clear title and description</format>
    <steps>
      <step>Read and understand the target code</step>
      <step>Identify the minimal change needed</step>
      <step>Implement changes within scope</step>
      <step>Write or update tests to verify</step>
      <step>Run full test suite, lint, and build</step>
      <step>Create PR with summary of what changed and why</step>
    </steps>
    <stop_condition>All acceptance criteria met, tests pass, no scope creep</stop_condition>
  </output>
</agent_task>`;
  }

  return `<agent_task>
  <identity>
    <role>Coding agent executing a structured task</role>
    <constraints>
      <constraint>Only modify files within assigned scope</constraint>
      <constraint>Follow existing project patterns and conventions</constraint>
      <constraint>No emojis in code, comments, or commits</constraint>
      <constraint>Search for solutions before guessing</constraint>
      <constraint>Ask for clarification if requirements are ambiguous</constraint>
    </constraints>
  </identity>

  <instructions>
    <task_name>${name}</task_name>
    <task_description>
${escaped}
    </task_description>
  </instructions>

  <quality_gates>
    <gate type="testing">All tests must pass</gate>
    <gate type="lint">Lint and type checks must be clean</gate>
    <gate type="build">Build must succeed</gate>
    <gate type="review">Changes are minimal and reviewable</gate>
  </quality_gates>

  <output>
    <format>Numbered findings or pull request depending on task type</format>
    <steps>
      <step>Analyze the target code or changes</step>
      <step>Execute the task as specified</step>
      <step>Verify results against acceptance criteria</step>
      <step>Report findings or create PR</step>
    </steps>
    <stop_condition>Task complete, all criteria met, no unrelated changes</stop_condition>
  </output>
</agent_task>`;
}

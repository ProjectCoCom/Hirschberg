-- Summary: Supabase-compatible PostgreSQL schema definitions.
--
-- What it does: Defines tables, triggers, and views for the remote workspace database layout.
--
-- How it fits in: Kept for reference and documentation of schema structure.




create extension if not exists "uuid-ossp";
create extension if not exists "pgcrypto";

-- Jules account management

create table if not exists accounts (
    id uuid primary key default uuid_generate_v4(),
    name text not null,
    api_key_hash text not null,
    plan text not null default 'free' check (plan in ('free', 'pro', 'ultra')),
    max_concurrent int not null default 3,
    max_daily_tasks int not null default 15,
    enabled boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists account_sources (
    id uuid primary key default uuid_generate_v4(),
    account_id uuid not null references accounts(id) on delete cascade,
    source_name text not null,
    repo_owner text not null,
    repo_name text not null,
    created_at timestamptz not null default now(),
    unique (account_id, source_name)
);

-- Workflows and tasks

create table if not exists workflows (
    id uuid primary key default uuid_generate_v4(),
    name text not null,
    description text not null default '',
    status text not null default 'created'
        check (status in ('created', 'running', 'completed', 'failed', 'cancelled')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists agent_tasks (
    id uuid primary key default uuid_generate_v4(),
    workflow_id uuid references workflows(id) on delete cascade,
    parent_task_id uuid references agent_tasks(id) on delete set null,
    account_id uuid references accounts(id) on delete set null,
    session_id text,
    prompt text not null,
    repo_owner text not null default '',
    repo_name text not null default '',
    branch text not null default 'main',
    status text not null default 'pending'
        check (status in ('pending', 'waiting', 'running', 'completed', 'failed', 'cancelled')),
    depends_on uuid[] not null default '{}',
    pr_url text not null default '',
    context jsonb not null default '{}',
    error text not null default '',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- Context passing and merge queue

create table if not exists context_messages (
    id uuid primary key default uuid_generate_v4(),
    from_task_id uuid references agent_tasks(id) on delete cascade,
    to_task_id uuid references agent_tasks(id) on delete cascade,
    task_id uuid references agent_tasks(id) on delete cascade,
    message jsonb not null default '{}',
    context jsonb not null default '{}',
    created_at timestamptz not null default now()
);

create table if not exists merge_queue (
    id uuid primary key default uuid_generate_v4(),
    task_id uuid not null references agent_tasks(id) on delete cascade,
    repo_owner text not null,
    repo_name text not null,
    pr_number int not null,
    pr_url text not null default '',
    head_ref text not null default '',
    merge_strategy text not null default 'squash'
        check (merge_strategy in ('squash', 'merge', 'rebase')),
    ci_status text not null default 'pending'
        check (ci_status in ('pending', 'running', 'passed', 'failed')),
    merged boolean not null default false,
    merge_sha text not null default '',
    error text not null default '',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists session_activities (
    id uuid primary key default uuid_generate_v4(),
    task_id uuid not null references agent_tasks(id) on delete cascade,
    session_id text not null,
    activity_id text not null,
    originator text not null default '',
    description text not null default '',
    activity_type text not null default '',
    artifacts jsonb not null default '[]',
    raw_data jsonb not null default '{}',
    created_at timestamptz not null default now(),
    unique (session_id, activity_id)
);

-- AI provider management (encrypted keys stored as text)

create table if not exists ai_providers (
    id uuid primary key default uuid_generate_v4(),
    provider_type text not null,
    name text not null unique,
    api_key_encrypted text,
    model text not null default '',
    base_url text not null default '',
    enabled boolean not null default true,
    daily_limit int not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- Drop and recreate provider_type constraint so it always has the latest list
alter table ai_providers drop constraint if exists ai_providers_provider_type_check;
alter table ai_providers add constraint ai_providers_provider_type_check
    check (provider_type in ('groq', 'google', 'cloudflare', 'openrouter', 'ollama', 'cerebras', 'cohere', 'mistral', 'nvidia_nim', 'github_models', 'huggingface', 'sambanova', 'fireworks', 'nebius', 'hyperbolic', 'scaleway', 'longcat'));

-- Conversations

create table if not exists conversations (
    id uuid primary key default uuid_generate_v4(),
    title text not null default 'New Conversation',
    provider_id uuid references ai_providers(id) on delete set null,
    model text not null default '',
    mode text not null default 'ask'
        check (mode in ('ask', 'plan', 'build')),
    repo_owner text not null default '',
    repo_name text not null default '',
    template text not null default '',
    status text not null default 'active'
        check (status in ('active', 'archived', 'completed')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists conversation_messages (
    id uuid primary key default uuid_generate_v4(),
    conversation_id uuid not null references conversations(id) on delete cascade,
    role text not null check (role in ('user', 'assistant', 'system')),
    content text not null,
    image_urls text[] not null default '{}',
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now()
);

-- Prompt library

create table if not exists prompts (
    id uuid primary key default uuid_generate_v4(),
    name text not null unique,
    source text not null default 'user' check (source in ('builtin', 'user')),
    content text not null default '',
    format text not null default 'xml' check (format in ('xml', 'text')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- Indexes (idempotent via DO block)

do $$ begin
  if not exists (select 1 from pg_indexes where indexname = 'idx_agent_tasks_workflow') then
    create index idx_agent_tasks_workflow on agent_tasks(workflow_id);
  end if;
  if not exists (select 1 from pg_indexes where indexname = 'idx_agent_tasks_status') then
    create index idx_agent_tasks_status on agent_tasks(status);
  end if;
  if not exists (select 1 from pg_indexes where indexname = 'idx_context_messages_to') then
    create index idx_context_messages_to on context_messages(to_task_id);
  end if;
  if not exists (select 1 from pg_indexes where indexname = 'idx_merge_queue_task') then
    create index idx_merge_queue_task on merge_queue(task_id);
  end if;
  if not exists (select 1 from pg_indexes where indexname = 'idx_session_activities_task') then
    create index idx_session_activities_task on session_activities(task_id);
  end if;
  if not exists (select 1 from pg_indexes where indexname = 'idx_session_activities_session') then
    create index idx_session_activities_session on session_activities(session_id);
  end if;
  if not exists (select 1 from pg_indexes where indexname = 'idx_conv_messages_conv') then
    create index idx_conv_messages_conv on conversation_messages(conversation_id);
  end if;
  if not exists (select 1 from pg_indexes where indexname = 'idx_conversations_status') then
    create index idx_conversations_status on conversations(status);
  end if;
  if not exists (select 1 from pg_indexes where indexname = 'idx_ai_providers_type') then
    create index idx_ai_providers_type on ai_providers(provider_type);
  end if;
  if not exists (select 1 from pg_indexes where indexname = 'idx_prompts_source') then
    create index idx_prompts_source on prompts(source);
  end if;
end $$;

-- Seed built-in prompts (skip if already exist)

insert into prompts (name, source, content, format) values
('security-audit', 'builtin', '<prompt name="security-audit">
  <description>Deep security review of API endpoints and data handling</description>
  <system_instruction>You are a security specialist. Analyze the codebase for vulnerabilities.</system_instruction>
  <constraints>
    <constraint>Check for SQL injection, XSS, auth bypass, rate limiting, input validation</constraint>
    <constraint>Produce a prioritized list of findings with severity levels</constraint>
    <constraint>Decompose fixes into agent tasks with specific file scopes</constraint>
  </constraints>
  <output_format>JSON agent decomposition with findings summary</output_format>
</prompt>', 'xml'),
('add-tests', 'builtin', '<prompt name="add-tests">
  <description>Add comprehensive unit tests for components lacking coverage</description>
  <system_instruction>You are a testing specialist. Identify untested code and write tests.</system_instruction>
  <constraints>
    <constraint>Follow existing test patterns in the project</constraint>
    <constraint>Aim for over 80% coverage on new code</constraint>
    <constraint>Test edge cases, error paths, and happy paths</constraint>
  </constraints>
  <output_format>JSON agent decomposition grouped by test scope</output_format>
</prompt>', 'xml'),
('code-review', 'builtin', '<prompt name="code-review">
  <description>Review codebase for quality issues and create findings report</description>
  <system_instruction>You are a code review specialist. Analyze for quality, performance, and maintainability.</system_instruction>
  <constraints>
    <constraint>Check code style consistency and error handling patterns</constraint>
    <constraint>Identify performance bottlenecks and memory leaks</constraint>
    <constraint>Produce actionable findings, not vague suggestions</constraint>
  </constraints>
  <output_format>REVIEW.md with prioritized findings, then JSON agent decomposition</output_format>
</prompt>', 'xml'),
('new-project', 'builtin', '<prompt name="new-project">
  <description>Plan and scaffold a new repository from scratch</description>
  <system_instruction>You are a senior software architect. Help the user plan a new project.</system_instruction>
  <constraints>
    <constraint>Ask clarifying questions before proposing architecture</constraint>
    <constraint>Each agent task must be completable in a single session</constraint>
    <constraint>Include CI/CD setup as one of the agent tasks</constraint>
  </constraints>
  <output_format>Project structure overview, then JSON agent decomposition</output_format>
</prompt>', 'xml'),
('fix-issues', 'builtin', '<prompt name="fix-issues">
  <description>Analyze and fix bugs or issues in an existing repo</description>
  <system_instruction>You are a debugging specialist. Identify root causes and propose fixes.</system_instruction>
  <constraints>
    <constraint>Identify root cause before proposing fixes</constraint>
    <constraint>Include regression tests for each bug fix</constraint>
    <constraint>Do not refactor unrelated code while fixing bugs</constraint>
  </constraints>
  <output_format>Root cause analysis, then JSON agent decomposition for fixes</output_format>
</prompt>', 'xml')
on conflict (name) do nothing;

-- Disable RLS on all tables (private backend, no public access)

alter table accounts disable row level security;
alter table account_sources disable row level security;
alter table workflows disable row level security;
alter table agent_tasks disable row level security;
alter table context_messages disable row level security;
alter table merge_queue disable row level security;
alter table session_activities disable row level security;
alter table ai_providers disable row level security;
alter table conversations disable row level security;
alter table conversation_messages disable row level security;
alter table prompts disable row level security;

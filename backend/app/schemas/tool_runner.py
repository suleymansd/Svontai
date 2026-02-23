"""Schemas for standardized tool execution contracts."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ToolContext(BaseModel):
    locale: str = "tr-TR"
    timezone: str = "Europe/Istanbul"
    channel: str = "web"
    memory: dict = Field(default_factory=dict)


class ToolRunRequest(BaseModel):
    request_id: str | None = Field(default=None, alias="requestId")
    tool_slug: str = Field(..., alias="toolSlug")
    tool_input: dict = Field(default_factory=dict, alias="toolInput")
    context: ToolContext = Field(default_factory=ToolContext)

    model_config = ConfigDict(populate_by_name=True)


class ToolRunError(BaseModel):
    message: str
    code: str | None = None
    node: str | None = None


class ToolRunUsage(BaseModel):
    time_ms: int = Field(default=0, alias="timeMs")
    tokens: int | None = None
    cost: float | None = None

    model_config = ConfigDict(populate_by_name=True)


class ToolRunArtifact(BaseModel):
    id: str | None = None
    type: str
    name: str
    url: str | None = None
    storage_provider: str | None = Field(default=None, alias="storageProvider")
    path: str | None = None
    meta: dict = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class ToolRunResponse(BaseModel):
    request_id: str = Field(..., alias="requestId")
    success: bool
    data: dict = Field(default_factory=dict)
    error: ToolRunError | None = None
    usage: ToolRunUsage = Field(default_factory=ToolRunUsage)
    artifacts: list[ToolRunArtifact] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class ToolRunListItem(BaseModel):
    request_id: str = Field(..., alias="requestId")
    tool_slug: str = Field(..., alias="toolSlug")
    status: str
    success: bool = False
    n8n_execution_id: str | None = Field(default=None, alias="n8nExecutionId")
    created_at: datetime = Field(..., alias="createdAt")
    finished_at: datetime | None = Field(default=None, alias="finishedAt")
    artifacts_count: int = Field(default=0, alias="artifactsCount")

    model_config = ConfigDict(populate_by_name=True)


class ToolRunDetailResponse(ToolRunResponse):
    tool_slug: str = Field(..., alias="toolSlug")
    status: str
    correlation_id: str | None = Field(default=None, alias="correlationId")
    n8n_execution_id: str | None = Field(default=None, alias="n8nExecutionId")
    created_at: datetime = Field(..., alias="createdAt")
    started_at: datetime | None = Field(default=None, alias="startedAt")
    finished_at: datetime | None = Field(default=None, alias="finishedAt")

    model_config = ConfigDict(populate_by_name=True)


class AssistantChatRequest(BaseModel):
    request_id: str | None = Field(default=None, alias="requestId")
    message: str
    context: ToolContext = Field(default_factory=ToolContext)
    preferred_tool: str | None = Field(default=None, alias="preferredTool")

    model_config = ConfigDict(populate_by_name=True)


class AssistantChatResponse(BaseModel):
    request_id: str = Field(..., alias="requestId")
    mode: str  # direct|tool
    message: str
    tool_result: ToolRunResponse | None = Field(default=None, alias="toolResult")

    model_config = ConfigDict(populate_by_name=True)


class ToolRegistryItem(BaseModel):
    slug: str
    key: str
    name: str
    description: str | None = None
    category: str | None = None
    status: str
    is_public: bool = Field(alias="isPublic")
    is_premium: bool = Field(alias="isPremium")
    required_plan: str = Field(default="free", alias="requiredPlan")
    enabled: bool
    required_integrations: list[str] = Field(default_factory=list, alias="requiredIntegrations")
    n8n_workflow_id: str | None = Field(default=None, alias="n8nWorkflowId")
    rate_limit_per_minute: int | None = Field(default=None, alias="rateLimitPerMinute")

    model_config = ConfigDict(populate_by_name=True)


class TenantToolUpsertRequest(BaseModel):
    enabled: bool
    rate_limit_per_minute: int | None = Field(default=None, alias="rateLimitPerMinute")
    config: dict = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)

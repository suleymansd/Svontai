"""Seed helpers for initial marketplace tools."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.tool import Tool


INITIAL_TOOL_DEFINITIONS: list[dict] = [
    {
        "key": "pdf_summary",
        "slug": "pdf_summary",
        "name": "PDF Summary",
        "description": "PDF içeriğini kısa özetler.",
        "category": "documents",
        "required_integrations_json": ["openai"],
        "required_plan": "free",
        "input_schema_json": {
            "type": "object",
            "properties": {
                "pdf_url": {"type": "string", "format": "uri"},
                "base64_pdf": {"type": "string"},
                "language": {"type": "string", "default": "tr"},
            },
            "anyOf": [{"required": ["pdf_url"]}, {"required": ["base64_pdf"]}],
        },
        "output_schema_json": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "artifact_url": {"type": "string"},
            },
            "required": ["summary"],
        },
        "n8n_workflow_id": "svontai-tool-runner",
    },
    {
        "key": "pdf_to_word",
        "slug": "pdf_to_word",
        "name": "PDF to Word",
        "description": "PDF dosyasını Word formatına çevirir.",
        "category": "documents",
        "required_integrations_json": ["document_converter"],
        "required_plan": "pro",
        "input_schema_json": {
            "type": "object",
            "properties": {
                "pdf_url": {"type": "string", "format": "uri"},
                "base64_pdf": {"type": "string"},
                "output_name": {"type": "string"},
            },
            "anyOf": [{"required": ["pdf_url"]}, {"required": ["base64_pdf"]}],
        },
        "output_schema_json": {
            "type": "object",
            "properties": {
                "document_url": {"type": "string"},
                "filename": {"type": "string"},
            },
            "required": ["document_url"],
        },
        "n8n_workflow_id": "svontai-tool-runner",
    },
    {
        "key": "drive_save_file",
        "slug": "drive_save_file",
        "name": "Drive Save File",
        "description": "Dosyayı Google Drive klasörüne kaydeder.",
        "category": "storage",
        "required_integrations_json": ["google_drive"],
        "required_plan": "pro",
        "input_schema_json": {
            "type": "object",
            "properties": {
                "file_url": {"type": "string", "format": "uri"},
                "base64_content": {"type": "string"},
                "file_name": {"type": "string"},
                "folder_id": {"type": "string"},
            },
            "anyOf": [{"required": ["file_url"]}, {"required": ["base64_content"]}],
            "required": ["file_name"],
        },
        "output_schema_json": {
            "type": "object",
            "properties": {
                "drive_file_id": {"type": "string"},
                "drive_file_url": {"type": "string"},
            },
            "required": ["drive_file_id", "drive_file_url"],
        },
        "n8n_workflow_id": "svontai-tool-runner",
    },
    {
        "key": "excel_analysis",
        "slug": "excel_analysis",
        "name": "Excel Analysis",
        "description": "Excel verisini analiz edip özet çıkarır.",
        "category": "analytics",
        "required_integrations_json": ["openai"],
        "required_plan": "pro",
    },
    {
        "key": "email_send",
        "slug": "email_send",
        "name": "Email Send",
        "description": "Email gönderimi yapar.",
        "category": "communication",
        "required_integrations_json": ["gmail"],
        "required_plan": "premium",
    },
    {
        "key": "gmail_summary",
        "slug": "gmail_summary",
        "name": "Gmail Summary",
        "description": "Gmail kutusunu özetler.",
        "category": "communication",
        "required_integrations_json": ["gmail", "openai"],
        "required_plan": "premium",
        "input_schema_json": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_messages": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
                "label_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["query"],
        },
        "output_schema_json": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "message_count": {"type": "integer"},
                "gmail_search_url": {"type": "string"},
            },
            "required": ["summary"],
        },
        "n8n_workflow_id": "svontai-tool-runner",
    },
    {
        "key": "meeting_summary",
        "slug": "meeting_summary",
        "name": "Meeting Summary",
        "description": "Toplantı notlarını aksiyon maddeleriyle özetler.",
        "category": "productivity",
        "required_integrations_json": ["openai"],
        "required_plan": "premium",
    },
    {
        "key": "ocr_image_to_text",
        "slug": "ocr_image_to_text",
        "name": "OCR Image to Text",
        "description": "Görsellerden metin çıkarır.",
        "category": "vision",
        "required_integrations_json": ["openai"],
        "required_plan": "premium",
    },
    {
        "key": "lead_capture_to_crm_or_sheet",
        "slug": "lead_capture_to_crm_or_sheet",
        "name": "Lead Capture to CRM/Sheet",
        "description": "Lead verisini CRM veya Google Sheet'e yazar.",
        "category": "crm",
        "required_integrations_json": ["google_sheets"],
        "required_plan": "premium",
    },
    {
        "key": "report_generator",
        "slug": "report_generator",
        "name": "Report Generator",
        "description": "Verilerden özet rapor üretir.",
        "category": "analytics",
        "required_integrations_json": ["openai"],
        "required_plan": "enterprise",
    },
]


def seed_initial_tools(db: Session) -> dict:
    created = 0
    updated = 0
    for item in INITIAL_TOOL_DEFINITIONS:
        tool = db.query(Tool).filter(Tool.key == item["key"]).first()
        if not tool:
            tool = Tool(
                key=item["key"],
                slug=item["slug"],
                name=item["name"],
                description=item["description"],
                category=item["category"],
                status="active",
                is_public=True,
                coming_soon=False,
                is_premium=item.get("required_plan") in {"premium", "enterprise"},
                required_plan=item.get("required_plan"),
                required_integrations_json=item["required_integrations_json"],
                input_schema_json=item.get("input_schema_json", {}),
                output_schema_json=item.get("output_schema_json", {}),
                n8n_workflow_id=item.get("n8n_workflow_id"),
            )
            db.add(tool)
            created += 1
        else:
            tool.slug = item["slug"]
            tool.name = item["name"]
            tool.description = item["description"]
            tool.category = item["category"]
            tool.required_plan = item.get("required_plan")
            tool.is_premium = item.get("required_plan") in {"premium", "enterprise"}
            tool.required_integrations_json = item["required_integrations_json"]
            tool.input_schema_json = item.get("input_schema_json", tool.input_schema_json or {})
            tool.output_schema_json = item.get("output_schema_json", tool.output_schema_json or {})
            if item.get("n8n_workflow_id"):
                tool.n8n_workflow_id = item["n8n_workflow_id"]
            if tool.status not in {"active", "draft", "disabled"}:
                tool.status = "active"
            updated += 1

    db.commit()
    return {"created": created, "updated": updated, "total": len(INITIAL_TOOL_DEFINITIONS)}

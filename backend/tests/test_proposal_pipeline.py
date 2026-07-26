import io
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from docx import Document
from werkzeug.datastructures import FileStorage

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from proposal_agent import analyze_document, _normalize_architecture, _sanitize_extracted_requirements
from proposal_ingestion import ingest_text, ingest_upload


class ProposalPipelineTests(unittest.TestCase):
    def test_docx_tables_are_preserved_in_ingestion(self):
        document = Document()
        document.add_heading("Security Requirements", level=1)
        document.add_paragraph("Employees must authenticate with single sign-on.")
        table = document.add_table(rows=2, cols=2)
        table.cell(0, 0).text = "Retention"
        table.cell(0, 1).text = "90 days"
        table.cell(1, 0).text = "Audit logs"
        table.cell(1, 1).text = "12 months"
        raw = io.BytesIO()
        document.save(raw)
        raw.seek(0)

        ingestion = ingest_upload(FileStorage(raw, filename="requirements.docx"))

        self.assertEqual(ingestion["source_type"], "docx")
        self.assertGreaterEqual(ingestion["stats"]["chunks"], 1)
        joined = "\n".join(chunk["text"] for chunk in ingestion["chunks"])
        self.assertIn("Retention | 90 days", joined)
        self.assertIn("Audit logs | 12 months", joined)

    def test_hierarchical_chunking_preserves_sections_and_pages(self):
        text = "\f".join(
            [
                "1 Scope\n\n" + ("The solution must accept customer requirement documents. " * 20),
                "2 Security Requirements\n\n" + ("Employees must use single sign-on and authorized project access. " * 20),
                "3 Performance\n\n" + ("The system must process a 150-page document within 12 minutes. " * 20),
            ]
        )
        ingestion = ingest_text(text, "long-rfp.txt")
        chunks = ingestion["chunks"]

        self.assertGreaterEqual(len(chunks), 3)
        self.assertTrue(all(chunk["chunk_id"] and chunk["section"] for chunk in chunks))
        self.assertEqual({1, 2, 3}, {chunk["page_start"] for chunk in chunks})

    def test_requirement_normalizer_removes_cross_category_duplicates(self):
        raw = {
            "functional_requirements": [
                "The solution shall read documents from Microsoft SharePoint.",
                "Architecture generation must not begin until an architect approves requirements.",
            ],
            "non_functional_requirements": [
                "Expected peak concurrency is 20 users.",
                "Minimize monthly operating cost.",
            ],
            "constraints": [
                "Use Microsoft Azure as the primary cloud platform.",
                "Documents must be retained for 90 days.",
            ],
            "integrations": ["Read documents from Microsoft SharePoint."],
            "security_needs": [
                "Employees must authenticate using single sign-on.",
                "Customer documents are confidential and only authorized project members may access them.",
            ],
            "expected_users": ["Expected peak concurrency is 20 users."],
        }
        normalized = _sanitize_extracted_requirements(raw)

        self.assertEqual(len(normalized["integrations"]), 1)
        self.assertEqual(normalized["expected_users"], [])
        self.assertIn("Expected peak concurrency is 20 users.", normalized["non_functional_requirements"])
        self.assertIn("Minimize monthly operating cost.", normalized["constraints"])
        self.assertIn("Employees must authenticate using single sign-on.", normalized["security_needs"])

    def test_analysis_returns_traceable_requirement_records(self):
        ingestion = ingest_text(
            "1 Security\n\nEmployees must authenticate using single sign-on. "
            "Customer documents are confidential and only authorized project members may access them.",
            "security.txt",
        )
        with patch("proposal_agent.azure_openai_configured", return_value=False):
            analysis = analyze_document(ingestion)

        records = analysis["traceability"]["security_needs"]
        self.assertGreaterEqual(len(records), 1)
        self.assertTrue(records[0]["source_chunk_ids"])
        self.assertIn(records[0]["confidence"], {"high", "medium"})

    def test_architecture_normalizer_enforces_contract(self):
        extracted = {
            "business_goals": ["Reduce proposal preparation time by 40 percent."],
            "functional_requirements": ["Export a PowerPoint template."],
            "non_functional_requirements": ["P95 response time below four seconds."],
            "constraints": ["Use Azure and minimize cost."],
            "assumptions": [],
            "integrations": ["Read documents from SharePoint."],
            "security_needs": ["Use SSO and project-scoped access."],
            "expected_users": ["Support 20 users."],
        }
        architecture = _normalize_architecture(
            {
                "architecture_summary": "Draft",
                "selected_patterns": ["RAG with metadata filtering"],
                "components": [
                    {
                        "service": "Azure Cognitive Search",
                        "purpose": "Grounded document retrieval.",
                        "requirement_ids": ["functional_requirements"],
                    },
                    {
                        "service": "Azure Functions (Consumption)",
                        "purpose": "Run the authenticated API and approval workflow.",
                        "requirement_ids": ["functional_requirements"],
                    },
                    {
                        "service": "Azure AD",
                        "purpose": "Authenticate enterprise users.",
                        "requirement_ids": ["security_needs"],
                    },
                ],
            },
            extracted,
            [{"title": "Azure AI Search", "url": "https://learn.microsoft.com/azure/search/"}],
            "azure_official_only",
        )

        self.assertEqual(architecture["research_status"], "completed")
        self.assertIn("Workflow automation", architecture["selected_patterns"])
        self.assertEqual(architecture["components"][0]["service"], "Azure AI Search")
        services = [item["service"] for item in architecture["components"]]
        self.assertIn("Microsoft Entra ID", services)
        self.assertNotIn("Azure Container Apps", services)
        self.assertEqual(set(architecture["cost_estimate"]), {"development", "test", "uat_or_staging"})
        self.assertTrue(any("template mapping" in item["service"].lower() for item in architecture["components"]))

    def test_150_page_text_ingestion_speed(self):
        page = "1 Requirement Section\n\n" + ("The platform must retain source metadata for traceability. " * 45)
        text = "\f".join(page for _ in range(150))

        started = time.perf_counter()
        ingestion = ingest_text(text, "150-pages.txt")
        elapsed = time.perf_counter() - started

        self.assertEqual(ingestion["stats"]["pages"], 150)
        self.assertGreater(ingestion["stats"]["chunks"], 10)
        self.assertLess(elapsed, 3.0, f"Ingestion took {elapsed:.2f}s")


if __name__ == "__main__":
    unittest.main()

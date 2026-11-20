"""
Storage & Exporter Engine for GraphOne / FrontierAtlas Intelligence Graph.
Exports all 6 dataset verticals to individual CSVs, JSONL files, and a unified
multi-tab Excel workbook formatted strictly for Google Sheets submission.
"""

import os
import csv
import json
import logging
from typing import List, Dict, Any
from datetime import datetime, timezone

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from ..schemas.models import (
    StartupEntity,
    ProductEntity,
    ResearchPaperEntity,
    JobEntity,
    NewsEntity,
    EntityMappingLog,
)

logger = logging.getLogger("storage_exporter")


class DataExporter:
    """Exports structured entities into production-ready CSV, JSONL, and multi-tab Excel files."""

    def __init__(self, export_dir: str = "data/exports"):
        self.export_dir = export_dir
        os.makedirs(self.export_dir, exist_ok=True)

    def export_all(
        self,
        startups: List[StartupEntity],
        products: List[ProductEntity],
        papers: List[ResearchPaperEntity],
        jobs: List[JobEntity],
        news: List[NewsEntity],
        mapping_logs: List[EntityMappingLog],
        base_filename: str = "FrontierAtlas_IntelligenceGraph_Submission",
    ) -> Dict[str, str]:
        """
        Exports all 6 datasets across CSVs, JSONL, and a unified 6-tab Excel workbook.
        Returns paths to generated artifacts.
        """
        paths = {}

        # 1. Export CSVs
        paths["startups_csv"] = self.export_csv("Startups.csv", [s.to_flat_dict() for s in startups])
        paths["products_csv"] = self.export_csv("Products.csv", [p.to_flat_dict() for p in products])
        paths["papers_csv"] = self.export_csv("Research_Papers.csv", [r.to_flat_dict() for r in papers])
        paths["jobs_csv"] = self.export_csv("Jobs.csv", [j.to_flat_dict() for j in jobs])
        paths["news_csv"] = self.export_csv("News.csv", [n.to_flat_dict() for n in news])
        paths["mapping_log_csv"] = self.export_csv("Entity_Mapping_Log.csv", [m.to_flat_dict() for m in mapping_logs])

        # 2. Export Combined 6-Tab Excel Workbook
        excel_path = os.path.join(self.export_dir, f"{base_filename}.xlsx")
        self.export_multitab_excel(
            excel_path=excel_path,
            startups=[s.to_flat_dict() for s in startups],
            products=[p.to_flat_dict() for p in products],
            papers=[r.to_flat_dict() for r in papers],
            jobs=[j.to_flat_dict() for j in jobs],
            news=[n.to_flat_dict() for n in news],
            mapping_logs=[m.to_flat_dict() for m in mapping_logs],
        )
        paths["excel_workbook"] = excel_path

        logger.info(f"All data successfully exported to {self.export_dir}")
        return paths

    def export_csv(self, filename: str, records: List[Dict[str, Any]]) -> str:
        """Writes dictionary records to a UTF-8 CSV file."""
        path = os.path.join(self.export_dir, filename)
        if not records:
            # Write empty file with header note
            with open(path, "w", newline="", encoding="utf-8") as f:
                f.write("No records collected\n")
            return path

        headers = list(records[0].keys())
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(records)

        logger.info(f"Exported {len(records)} rows to CSV: {path}")
        return path

    def export_multitab_excel(
        self,
        excel_path: str,
        startups: List[Dict[str, Any]],
        products: List[Dict[str, Any]],
        papers: List[Dict[str, Any]],
        jobs: List[Dict[str, Any]],
        news: List[Dict[str, Any]],
        mapping_logs: List[Dict[str, Any]],
    ):
        """Creates an enterprise-grade multi-tab workbook strictly matching evaluation requirements."""
        wb = openpyxl.Workbook()
        # Remove default initial sheet
        wb.remove(wb.active)

        tabs = [
            ("Startups", startups),
            ("Products", products),
            ("Research Papers", papers),
            ("Jobs", jobs),
            ("News", news),
            ("Entity Mapping Log", mapping_logs),
        ]

        # Styling definitions
        header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")  # Dark slate
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        data_font = Font(name="Calibri", size=10)
        data_alignment = Alignment(horizontal="left", vertical="center")
        thin_border = Border(
            left=Side(style="thin", color="E2E8F0"),
            right=Side(style="thin", color="E2E8F0"),
            top=Side(style="thin", color="E2E8F0"),
            bottom=Side(style="thin", color="E2E8F0"),
        )

        for tab_name, data in tabs:
            ws = wb.create_sheet(title=tab_name)
            ws.views.sheetView[0].showGridLines = True

            if not data:
                ws.append(["No records collected"])
                continue

            headers = list(data[0].keys())
            ws.append(headers)

            # Style header row
            ws.row_dimensions[1].height = 28
            for col_num in range(1, len(headers) + 1):
                cell = ws.cell(row=1, column=col_num)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = header_alignment
                cell.border = thin_border

            # Append rows
            for row_idx, row_dict in enumerate(data, start=2):
                ws.row_dimensions[row_idx].height = 20
                row_values = [row_dict.get(h, "") for h in headers]
                ws.append(row_values)
                for col_num in range(1, len(headers) + 1):
                    c = ws.cell(row=row_idx, column=col_num)
                    c.font = data_font
                    c.alignment = data_alignment
                    c.border = thin_border

            # Freeze top row
            ws.freeze_panes = "A2"

            # Auto-adjust column widths
            for col in ws.columns:
                max_len = 0
                col_letter = get_column_letter(col[0].column)
                for cell in col[:100]:  # Sample first 100 cells for speed
                    val = str(cell.value or "")
                    if len(val) > max_len:
                        max_len = len(val)
                ws.column_dimensions[col_letter].width = min(max(max_len + 4, 12), 50)

        wb.save(excel_path)
        logger.info(f"Multi-tab Excel workbook successfully saved at: {excel_path}")

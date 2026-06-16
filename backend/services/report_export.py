from __future__ import annotations
import json
from typing import Any, Dict

def export_report_to_json(report: Dict[str, Any]) -> str:
    """Serialize storytelling report to structured JSON format."""
    return json.dumps(report, indent=2)

def export_report_to_markdown(report: Dict[str, Any]) -> str:
    """Format storytelling report into a readable Markdown document."""
    exec_summary = report.get("executive_summary", {})
    sections = report.get("sections", [])
    recommendations = report.get("recommendations", [])
    
    md_lines = [
        f"# {report.get('title', 'Data Storytelling Report')}",
        f"**Generated:** {report.get('generated_timestamp', '')} | **Confidence:** {int(report.get('confidence_score', 0.85) * 100)}%",
        "",
        "## 1. Executive Summary",
        f"- **Dataset Overview:** {exec_summary.get('dataset_overview', '')}",
        f"- **Data Quality Score:** {exec_summary.get('data_quality_score', 0.0)}/100",
        f"- **Business Highlights:** {exec_summary.get('overall_business_summary', '')}",
        ""
    ]
    
    md_lines.append("## 2. Key Insights & Details")
    for sec in sections:
        md_lines.extend([
            f"### {sec.get('title', '')}",
            f"{sec.get('content', '')}",
            ""
        ])
        
    md_lines.append("## 3. Action Recommendations")
    for rec in recommendations:
        steps_str = "\n".join([f"  1. {step}" for step in rec.get("action_steps", [])])
        md_lines.extend([
            f"### [{rec.get('rec_type', '').upper()}] {rec.get('title', '')}",
            f"- **Description:** {rec.get('description', '')}",
            f"- **Expected Impact:** {rec.get('expected_impact', '')}",
            f"- **Action Steps:**",
            steps_str,
            ""
        ])
        
    md_lines.append("---")
    md_lines.append(f"**Sources:** {', '.join(report.get('sources', []))}")
    return "\n".join(md_lines)

def export_report_to_html(report: Dict[str, Any]) -> str:
    """Format storytelling report as an elegant print-ready HTML page."""
    exec_summary = report.get("executive_summary", {})
    sections = report.get("sections", [])
    recommendations = report.get("recommendations", [])
    
    # Building HTML layout
    sections_html = ""
    for sec in sections:
        sections_html += f"""
        <div class="section-card">
            <h3>{sec.get('title', '')}</h3>
            <p>{sec.get('content', '')}</p>
        </div>
        """
        
    recs_html = ""
    for rec in recommendations:
        steps_html = "".join([f"<li>{step}</li>" for step in rec.get("action_steps", [])])
        recs_html += f"""
        <div class="rec-card {rec.get('rec_type', '')}">
            <h4><span class="badge">{rec.get('rec_type', '').upper()}</span> {rec.get('title', '')}</h4>
            <p><strong>Description:</strong> {rec.get('description', '')}</p>
            <p><strong>Expected Impact:</strong> {rec.get('expected_impact', '')}</p>
            <p><strong>Action Steps:</strong></p>
            <ul>{steps_html}</ul>
        </div>
        """

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{report.get('title', 'Data Report')}</title>
    <style>
        body {{
            font-family: 'Outfit', -apple-system, sans-serif;
            color: #1e293b;
            background: #fff;
            margin: 0;
            padding: 40px;
            line-height: 1.6;
        }}
        .header {{
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        h1 {{
            margin: 0 0 10px 0;
            color: #0f172a;
            font-size: 24px;
        }}
        .meta {{
            font-size: 14px;
            color: #64748b;
        }}
        h2 {{
            color: #1e293b;
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 8px;
            margin-top: 40px;
            font-size: 20px;
        }}
        h3 {{
            color: #0f172a;
            font-size: 16px;
            margin-bottom: 10px;
        }}
        .exec-card {{
            background: #f8fafc;
            border-radius: 8px;
            padding: 20px;
            border: 1px solid #e2e8f0;
            margin-bottom: 20px;
        }}
        .section-card, .rec-card {{
            margin-bottom: 25px;
        }}
        .badge {{
            display: inline-block;
            background: #e2e8f0;
            color: #475569;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
            margin-right: 6px;
        }}
        .rec-card.business .badge {{ background: #dcfce7; color: #15803d; }}
        .rec-card.analytical .badge {{ background: #dbeafe; color: #1d4ed8; }}
        .rec-card.ml .badge {{ background: #f3e8ff; color: #6b21a8; }}
        
        @media print {{
            body {{ padding: 0; }}
            .section-card, .rec-card {{ page-break-inside: avoid; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{report.get('title', 'Data Storytelling Report')}</h1>
        <div class="meta">
            Generated: {report.get('generated_timestamp', '')} &nbsp;|&nbsp; 
            Confidence Score: {int(report.get('confidence_score', 0.85) * 100)}% &nbsp;|&nbsp;
            Sources: {', '.join(report.get('sources', []))}
        </div>
    </div>
    
    <h2>1. Executive Summary</h2>
    <div class="exec-card">
        <p><strong>Dataset Overview:</strong> {exec_summary.get('dataset_overview', '')}</p>
        <p><strong>Data Quality Score:</strong> {exec_summary.get('data_quality_score', 0.0)}/100</p>
        <p><strong>Business highlights:</strong> {exec_summary.get('overall_business_summary', '')}</p>
    </div>
    
    <h2>2. Key Findings & Details</h2>
    {sections_html}
    
    <h2>3. Action Recommendations</h2>
    {recs_html}
</body>
</html>
"""
    return html_content

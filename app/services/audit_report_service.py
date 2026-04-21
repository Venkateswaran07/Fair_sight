"""
AuditReportService — generates a structured PDF fairness audit report using ReportLab.

All generation happens in memory (BytesIO); no files are written to disk.

Seven sections
--------------
1. Header          — title, timestamp, dataset hash
2. Dataset Summary — row count, protected columns, group distribution
3. Fairness Metrics— DPD, EOD, DIR with value, threshold, PASS / FAIL
4. Proxy Findings  — ranked feature table with HIGH RISK badges
5. Mitigation      — before/after metric table (or "not applied")
6. Limitations     — fixed boilerplate
7. Sign-off        — blank lines for Auditor, Date, Signature
"""

import hashlib
import io
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ── Design tokens ──────────────────────────────────────────────────────────
_ACCENT    = colors.HexColor('#1D4ED8')   # blue — matches UI
_PASS_C    = colors.HexColor('#16A34A')   # green
_FAIL_C    = colors.HexColor('#DC2626')   # red
_WARN_C    = colors.HexColor('#D97706')   # amber — high-risk proxies
_LIGHT_BG  = colors.HexColor('#F3F4F6')
_BORDER    = colors.HexColor('#D1D5DB')


# ── Helpers ────────────────────────────────────────────────────────────────

def _hr(thickness: float = 0.5) -> HRFlowable:
    return HRFlowable(
        width='100%', thickness=thickness,
        color=_BORDER, spaceAfter=10, spaceBefore=4,
    )


def _section_heading(text: str, styles) -> Paragraph:
    return Paragraph(
        f'<font color="{_ACCENT.hexval()}">{text}</font>',
        styles['_SectionHeading'],
    )


def _flag_color(flagged: bool) -> colors.Color:
    return _FAIL_C if flagged else _PASS_C


def _pass_fail(flagged: bool) -> str:
    return '<font color="#DC2626"><b>FAIL</b></font>' if flagged \
        else '<font color="#16A34A"><b>PASS</b></font>'


def _pct(v: float) -> str:
    return f'{v:.3f}'


def _compute_hash(data: Any) -> str:
    """MD5 of the JSON-serialised data object."""
    raw = json.dumps(data, sort_keys=True, default=str).encode()
    return hashlib.md5(raw).hexdigest()


def _make_table(
    data: List[List],
    col_widths: List[float],
    header_row: bool = True,
    extra_styles: Optional[List] = None,
) -> Table:
    """Build a consistently styled ReportLab Table."""
    tbl = Table(data, colWidths=col_widths)

    base = [
        ('FONTNAME',     (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE',     (0, 0), (-1, -1), 9),
        ('LEFTPADDING',  (0, 0), (-1, -1), 7),
        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING',   (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 5),
        ('GRID',         (0, 0), (-1, -1), 0.4, _BORDER),
        ('ROWBACKGROUNDS', (0, 1 if header_row else 0), (-1, -1),
         [colors.white, _LIGHT_BG]),
    ]

    if header_row:
        base += [
            ('BACKGROUND', (0, 0), (-1, 0), _ACCENT),
            ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
            ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0, 0), (-1, 0), 9),
        ]

    if extra_styles:
        base += extra_styles

    tbl.setStyle(TableStyle(base))
    return tbl


# ══════════════════════════════════════════════════════════════════════════
# Service
# ══════════════════════════════════════════════════════════════════════════

class AuditReportService:

    def generate(
        self,
        dataset_name:      Optional[str],
        dataset_hash:      Optional[str],
        demographics:      Optional[Dict[str, Any]],
        performance:       Optional[Dict[str, Any]],
        fairness:          Optional[Dict[str, Any]],
        proxies:           Optional[Dict[str, Any]],
        mitigation:        Optional[Dict[str, Any]],
        auditor_name:      Optional[str],
    ) -> bytes:
        """
        Build the full audit PDF in memory and return raw bytes.

        Parameters
        ----------
        dataset_name  : display name for the dataset
        dataset_hash  : md5 supplied by the caller (falls back to hash of demographics JSON)
        demographics  : response from POST /audit/demographics
        performance   : response from POST /audit/performance
        fairness      : response from POST /audit/fairness
        proxies       : response from POST /audit/proxies
        mitigation    : optional before/after dict  { original_metrics, mitigated_metrics }
        auditor_name  : pre-filled in sign-off field (optional)
        """
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
            title='FairSight Audit Report',
            author='FairSight',
        )

        styles = self._make_styles()
        story  = self._build_story(
            styles, dataset_name, dataset_hash,
            demographics, performance, fairness,
            proxies, mitigation, auditor_name,
        )

        doc.build(story)
        buf.seek(0)
        return buf.read()

    # ── Style definitions ─────────────────────────────────────────────────

    def _make_styles(self):
        base = getSampleStyleSheet()

        base.add(ParagraphStyle(
            '_ReportTitle',
            parent=base['Normal'],
            fontSize=22,
            fontName='Helvetica-Bold',
            textColor=_ACCENT,
            spaceAfter=2,
        ))
        base.add(ParagraphStyle(
            '_SubTitle',
            parent=base['Normal'],
            fontSize=10,
            fontName='Helvetica',
            textColor=colors.HexColor('#6B7280'),
            spaceAfter=8,
        ))
        base.add(ParagraphStyle(
            '_SectionHeading',
            parent=base['Normal'],
            fontSize=12,
            fontName='Helvetica-Bold',
            spaceBefore=14,
            spaceAfter=6,
        ))
        base.add(ParagraphStyle(
            '_Body',
            parent=base['Normal'],
            fontSize=9,
            leading=14,
            spaceAfter=4,
        ))
        base.add(ParagraphStyle(
            '_TableCell',
            parent=base['Normal'],
            fontSize=9,
            leading=12,
        ))
        base.add(ParagraphStyle(
            '_Italic',
            parent=base['Normal'],
            fontSize=9,
            leading=14,
            fontName='Helvetica-Oblique',
            textColor=colors.HexColor('#374151'),
        ))
        base.add(ParagraphStyle(
            '_SignoffLabel',
            parent=base['Normal'],
            fontSize=9,
            fontName='Helvetica-Bold',
            spaceAfter=16,
        ))
        return base

    # ── Master story ──────────────────────────────────────────────────────

    def _build_story(
        self, styles,
        dataset_name, dataset_hash,
        demographics, performance, fairness,
        proxies, mitigation, auditor_name,
    ) -> list:
        story: list = []

        # Compute fallback hash
        if not dataset_hash:
            source = demographics or performance or fairness or proxies or {}
            dataset_hash = _compute_hash(source)

        story += self._s1_header(styles, dataset_name, dataset_hash)
        story += self._s2_dataset_summary(styles, demographics)
        story += self._s3_fairness_metrics(styles, fairness)
        story += self._s4_proxy_findings(styles, proxies)
        story += self._s5_mitigation(styles, mitigation)
        story += self._s6_limitations(styles)
        story += self._s7_signoff(styles, auditor_name)

        return story

    # ── Section 1: Header ─────────────────────────────────────────────────

    def _s1_header(self, styles, dataset_name, dataset_hash) -> list:
        now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
        name_str = dataset_name or 'Unnamed dataset'

        story = [
            Paragraph('FairSight Audit Report', styles['_ReportTitle']),
            Paragraph(
                f'{name_str} &nbsp;·&nbsp; Generated {now}',
                styles['_SubTitle'],
            ),
            Paragraph(
                f'<font color="#9CA3AF">Dataset hash (MD5): <font name="Courier">{dataset_hash}</font></font>',
                styles['_Body'],
            ),
            HRFlowable(width='100%', thickness=2, color=_ACCENT,
                       spaceAfter=12, spaceBefore=4),
        ]
        return story

    # ── Section 2: Dataset Summary ────────────────────────────────────────

    def _s2_dataset_summary(self, styles, demographics) -> list:
        story = [_section_heading('1. Dataset Summary', styles)]

        if not demographics:
            story.append(Paragraph('<i>No demographics data provided.</i>', styles['_Italic']))
            return story

        num_rows  = demographics.get('num_rows', 'N/A')
        prot_cols = demographics.get('columns_analyzed', [])
        results   = demographics.get('results', {})

        story.append(Paragraph(
            f'<b>Total rows:</b> {num_rows:,}' if isinstance(num_rows, int) else f'<b>Total rows:</b> {num_rows}',
            styles['_Body'],
        ))
        story.append(Paragraph(
            f'<b>Protected columns:</b> {", ".join(prot_cols) if prot_cols else "N/A"}',
            styles['_Body'],
        ))
        story.append(Spacer(1, 0.3 * cm))

        # One distribution table per protected column
        for col, col_data in results.items():
            story.append(Paragraph(
                f'<b>Column:</b> <font name="Courier">{col}</font> — '
                f'representation score {col_data.get("representation_score", 0):.2f}',
                styles['_Body'],
            ))

            vc = col_data.get('value_counts', {})
            pcts = col_data.get('percentages', {})
            ug = set(col_data.get('underrepresented_groups', []))

            if vc:
                tdata = [['Group', 'Count', 'Percentage', 'Under-rep?']]
                for grp, cnt in vc.items():
                    flag = '⚠ Yes' if grp in ug else 'No'
                    tdata.append([
                        str(grp),
                        str(cnt),
                        f'{pcts.get(grp, 0):.1f}%',
                        flag,
                    ])

                extra = [('TEXTCOLOR', (3, i+1), (3, i+1), _WARN_C)
                         for i, g in enumerate(vc.keys()) if g in ug]
                tbl = _make_table(tdata, [5*cm, 3*cm, 3*cm, 3*cm], extra_styles=extra)
                story.append(tbl)

            story.append(Spacer(1, 0.3 * cm))

        return story

    # ── Section 3: Fairness Metrics ───────────────────────────────────────

    def _s3_fairness_metrics(self, styles, fairness) -> list:
        story = [_section_heading('2. Fairness Metrics', styles)]

        METRIC_META = {
            'demographic_parity_difference': ('DPD', 'Demographic Parity Difference', '> 0.10'),
            'equal_opportunity_difference':  ('EOD', 'Equal Opportunity Difference',  '> 0.10'),
            'disparate_impact_ratio':        ('DIR', 'Disparate Impact Ratio',         '< 0.80'),
        }

        if not fairness:
            story.append(Paragraph('<i>No fairness data provided.</i>', styles['_Italic']))
            return story

        metrics = fairness.get('metrics', {})
        overall_pass = fairness.get('overall_pass', None)

        # Overall verdict
        if overall_pass is not None:
            verdict_txt = (
                '<font color="#16A34A"><b>✓ All fairness metrics passing.</b></font>'
                if overall_pass else
                '<font color="#DC2626"><b>✗ One or more fairness metrics failing.</b></font>'
            )
            story.append(Paragraph(verdict_txt, styles['_Body']))
            story.append(Spacer(1, 0.2 * cm))

        # Metrics table
        tdata = [['Metric', 'Abbreviation', 'Value', 'Threshold', 'Status']]
        extra_styles = []

        for i, (key, meta_data) in enumerate(metrics.items()):
            abbr, label, threshold = METRIC_META.get(key, (key, key, ''))
            val     = meta_data.get('value', None)
            flagged = meta_data.get('flagged', False)
            row_idx = i + 1

            tdata.append([
                label,
                abbr,
                _pct(val) if val is not None else '—',
                f'Fail if {threshold}',
                Paragraph(_pass_fail(flagged), styles['_TableCell']),
            ])

            bg = colors.HexColor('#FEF2F2') if flagged else colors.HexColor('#F0FDF4')
            extra_styles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), bg))

        tbl = _make_table(
            tdata,
            [5.5*cm, 2*cm, 2.5*cm, 3*cm, 2*cm],
            extra_styles=extra_styles,
        )
        story.append(tbl)

        # Conflict warning
        warning = fairness.get('warning')
        if warning:
            story.append(Spacer(1, 0.3 * cm))
            story.append(Paragraph(
                f'<font color="#D97706"><b>⚠ Note:</b></font> {warning}',
                styles['_Body'],
            ))

        # Group stats
        group_stats = fairness.get('group_stats', {})
        if group_stats:
            story.append(Spacer(1, 0.3 * cm))
            story.append(Paragraph('<b>Group approval rates:</b>', styles['_Body']))
            gs_data = [['Group', 'Approval Rate', 'True Positive Rate']]
            for grp, stats in group_stats.items():
                gs_data.append([
                    str(grp),
                    f'{stats.get("approval_rate", 0):.3f}',
                    f'{stats.get("tpr", 0):.3f}' if stats.get("tpr") is not None else '—',
                ])
            story.append(_make_table(gs_data, [5*cm, 4.5*cm, 4.5*cm]))

        return story

    # ── Section 4: Proxy Findings ─────────────────────────────────────────

    def _s4_proxy_findings(self, styles, proxies) -> list:
        story = [_section_heading('3. Proxy Findings', styles)]

        if not proxies:
            story.append(Paragraph('<i>No proxy analysis data provided.</i>', styles['_Italic']))
            return story

        features     = proxies.get('features', [])
        n_high       = proxies.get('num_high_risk', 0)
        n_analyzed   = proxies.get('num_features_analyzed', 0)
        threshold    = proxies.get('proxy_risk_threshold', 0.3)
        prot_cols    = proxies.get('protected_columns_found', [])

        story.append(Paragraph(
            f'<b>{n_high}</b> of <b>{n_analyzed}</b> features flagged as HIGH RISK '
            f'(proxy risk score &gt; {threshold}). '
            f'Protected columns tested: {", ".join(prot_cols) if prot_cols else "N/A"}.',
            styles['_Body'],
        ))
        story.append(Spacer(1, 0.2 * cm))

        if not features:
            story.append(Paragraph('<i>No features found.</i>', styles['_Italic']))
            return story

        tdata = [['Feature', 'Proxy Risk Score', 'Risk Level']]
        extra_styles = []

        for i, feat in enumerate(features):
            score   = feat.get('proxy_risk_score', 0)
            flagged = feat.get('flagged', False)
            level   = feat.get('risk_level', 'LOW RISK')
            row_idx = i + 1

            risk_para = Paragraph(
                f'<font color="#DC2626"><b>{level}</b></font>' if flagged else level,
                styles['_TableCell'],
            )
            tdata.append([
                Paragraph(f'<font name="Courier">{feat["feature"]}</font>',
                          styles['_TableCell']),
                f'{score:.4f}',
                risk_para,
            ])

            if flagged:
                extra_styles.append(
                    ('BACKGROUND', (0, row_idx), (-1, row_idx),
                     colors.HexColor('#FEF2F2'))
                )

        tbl = _make_table(tdata, [7*cm, 4*cm, 4*cm], extra_styles=extra_styles)
        story.append(tbl)
        return story

    # ── Section 5: Mitigation ─────────────────────────────────────────────

    def _s5_mitigation(self, styles, mitigation) -> list:
        story = [_section_heading('4. Mitigation Applied', styles)]

        if not mitigation:
            story.append(Paragraph(
                'No mitigation algorithm was applied during this audit. '
                'Metrics reflect the model\'s raw predictions.',
                styles['_Body'],
            ))
            return story

        before = mitigation.get('original_metrics', {})
        after  = mitigation.get('mitigated_metrics', {})
        method = mitigation.get('method', 'Not specified')

        story.append(Paragraph(f'<b>Method:</b> {method}', styles['_Body']))
        story.append(Spacer(1, 0.2 * cm))

        if before or after:
            all_keys = sorted(set(list(before.keys()) + list(after.keys())))

            ABBR = {
                'demographic_parity_difference': 'DPD',
                'equal_opportunity_difference':  'EOD',
                'disparate_impact_ratio':        'DIR',
            }

            tdata = [['Metric', 'Before Mitigation', 'After Mitigation', 'Change']]
            for key in all_keys:
                b_val = before.get(key)
                a_val = after.get(key)
                b_str = f'{b_val:.4f}' if isinstance(b_val, float) else str(b_val or '—')
                a_str = f'{a_val:.4f}' if isinstance(a_val, float) else str(a_val or '—')

                if isinstance(b_val, float) and isinstance(a_val, float):
                    delta = a_val - b_val
                    change = f'{delta:+.4f}'
                    c_color = '#16A34A' if delta < 0 else '#DC2626'
                    change_para = Paragraph(
                        f'<font color="{c_color}">{change}</font>',
                        styles['_TableCell'],
                    )
                else:
                    change_para = Paragraph('—', styles['_TableCell'])

                label = ABBR.get(key, key.replace('_', ' ').title())
                tdata.append([label, b_str, a_str, change_para])

            story.append(_make_table(tdata, [5.5*cm, 3.5*cm, 3.5*cm, 2.5*cm]))

        return story

    # ── Section 6: Limitations ────────────────────────────────────────────

    def _s6_limitations(self, styles) -> list:
        story = [_section_heading('5. Limitations & Disclaimer', styles)]

        limitations = (
            'This report documents the mathematical fairness properties of the model\'s '
            'predictions as measured by specific statistical metrics: Demographic Parity '
            'Difference (DPD), Equal Opportunity Difference (EOD), and Disparate Impact '
            'Ratio (DIR). Compliance with or violation of these metrics does not constitute '
            'a certification that the model is fair, unbiased, or suitable for use in '
            'high-stakes decisions affecting individuals. '
            '<br/><br/>'
            'The metrics used reflect specific mathematical definitions of fairness that '
            'may conflict with each other and with other definitions not measured here. '
            'Satisfying one fairness criterion does not imply satisfying others. '
            '<br/><br/>'
            'Proxy risk scores indicate statistical correlation between a feature and a '
            'protected attribute; correlation does not prove causal discrimination. '
            'SHAP values and counterfactual explanations are model-dependent approximations '
            'and should be interpreted with appropriate statistical caution. '
            '<br/><br/>'
            '<b>Human review by a qualified AI ethics practitioner or legal professional is '
            'required before this audit is used as the basis for any deployment, compliance, '
            'or governance decision.</b> This report should be regarded as one component of '
            'a broader responsible AI governance process.'
        )

        story.append(Paragraph(limitations, styles['_Body']))
        return story

    # ── Section 7: Sign-off ───────────────────────────────────────────────

    def _s7_signoff(self, styles, auditor_name: Optional[str]) -> list:
        story = [
            _section_heading('6. Auditor Sign-Off', styles),
            Paragraph(
                'By signing below, the auditor confirms they have reviewed this report '
                'and take responsibility for its conclusions.',
                styles['_Body'],
            ),
            Spacer(1, 0.8 * cm),
        ]

        prefilled_name = auditor_name or ''
        gap = '&nbsp;' * 60   # blank fill line

        fields = [
            ('Auditor Name', prefilled_name),
            ('Date',         ''),
            ('Signature',    ''),
        ]

        for label, prefill in fields:
            value = prefill if prefill else gap
            story.append(Paragraph(
                f'<b>{label}:</b> &nbsp; '
                f'<font color="#9CA3AF">{value}</font>'
                f'<br/>'
                f'<font color="#D1D5DB">{"_" * 65}</font>',
                styles['_SignoffLabel'],
            ))

        story += [
            Spacer(1, 1 * cm),
            _hr(0.5),
            Paragraph(
                '<i>FairSight — Automated AI Fairness Auditing.</i>',
                styles['_Italic'],
            ),
        ]
        return story
